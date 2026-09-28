use std::path::PathBuf;
use std::sync::Arc;

use axum::Json;
use axum::extract::State;
use axum::extract::ws::{Message, WebSocket, WebSocketUpgrade};
use axum::http::{HeaderMap, HeaderValue, Method, StatusCode, header};
use axum::response::{IntoResponse, Response};
use axum::routing::{get, post};
use axum::{Router, serve};
use serde::Serialize;
use tokio::net::TcpListener;
use tokio::sync::{Mutex, broadcast};
use tower_http::cors::CorsLayer;
use tower_http::services::{ServeDir, ServeFile};
use tower_http::trace::TraceLayer;

use crate::match_state::{MatchCommand, MatchState};
use crate::match_store::{MatchStoreError, SqliteMatchStore};

pub const LOCAL_SERVER_ADDRESS: &str = "127.0.0.1:38471";
const UPDATE_CHANNEL_CAPACITY: usize = 32;
const ALLOWED_ORIGINS: [&str; 5] = [
    "http://127.0.0.1:1420",
    "http://localhost:1420",
    "http://127.0.0.1:38471",
    "http://tauri.localhost",
    "https://tauri.localhost",
];

#[derive(Clone)]
struct ApiState {
    store: Arc<Mutex<SqliteMatchStore>>,
    updates: broadcast::Sender<MatchState>,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct CommandResponse {
    changed: bool,
    state: MatchState,
}

#[derive(Debug, Serialize)]
struct ErrorResponse {
    error: String,
}

struct ApiError(MatchStoreError);

impl IntoResponse for ApiError {
    fn into_response(self) -> Response {
        let status = match self.0 {
            MatchStoreError::State(_) => StatusCode::UNPROCESSABLE_ENTITY,
            MatchStoreError::Database(_) | MatchStoreError::Serialization(_) => {
                StatusCode::INTERNAL_SERVER_ERROR
            }
        };
        let message = self.0.to_string();
        (status, Json(ErrorResponse { error: message })).into_response()
    }
}

/// Builds the local API router around the supplied persistent match store.
pub fn router(store: SqliteMatchStore) -> Router {
    let (updates, _) = broadcast::channel(UPDATE_CHANNEL_CAPACITY);
    build_router(store, updates, None)
}

/// Builds the local API and serves the React application as an SPA fallback.
pub fn router_with_frontend(store: SqliteMatchStore, frontend_directory: PathBuf) -> Router {
    let (updates, _) = broadcast::channel(UPDATE_CHANNEL_CAPACITY);
    build_router(store, updates, Some(frontend_directory))
}

fn build_router(
    store: SqliteMatchStore,
    updates: broadcast::Sender<MatchState>,
    frontend_directory: Option<PathBuf>,
) -> Router {
    let cors = CorsLayer::new()
        .allow_origin(ALLOWED_ORIGINS.map(HeaderValue::from_static))
        .allow_methods([Method::GET, Method::POST])
        .allow_headers([header::CONTENT_TYPE]);

    let router = Router::new()
        .route("/api/state", get(get_state))
        .route("/api/commands", post(post_command))
        .route("/ws", get(web_socket))
        .with_state(ApiState {
            store: Arc::new(Mutex::new(store)),
            updates,
        })
        .layer(cors)
        .layer(TraceLayer::new_for_http());

    if let Some(directory) = frontend_directory {
        let index = directory.join("index.html");
        router.fallback_service(ServeDir::new(directory).fallback(ServeFile::new(index)))
    } else {
        router
    }
}

/// Serves the local API until the application shuts down or the listener fails.
///
/// # Errors
///
/// Returns an I/O error when accepting or serving a connection fails.
pub async fn serve_local(
    listener: TcpListener,
    store: SqliteMatchStore,
    frontend_directory: Option<PathBuf>,
) -> std::io::Result<()> {
    let app = match frontend_directory {
        Some(directory) => router_with_frontend(store, directory),
        None => router(store),
    };
    serve(listener, app).await
}

async fn get_state(State(api): State<ApiState>) -> Json<MatchState> {
    let store = api.store.lock().await;
    Json(store.state().clone())
}

async fn post_command(
    State(api): State<ApiState>,
    Json(command): Json<MatchCommand>,
) -> Result<Json<CommandResponse>, ApiError> {
    let mut store = api.store.lock().await;
    let changed = store.apply(command).map_err(ApiError)?;
    let state = store.state().clone();
    drop(store);

    if changed {
        let _ = api.updates.send(state.clone());
    }

    Ok(Json(CommandResponse { changed, state }))
}

async fn web_socket(
    State(api): State<ApiState>,
    headers: HeaderMap,
    upgrade: WebSocketUpgrade,
) -> Response {
    if !is_allowed_web_socket_origin(headers.get(header::ORIGIN)) {
        return StatusCode::FORBIDDEN.into_response();
    }

    upgrade
        .on_upgrade(move |socket| stream_match_updates(socket, api))
        .into_response()
}

fn is_allowed_web_socket_origin(origin: Option<&HeaderValue>) -> bool {
    origin.is_none_or(|value| {
        value
            .to_str()
            .is_ok_and(|value| ALLOWED_ORIGINS.contains(&value))
    })
}

async fn stream_match_updates(mut socket: WebSocket, api: ApiState) {
    let mut updates = api.updates.subscribe();
    let initial_state = {
        let store = api.store.lock().await;
        store.state().clone()
    };
    let mut last_revision = initial_state.revision;

    if send_state(&mut socket, &initial_state).await.is_err() {
        return;
    }

    loop {
        match updates.recv().await {
            Ok(state) if state.revision > last_revision => {
                last_revision = state.revision;
                if send_state(&mut socket, &state).await.is_err() {
                    return;
                }
            }
            Ok(_) | Err(broadcast::error::RecvError::Lagged(_)) => {}
            Err(broadcast::error::RecvError::Closed) => return,
        }
    }
}

async fn send_state(socket: &mut WebSocket, state: &MatchState) -> Result<(), axum::Error> {
    let json = serde_json::to_string(state).map_err(axum::Error::new)?;
    socket.send(Message::Text(json.into())).await
}

#[cfg(test)]
mod tests {
    use std::fs;
    use std::time::{SystemTime, UNIX_EPOCH};

