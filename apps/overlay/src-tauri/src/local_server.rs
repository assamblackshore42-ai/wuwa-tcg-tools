use std::sync::Arc;

use axum::Json;
use axum::extract::State;
use axum::http::{HeaderValue, Method, StatusCode, header};
use axum::response::{IntoResponse, Response};
use axum::routing::{get, post};
use axum::{Router, serve};
use serde::Serialize;
use tokio::net::TcpListener;
use tokio::sync::Mutex;
use tower_http::cors::CorsLayer;
use tower_http::trace::TraceLayer;

use crate::match_state::{MatchCommand, MatchState};
use crate::match_store::{MatchStoreError, SqliteMatchStore};

pub const LOCAL_SERVER_ADDRESS: &str = "127.0.0.1:38471";

#[derive(Clone)]
struct ApiState {
    store: Arc<Mutex<SqliteMatchStore>>,
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
    let cors = CorsLayer::new()
        .allow_origin([
            HeaderValue::from_static("http://127.0.0.1:1420"),
            HeaderValue::from_static("http://localhost:1420"),
            HeaderValue::from_static("http://tauri.localhost"),
            HeaderValue::from_static("https://tauri.localhost"),
        ])
        .allow_methods([Method::GET, Method::POST])
        .allow_headers([header::CONTENT_TYPE]);

    Router::new()
        .route("/api/state", get(get_state))
        .route("/api/commands", post(post_command))
        .with_state(ApiState {
            store: Arc::new(Mutex::new(store)),
        })
        .layer(cors)
        .layer(TraceLayer::new_for_http())
}

/// Serves the local API until the application shuts down or the listener fails.
///
/// # Errors
///
/// Returns an I/O error when accepting or serving a connection fails.
pub async fn serve_local(listener: TcpListener, store: SqliteMatchStore) -> std::io::Result<()> {
    serve(listener, router(store)).await
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

    Ok(Json(CommandResponse {
        changed,
        state: store.state().clone(),
    }))
}

#[cfg(test)]
mod tests {
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
}
