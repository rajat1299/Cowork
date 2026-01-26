from __future__ import annotations

import json
import os
import shutil
import subprocess
import threading
import time
from importlib import metadata, util
from pathlib import Path
from typing import Any, Iterator

_INSTALL_THREAD: threading.Thread | None = None
_INSTALL_MUTEX = threading.Lock()


def _deps_root() -> Path:
    root = os.environ.get("COWORK_DEPS_DIR")
    if root:
        return Path(root).expanduser()
    return Path.home() / ".cowork" / "deps"


def _status_path() -> Path:
    return _deps_root() / "status.json"


def _log_path() -> Path:
    return _deps_root() / "install.log"


def _lock_path() -> Path:
    return _deps_root() / "install.lock"


def _now() -> float:
    return time.time()


def _package_version() -> str:
    try:
        return metadata.version("cowork-orchestrator")
    except metadata.PackageNotFoundError:
        return "0.1.0"


def _default_status() -> dict[str, Any]:
    return {
        "state": "idle",
        "progress": 0,
        "message": "idle",
        "error": None,
        "started_at": None,
        "finished_at": None,
        "version": _package_version(),
    }


def _read_status() -> dict[str, Any]:
    path = _status_path()
    if not path.exists():
        return _default_status()
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except json.JSONDecodeError:
        return _default_status()
    if not isinstance(data, dict):
        return _default_status()
    merged = _default_status()
    merged.update(data)
    return merged


def _write_status(data: dict[str, Any]) -> None:
    path = _status_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, sort_keys=True)


def _append_log(kind: str, message: str) -> None:
    log_path = _log_path()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    line = f"{timestamp} [{kind}] {message}"
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(line.rstrip() + "\n")


def _module_available(module_name: str) -> bool:
    return util.find_spec(module_name) is not None


def _resolve_hybrid_browser_ts_dir() -> Path | None:
    try:
        import camel
    except Exception:
        return None
    camel_path = Path(camel.__file__).resolve().parent
    ts_dir = camel_path / "toolkits" / "hybrid_browser_toolkit" / "ts"
    if ts_dir.exists():
        return ts_dir
    return None


