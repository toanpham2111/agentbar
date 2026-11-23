pub mod adapters;
pub mod core;
pub mod database;
pub mod platform;
pub mod services;

#[cfg(feature = "desktop")]
mod desktop;

#[cfg(feature = "desktop")]
pub fn run() {
    desktop::run();
}
