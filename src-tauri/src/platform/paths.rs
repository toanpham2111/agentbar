use std::{env, path::PathBuf};

pub fn home_dir() -> Option<PathBuf> {
    env::var_os(if cfg!(windows) { "USERPROFILE" } else { "HOME" }).map(PathBuf::from)
}

pub fn config_dir() -> Option<PathBuf> {
    if cfg!(windows) {
        env::var_os("APPDATA").map(PathBuf::from)
    } else if cfg!(target_os = "macos") {
        home_dir().map(|home| home.join("Library/Application Support"))
    } else {
        env::var_os("XDG_CONFIG_HOME")
            .map(PathBuf::from)
            .or_else(|| home_dir().map(|home| home.join(".config")))
    }
}

pub fn data_dir() -> Option<PathBuf> {
    if cfg!(windows) {
        env::var_os("LOCALAPPDATA").map(PathBuf::from)
    } else if cfg!(target_os = "macos") {
        config_dir()
    } else {
        env::var_os("XDG_DATA_HOME")
            .map(PathBuf::from)
            .or_else(|| home_dir().map(|home| home.join(".local/share")))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn platform_paths_follow_the_current_environment() {
        let home = home_dir().expect("the test environment should expose a home directory");
        let config = config_dir().expect("the test environment should expose a config directory");
        let data = data_dir().expect("the test environment should expose a data directory");

        assert!(home.is_absolute());
        assert!(config.is_absolute());
        assert!(data.is_absolute());

        #[cfg(not(windows))]
        {
            assert!(config.starts_with(&home) || env::var_os("XDG_CONFIG_HOME").is_some());
            assert!(data.starts_with(&home) || env::var_os("XDG_DATA_HOME").is_some());
        }
    }
}