def _marker_matches_version(marker_path: Path, version: str) -> bool:
    if not marker_path.exists():
        return False
    try:
        payload = json.loads(marker_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    return payload.get("version") == version


def _node_available() -> bool:
    return shutil.which("node") is not None


def _npm_available() -> bool:
    return shutil.which("npm") is not None


def _npx_available() -> bool:
    return shutil.which("npx") is not None


def _playwright_available() -> bool:
    return _module_available("playwright")


def _playwright_marker(ts_dir: Path | None) -> Path:
    if ts_dir is None:
        return _deps_root() / ".playwright_installed"
    return ts_dir / ".playwright_installed"


def check_dependencies() -> dict[str, Any]:
    version = _package_version()
    ts_dir = _resolve_hybrid_browser_ts_dir()
    marker_path = (ts_dir / ".npm_dependencies_installed") if ts_dir else None
    npm_installed = False
    if ts_dir:
        npm_installed = (ts_dir / "node_modules").exists() and (ts_dir / "dist").exists()
        if marker_path and _marker_matches_version(marker_path, version):
            npm_installed = npm_installed and True
    playwright_marker = _playwright_marker(ts_dir)
    playwright_installed = playwright_marker.exists()
    checks = {
        "node": _node_available(),
        "npm": _npm_available(),
        "npx": _npx_available(),
        "playwright_python": _playwright_available(),
        "hybrid_browser_ts_dir": str(ts_dir) if ts_dir else None,
        "hybrid_browser_npm": npm_installed,
        "playwright_browsers": playwright_installed,
    }
    missing = [key for key, ok in checks.items() if key.endswith(("_dir",)) is False and not ok]
    ready = checks["hybrid_browser_npm"] and checks["playwright_browsers"]
    return {"checks": checks, "missing": missing, "ready": ready}


def _install_enabled() -> bool:
    env_flag = os.environ.get("COWORK_DEPS_API_ENABLED")
    if env_flag is not None:
        return env_flag.lower() in {"1", "true", "yes"}
    return os.environ.get("APP_ENV", "development") != "production"


def deps_enabled() -> bool:
    return _install_enabled()


def _run_command(
    command: list[str],
    cwd: Path | None,
    env: dict[str, str] | None,
    label: str,
) -> bool:
    _append_log("info", f"Running: {' '.join(command)}")
    try:
        process = subprocess.Popen(
            command,
            cwd=str(cwd) if cwd else None,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
    except Exception as exc:
        _append_log("error", f"{label} failed to start: {exc}")
        return False
    assert process.stdout is not None
    for line in process.stdout:
        _append_log("stdout", line.rstrip())
    code = process.wait()
    if code != 0:
        _append_log("error", f"{label} exited with code {code}")
        return False
    _append_log("info", f"{label} completed")
    return True


def _npm_env() -> dict[str, str]:
    env = os.environ.copy()
    cache_dir = _deps_root() / ".npm-cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    env["npm_config_cache"] = str(cache_dir)
    return env


def _install_hybrid_browser_npm(ts_dir: Path, version: str) -> bool:
    marker_path = ts_dir / ".npm_dependencies_installed"
    node_modules = ts_dir / "node_modules"
    dist_dir = ts_dir / "dist"
    if node_modules.exists() and dist_dir.exists() and _marker_matches_version(marker_path, version):
        _append_log("info", "Hybrid browser npm dependencies already installed")
        return True
    if not _npm_available():
        _append_log("error", "npm not available; cannot install hybrid browser dependencies")
        return False
    if not _run_command(["npm", "install"], ts_dir, _npm_env(), "npm install"):
        return False
    if not _run_command(["npm", "run", "build"], ts_dir, _npm_env(), "npm build"):
        return False
    marker_path.write_text(
        json.dumps({"version": version, "installed_at": time.strftime("%Y-%m-%d %H:%M:%S")}),
        encoding="utf-8",
    )
    return True


def _install_playwright(ts_dir: Path | None) -> bool:
    env = os.environ.copy()
    if _npx_available():
        command = ["npx", "playwright", "install"]
        return _run_command(command, ts_dir, env, "playwright install (npx)")
    if _playwright_available():
        command = [shutil.which("python") or "python", "-m", "playwright", "install"]
        return _run_command(command, None, env, "playwright install (python)")
    _append_log("error", "Playwright not available; install playwright package first")
    return False


def _set_lock(active: bool) -> None:
    lock_path = _lock_path()
    if active:
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_path.write_text(str(os.getpid()), encoding="utf-8")
    else:
        if lock_path.exists():
            lock_path.unlink()


def _is_installing() -> bool:
    return _lock_path().exists()


def start_install(force: bool = False) -> dict[str, Any]:
    global _INSTALL_THREAD
    with _INSTALL_MUTEX:
        if _INSTALL_THREAD and _INSTALL_THREAD.is_alive():
            return get_status()
        if _is_installing() and not force:
            return get_status()
        _INSTALL_THREAD = threading.Thread(target=_run_install, args=(force,), daemon=True)
        _INSTALL_THREAD.start()
    return get_status()


def _run_install(force: bool) -> None:
    _set_lock(True)
    status = _read_status()
    status.update(
        {
            "state": "installing",
            "progress": 5,
            "message": "Starting dependency installation",
            "error": None,
            "started_at": _now(),
            "finished_at": None,
        }
    )
    _write_status(status)
    _append_log("info", "Install started")

    version = _package_version()
    checks = check_dependencies()
    if checks["ready"] and not force:
        status.update(
            {
                "state": "completed",
                "progress": 100,
                "message": "Dependencies already installed",
                "finished_at": _now(),
            }
        )
        _write_status(status)
        _append_log("info", "Dependencies already installed; skipping")
        _set_lock(False)
        return

    ts_dir = _resolve_hybrid_browser_ts_dir()
    if ts_dir is None:
        status.update(
            {
                "state": "error",
                "progress": 100,
                "message": "Hybrid browser toolkit not found",
                "error": "camel.toolkits.hybrid_browser_toolkit.ts not available",
                "finished_at": _now(),
            }
        )
        _write_status(status)
        _append_log("error", "Hybrid browser toolkit not found")
        _set_lock(False)
        return

    status.update({"progress": 30, "message": "Installing hybrid browser dependencies"})
    _write_status(status)
    if not _install_hybrid_browser_npm(ts_dir, version):
        status.update(
            {
                "state": "error",
                "progress": 100,
                "message": "Hybrid browser npm install failed",
                "error": "npm install/build failed",
                "finished_at": _now(),
            }
        )
        _write_status(status)
        _set_lock(False)
        return

    status.update({"progress": 70, "message": "Installing Playwright browsers"})
    _write_status(status)
    if not _install_playwright(ts_dir):
        status.update(
            {
                "state": "error",
                "progress": 100,
                "message": "Playwright browser install failed",
                "error": "playwright install failed",
                "finished_at": _now(),
            }
        )
        _write_status(status)
        _set_lock(False)
        return

    _playwright_marker(ts_dir).write_text("installed", encoding="utf-8")
    status.update(
        {
            "state": "completed",
            "progress": 100,
            "message": "Dependency installation complete",
            "finished_at": _now(),
        }
    )
    _write_status(status)
    _append_log("info", "Install completed")
    _set_lock(False)


def get_status(include_logs: bool = False, log_tail: int = 200) -> dict[str, Any]:
    status = _read_status()
    status["is_installing"] = _is_installing()
    checks = check_dependencies()
    status.update(checks)
    if include_logs:
        status["logs"] = tail_logs(log_tail)
    return status


def tail_logs(limit: int = 200) -> list[str]:
    path = _log_path()
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    if limit <= 0:
        return lines
    return lines[-limit:]


def stream_logs(poll_interval: float = 0.5) -> Iterator[str]:
    last_size = 0
    while True:
        path = _log_path()
        if path.exists():
            with path.open("r", encoding="utf-8") as handle:
                handle.seek(last_size)
                chunk = handle.read()
                last_size = handle.tell()
            for line in chunk.splitlines():
                payload = json.dumps({"line": line})
                yield f"data: {payload}\n\n"
        else:
            yield ":\n\n"
        time.sleep(poll_interval)


def maybe_start_auto_install() -> None:
    auto_flag = os.environ.get("COWORK_DEPS_AUTO_INSTALL")
    if auto_flag and auto_flag.lower() in {"1", "true", "yes"}:
        start_install(force=False)
