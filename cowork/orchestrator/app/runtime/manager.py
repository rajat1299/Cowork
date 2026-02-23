import threading

from app.runtime.task_lock import TaskLock

_locks: dict[str, TaskLock] = {}
_remembered_approvals_by_project: dict[str, set[str]] = {}
_lock = threading.Lock()


def get_or_create(project_id: str) -> TaskLock:
    with _lock:
        if project_id not in _locks:
            remembered = set(_remembered_approvals_by_project.get(project_id, set()))
            _locks[project_id] = TaskLock(
                project_id=project_id,
                remembered_approvals=remembered,
            )
        return _locks[project_id]


def get(project_id: str) -> TaskLock | None:
    return _locks.get(project_id)


def remove(project_id: str) -> None:
    with _lock:
        lock = _locks.pop(project_id, None)
        if not lock:
            return
        if lock.remembered_approvals:
            _remembered_approvals_by_project[project_id] = set(lock.remembered_approvals)
        else:
            _remembered_approvals_by_project.pop(project_id, None)