    use axum::body::{Body, to_bytes};
    use axum::http::Request;
    use serde_json::{Value, json};
    use tower::ServiceExt;

    use super::*;

    #[tokio::test]
    async fn gets_the_current_match_state() {
        let app = router(SqliteMatchStore::open_in_memory().unwrap());
        let response = app
            .oneshot(
                Request::builder()
                    .uri("/api/state")
                    .body(Body::empty())
                    .unwrap(),
            )
            .await
            .unwrap();

        assert_eq!(response.status(), StatusCode::OK);
        let body = to_bytes(response.into_body(), 64 * 1024).await.unwrap();
        let state: MatchState = serde_json::from_slice(&body).unwrap();
        assert_eq!(state, MatchState::default());
    }

    #[tokio::test]
    async fn applies_a_command_and_returns_the_updated_state() {
        let app = router(SqliteMatchStore::open_in_memory().unwrap());
        let response = app
            .oneshot(
                Request::builder()
                    .method(Method::POST)
                    .uri("/api/commands")
                    .header(header::CONTENT_TYPE, "application/json")
                    .body(Body::from(
                        json!({
                            "type": "adjust_life",
                            "player": "player_one",
                            "amount": -2
                        })
                        .to_string(),
                    ))
                    .unwrap(),
            )
            .await
            .unwrap();

        assert_eq!(response.status(), StatusCode::OK);
        let body = to_bytes(response.into_body(), 64 * 1024).await.unwrap();
        let payload: Value = serde_json::from_slice(&body).unwrap();
        assert_eq!(payload["changed"], true);
        assert_eq!(payload["state"]["players"][0]["life"], 18);
        assert_eq!(payload["state"]["revision"], 1);
    }

    #[tokio::test]
    async fn rejects_an_invalid_command_without_changing_the_state() {
        let app = router(SqliteMatchStore::open_in_memory().unwrap());
        let invalid_response = app
            .clone()
            .oneshot(
                Request::builder()
                    .method(Method::POST)
                    .uri("/api/commands")
                    .header(header::CONTENT_TYPE, "application/json")
                    .body(Body::from(
                        json!({
                            "type": "set_life",
                            "player": "player_two",
                            "life": 1000
                        })
                        .to_string(),
                    ))
                    .unwrap(),
            )
            .await
            .unwrap();

        assert_eq!(invalid_response.status(), StatusCode::UNPROCESSABLE_ENTITY);

        let state_response = app
            .oneshot(
                Request::builder()
                    .uri("/api/state")
                    .body(Body::empty())
                    .unwrap(),
            )
            .await
            .unwrap();
        let body = to_bytes(state_response.into_body(), 64 * 1024)
            .await
            .unwrap();
        let state: MatchState = serde_json::from_slice(&body).unwrap();
        assert_eq!(state, MatchState::default());
    }

    #[tokio::test]
    async fn broadcasts_each_state_changing_command() {
        let (updates, mut receiver) = broadcast::channel(UPDATE_CHANNEL_CAPACITY);
        let app = build_router(SqliteMatchStore::open_in_memory().unwrap(), updates, None);

        let response = app
            .oneshot(
                Request::builder()
                    .method(Method::POST)
                    .uri("/api/commands")
                    .header(header::CONTENT_TYPE, "application/json")
                    .body(Body::from(
                        json!({
                            "type": "end_turn"
                        })
                        .to_string(),
                    ))
                    .unwrap(),
            )
            .await
            .unwrap();

        assert_eq!(response.status(), StatusCode::OK);
        let state = receiver.recv().await.unwrap();
        assert_eq!(state.revision, 1);
        assert_eq!(state.turn.number, 2);
    }

    #[tokio::test]
    async fn serves_the_spa_entry_point_for_the_overlay_route() {
        let unique = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        let directory = std::env::temp_dir().join(format!(
            "wuwatcg-overlay-frontend-{}-{unique}",
            std::process::id()
        ));
        fs::create_dir(&directory).unwrap();
        fs::write(directory.join("index.html"), "<main>OBS overlay</main>").unwrap();
        let app = router_with_frontend(
            SqliteMatchStore::open_in_memory().unwrap(),
            directory.clone(),
        );

        let response = app
            .oneshot(
                Request::builder()
                    .uri("/overlay")
                    .body(Body::empty())
                    .unwrap(),
            )
            .await
            .unwrap();

        assert_eq!(response.status(), StatusCode::OK);
        let body = to_bytes(response.into_body(), 64 * 1024).await.unwrap();
        assert_eq!(body, "<main>OBS overlay</main>");

        fs::remove_dir_all(directory).unwrap();
    }

    #[test]
    fn rejects_unknown_browser_origins_for_web_sockets() {
        assert!(is_allowed_web_socket_origin(Some(
            &HeaderValue::from_static("http://127.0.0.1:1420")
        )));
        assert!(is_allowed_web_socket_origin(None));
        assert!(!is_allowed_web_socket_origin(Some(
            &HeaderValue::from_static("https://example.com")
        )));
    }
}
