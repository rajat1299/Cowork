import threading

from app.runtime.task_lock import TaskLock

_locks: dict[str, TaskLock] = {}
_lock = threading.Lock()


def get_or_create(project_id: str) -> TaskLock:
    with _lock:
        if project_id not in _locks:
            _locks[project_id] = TaskLock(project_id=project_id)
        return _locks[project_id]


def get(project_id: str) -> TaskLock | None:
    return _locks.get(project_id)


def remove(project_id: str) -> None:
    with _lock:
        _locks.pop(project_id, None)
