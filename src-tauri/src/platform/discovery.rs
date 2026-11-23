use std::{
    collections::HashSet,
    env, fs,
    path::{Path, PathBuf},
};

pub fn find_executable(names: &[&str]) -> Option<PathBuf> {
    let path = env::var_os("PATH")?;
    let extensions: &[&str] = if cfg!(windows) {
        &[".exe", ".cmd", ".bat", ""]
    } else {
        &[""]
    };
    for directory in env::split_paths(&path) {
        for name in names {
            for extension in extensions {
                let candidate = directory.join(format!("{name}{extension}"));
                if candidate.is_file() {
                    return Some(candidate);
                }
            }
        }
    }
    None
}

pub fn collect_files(root: &Path, file_name: &str, max_depth: usize) -> Vec<PathBuf> {
    let mut files = Vec::new();
    let mut visited = HashSet::new();
    visit(root, file_name, max_depth, &mut visited, &mut files);
    files
}

fn visit(
    root: &Path,
    file_name: &str,
    depth: usize,
    visited: &mut HashSet<PathBuf>,
    files: &mut Vec<PathBuf>,
) {
    if depth == 0 || !root.is_dir() {
        return;
    }
    let canonical = root.canonicalize().unwrap_or_else(|_| root.to_path_buf());
    if !visited.insert(canonical) {
        return;
    }
    let Ok(entries) = fs::read_dir(root) else {
        return;
    };
    for entry in entries.flatten() {
        let path = entry.path();
        if path.is_file()
            && (file_name.is_empty() || path.file_name().is_some_and(|name| name == file_name))
        {
            files.push(path);
        } else if path.is_dir() {
            visit(&path, file_name, depth - 1, visited, files);
        }
    }
}
