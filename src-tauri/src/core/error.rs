use thiserror::Error;

#[derive(Debug, Error)]
pub enum AdapterError {
    #[error("provider is not installed")]
    NotInstalled,
    #[error("permission denied while reading {path}")]
    PermissionDenied { path: String },
    #[error("provider data is unsupported: {reason}")]
    Unsupported { reason: String },
    #[error("invalid provider data in {path}: {reason}")]
    InvalidData { path: String, reason: String },
    #[error("provider collection failed: {0}")]
    Collection(String),
}

#[derive(Debug, Error)]
pub enum AppError {
    #[error(transparent)]
    Adapter(#[from] AdapterError),
    #[error("database error: {0}")]
    Database(#[from] sqlx::Error),
    #[error("database migration error: {0}")]
    Migration(#[from] sqlx::migrate::MigrateError),
    #[error("invalid input: {0}")]
    Validation(String),
    #[error("filesystem error: {0}")]
    Io(#[from] std::io::Error),
}

impl serde::Serialize for AppError {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: serde::Serializer,
    {
        serializer.serialize_str(&self.to_string())
    }
}
