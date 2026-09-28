use std::fs;
use std::path::PathBuf;

use tauri::Manager;
use tracing_subscriber::EnvFilter;

pub mod local_server;
pub mod match_state;
pub mod match_store;
pub mod tray;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
/// Starts the desktop application event loop.
///
/// # Panics
///
/// Panics when Tauri cannot initialize or run the application.
pub fn run() {
    let filter = EnvFilter::try_from_default_env().unwrap_or_else(|_| EnvFilter::new("info"));
    let _ = tracing_subscriber::fmt().with_env_filter(filter).try_init();

    tauri::Builder::default()
        .plugin(tauri_plugin_single_instance::init(|app, _args, _cwd| {
            tray::show_control_window(app);
        }))
        .setup(|app| {
            tray::setup(app)?;
            let data_directory = app.path().app_data_dir()?;
            fs::create_dir_all(&data_directory)?;
            let store = match_store::SqliteMatchStore::open(data_directory.join("match.sqlite3"))?;
            let resource_frontend = app.path().resource_dir()?.join("dist");
            let development_frontend = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../dist");
            let frontend_directory = if resource_frontend.is_dir() {
                Some(resource_frontend)
            } else if development_frontend.is_dir() {
                Some(development_frontend)
            } else {
                None
            };

            tauri::async_runtime::spawn(async move {
                match tokio::net::TcpListener::bind(local_server::LOCAL_SERVER_ADDRESS).await {
                    Ok(listener) => {
                        tracing::info!(
                            address = local_server::LOCAL_SERVER_ADDRESS,
                            "local OBS overlay server started"
                        );
                        if let Err(error) =
                            local_server::serve_local(listener, store, frontend_directory).await
                        {
                            tracing::error!(%error, "local OBS overlay server stopped");
                        }
                    }
                    Err(error) => {
                        tracing::error!(
                            %error,
                            address = local_server::LOCAL_SERVER_ADDRESS,
                            "failed to bind local OBS overlay server"
                        );
                    }
                }
            });

            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                api.prevent_close();
                if let Err(error) = window.hide() {
                    tracing::error!(%error, "failed to hide control window");
                }
            }
        })
        .run(tauri::generate_context!())
        .expect("failed to run the OBS overlay application");
}
