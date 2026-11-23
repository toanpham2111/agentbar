use std::sync::Arc;

use tauri::{
    AppHandle, Emitter, Manager, State,
    menu::{MenuBuilder, MenuItemBuilder},
    tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent},
};
use tokio::sync::RwLock;

use crate::{
    adapters::ProviderRegistry,
    core::{
        error::AppError,
        models::{
            AlertRule, AppSettings, ExportPayload, HistoryPoint, ProviderSnapshot, QuotaWindow,
            UsageSummary,
        },
    },
    database::repository::{UsageRepository, validate_settings},
    services::{
        collector::{CollectorService, parse_provider_id},
        scheduler::CollectorScheduler,
    },
};

pub struct AppState {
    collector: CollectorService,
    repository: UsageRepository,
    settings: RwLock<AppSettings>,
    alert_rules: RwLock<Vec<AlertRule>>,
}

#[tauri::command]
async fn discover_providers(state: State<'_, AppState>) -> Result<Vec<ProviderSnapshot>, AppError> {
    Ok(state.collector.current().await)
}

#[tauri::command]
async fn get_providers(state: State<'_, AppState>) -> Result<Vec<ProviderSnapshot>, AppError> {
    Ok(state.collector.current().await)
}

#[tauri::command]
async fn refresh_provider(
    provider_id: String,
    state: State<'_, AppState>,
    app: AppHandle,
) -> Result<ProviderSnapshot, AppError> {
    let snapshot = state
        .collector
        .refresh_provider(parse_provider_id(&provider_id)?)
        .await?;
    app.emit("provider:updated", &snapshot)
        .map_err(|error| AppError::Validation(error.to_string()))?;
    Ok(snapshot)
}

#[tauri::command]
async fn refresh_all(
    state: State<'_, AppState>,
    app: AppHandle,
) -> Result<Vec<ProviderSnapshot>, AppError> {
    let snapshots = state.collector.refresh_all().await;
    app.emit("usage:updated", &snapshots)
        .map_err(|error| AppError::Validation(error.to_string()))?;
    Ok(snapshots)
}

#[tauri::command]
async fn get_usage_summary(state: State<'_, AppState>) -> Result<UsageSummary, AppError> {
    Ok(CollectorService::summary(&state.collector.current().await))
}

#[tauri::command]
async fn get_usage_history(
    days: u16,
    state: State<'_, AppState>,
) -> Result<Vec<HistoryPoint>, AppError> {
    state.repository.history(days).await
}

#[tauri::command]
async fn get_quota_windows(
    provider_id: String,
    state: State<'_, AppState>,
) -> Result<Vec<QuotaWindow>, AppError> {
    let snapshot = state
        .collector
        .refresh_provider(parse_provider_id(&provider_id)?)
        .await?;
    Ok(snapshot.quota_windows)
}

#[tauri::command]
async fn get_alert_rules(state: State<'_, AppState>) -> Result<Vec<AlertRule>, AppError> {
    Ok(state.alert_rules.read().await.clone())
}

#[tauri::command]
async fn update_alert_rules(
    rules: Vec<AlertRule>,
    state: State<'_, AppState>,
) -> Result<Vec<AlertRule>, AppError> {
    if rules
        .iter()
        .any(|rule| rule.threshold == 0 || rule.threshold > 100)
    {
        return Err(AppError::Validation(
            "alert thresholds must be between 1 and 100".into(),
        ));
    }
    *state.alert_rules.write().await = rules.clone();
    Ok(rules)
}

