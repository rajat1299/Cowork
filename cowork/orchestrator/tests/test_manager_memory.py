from app.runtime.manager import get_or_create, remove


def test_remembered_approvals_restore_after_remove_for_same_project() -> None:
    project_id = "proj-manager-memory-restore"
    remove(project_id)

    lock = get_or_create(project_id)
    lock.remembered_approvals.add("terminal_command")
    remove(project_id)

    restored = get_or_create(project_id)
    assert "terminal_command" in restored.remembered_approvals
    remove(project_id)


def test_remembered_approvals_snapshot_updates_when_next_lock_clears_memory() -> None:
    project_id = "proj-manager-memory-clear"
    remove(project_id)

    first = get_or_create(project_id)
    first.remembered_approvals.add("file_write")
    remove(project_id)

    second = get_or_create(project_id)
    assert "file_write" in second.remembered_approvals
    second.remembered_approvals.clear()
    remove(project_id)

    third = get_or_create(project_id)
    assert third.remembered_approvals == set()
    remove(project_id)
