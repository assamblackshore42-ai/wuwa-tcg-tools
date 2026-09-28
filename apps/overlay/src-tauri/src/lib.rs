use std::fs;

use tauri::Manager;
use tracing_subscriber::EnvFilter;

pub mod local_server;
pub mod match_state;
pub mod match_store;

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
        .setup(|app| {
            let data_directory = app.path().app_data_dir()?;
            fs::create_dir_all(&data_directory)?;
            let store = match_store::SqliteMatchStore::open(data_directory.join("match.sqlite3"))?;

            tauri::async_runtime::spawn(async move {
                match tokio::net::TcpListener::bind(local_server::LOCAL_SERVER_ADDRESS).await {
                    Ok(listener) => {
                        tracing::info!(
                            address = local_server::LOCAL_SERVER_ADDRESS,
                            "local OBS overlay server started"
                        );
                        if let Err(error) = local_server::serve_local(listener, store).await {
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
        .run(tauri::generate_context!())
        .expect("failed to run the OBS overlay application");
}
