use tauri::menu::{Menu, MenuItem};
use tauri::tray::TrayIconBuilder;
use tauri::{App, Manager};

const SHOW_CONTROL_ID: &str = "show-control";
const QUIT_ID: &str = "quit";

/// Creates the desktop tray menu used while the control window is hidden.
///
/// # Errors
///
/// Returns an error if a menu item or tray icon cannot be created.
pub fn setup(app: &App) -> tauri::Result<()> {
    let show_control =
        MenuItem::with_id(app, SHOW_CONTROL_ID, "操作画面を表示", true, None::<&str>)?;
    let quit = MenuItem::with_id(app, QUIT_ID, "終了", true, None::<&str>)?;
    let menu = Menu::with_items(app, &[&show_control, &quit])?;

    let mut builder = TrayIconBuilder::with_id("main-tray")
        .menu(&menu)
        .tooltip("鳴潮：対決 オーバーレイ")
        .on_menu_event(|app, event| match event.id().as_ref() {
            SHOW_CONTROL_ID => show_control_window(app),
            QUIT_ID => app.exit(0),
            _ => {}
        });

    if let Some(icon) = app.default_window_icon() {
        builder = builder.icon(icon.clone());
    }

    builder.build(app)?;
    Ok(())
}

pub fn show_control_window(app: &tauri::AppHandle) {
    if let Some(window) = app.get_webview_window("main") {
        if let Err(error) = window.show() {
            tracing::error!(%error, "failed to show control window");
        }
        if let Err(error) = window.set_focus() {
            tracing::error!(%error, "failed to focus control window");
        }
    }
}
