#[cfg(feature = "desktop")]
fn main() {
    kio_usage_monitor_lib::run();
}

#[cfg(not(feature = "desktop"))]
fn main() {
    println!("KIO Usage Monitor core build; enable the desktop feature to launch Tauri.");
}