#[tauri::command]
async fn export_usage(
    format: String,
    days: u16,
    state: State<'_, AppState>,
) -> Result<ExportPayload, AppError> {
    let history = state.repository.history(days).await?;
    let content = match format.as_str() {
        "json" => serde_json::to_string_pretty(&history)
            .map_err(|error| AppError::Validation(error.to_string()))?,
        "csv" => {
            let mut output = String::from("date,provider_id,tokens,estimated_cost_usd\n");
            for point in history {
                output.push_str(&format!(
                    "{},{},{},{}\n",
                    point.date,
                    point.provider_id,
                    point.tokens,
                    point
                        .estimated_cost_usd
                        .map(|value| value.to_string())
                        .unwrap_or_default()
                ));
            }
            output
        }
        _ => {
            return Err(AppError::Validation(
                "export format must be csv or json".into(),
            ));
        }
    };
    Ok(ExportPayload { format, content })
}

#[tauri::command]
async fn get_settings(state: State<'_, AppState>) -> Result<AppSettings, AppError> {
    Ok(state.settings.read().await.clone())
}

#[tauri::command]
async fn update_settings(
    settings: AppSettings,
    state: State<'_, AppState>,
) -> Result<AppSettings, AppError> {
    validate_settings(&settings)?;
    state.repository.save_settings(&settings).await?;
    *state.settings.write().await = settings.clone();
    Ok(settings)
}

fn setup_tray(app: &tauri::App) -> tauri::Result<()> {
    let open = MenuItemBuilder::with_id("open", "Open Dashboard").build(app)?;
    let refresh = MenuItemBuilder::with_id("refresh", "Refresh All").build(app)?;
    let settings = MenuItemBuilder::with_id("settings", "Settings").build(app)?;
    let quit = MenuItemBuilder::with_id("quit", "Quit").build(app)?;
    let menu = MenuBuilder::new(app)
        .items(&[&open, &refresh, &settings, &quit])
        .build()?;
    TrayIconBuilder::with_id("main")
        .menu(&menu)
        .show_menu_on_left_click(false)
        .on_menu_event(|app, event| match event.id().as_ref() {
            "open" => show_main(app),
            "settings" => {
                show_main(app);
                let _ = app.emit("navigate", "/settings");
            }
            "refresh" => {
                let app = app.clone();
                tauri::async_runtime::spawn(async move {
                    let state = app.state::<AppState>();
                    let snapshots = state.collector.refresh_all().await;
                    let _ = app.emit("usage:updated", snapshots);
                });
            }
            "quit" => app.exit(0),
            _ => {}
        })
        .on_tray_icon_event(|tray, event| {
            if let TrayIconEvent::Click {
                button: MouseButton::Left,
                button_state: MouseButtonState::Up,
                ..
            } = event
            {
                show_main(tray.app_handle());
            }
        })
        .build(app)?;
    Ok(())
}

fn show_main(app: &AppHandle) {
    if let Some(window) = app.get_webview_window("main") {
        let _ = window.show();
        let _ = window.set_focus();
    }
}

pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_notification::init())
        .plugin(tauri_plugin_autostart::Builder::new().build())
        .setup(|app| {
            let data_dir = app.path().app_data_dir()?;
            let repository =
                tauri::async_runtime::block_on(UsageRepository::open(&data_dir.join("usage.db")))
                    .map_err(|error| std::io::Error::other(error.to_string()))?;
            let settings =
                tauri::async_runtime::block_on(repository.get_settings()).unwrap_or_default();
            let collector =
                CollectorService::new(Arc::new(ProviderRegistry::default()), repository.clone());
            let _scheduler =
                CollectorScheduler::start(collector.clone(), settings.refresh_interval_minutes);
            app.manage(AppState {
                collector,
                repository,
                settings: RwLock::new(settings),
                alert_rules: RwLock::new(AlertRule::defaults()),
            });
            setup_tray(app)?;
            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                api.prevent_close();
                let _ = window.hide();
            }
        })
        .invoke_handler(tauri::generate_handler![
            discover_providers,
            get_providers,
            refresh_provider,
            refresh_all,
            get_usage_summary,
            get_usage_history,
            get_quota_windows,
            get_alert_rules,
            update_alert_rules,
            get_settings,
            update_settings,
            export_usage
        ])
        .run(tauri::generate_context!())
        .expect("failed to run KIO Usage Monitor");
}
