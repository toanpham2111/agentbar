use crate::{
    core::models::{AdapterStatus, DetectionResult, ProviderId, ProviderSnapshot},
    platform::discovery::find_executable,
};

pub fn detect(
    provider_id: ProviderId,
    display_name: &str,
    binary_names: &[&str],
) -> DetectionResult {
    let executable = find_executable(binary_names);
    let installed = executable.is_some();
    DetectionResult {
        provider_id,
        display_name: display_name.into(),
        installed,
        executable_path: executable.map(|path| path.to_string_lossy().into_owned()),
        version: None,
        status: if installed {
            AdapterStatus::PartiallySupported
        } else {
            AdapterStatus::NotInstalled
        },
    }
}

pub fn snapshot(detection: DetectionResult, limitation: &str) -> ProviderSnapshot {
    ProviderSnapshot::unsupported(detection, limitation)
}
