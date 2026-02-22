import { beforeEach, describe, expect, it } from 'vitest'

import { useChatStore } from './chatStore'

describe('chatStore state transitions', () => {
  beforeEach(() => {
    const store = useChatStore.getState()
    store.clearTasks()
    useChatStore.setState({ isConnecting: false })
  })

  it('creates a task and sets it active', () => {
    const store = useChatStore.getState()

    const taskId = store.createTask('project-1', 'Ship phase 3')
    const task = useChatStore.getState().tasks[taskId]

    expect(useChatStore.getState().activeProjectId).toBe('project-1')
    expect(useChatStore.getState().activeTaskId).toBe(taskId)
    expect(task.status).toBe('pending')
    expect(task.messages).toHaveLength(1)
    expect(task.messages[0].role).toBe('user')
    expect(task.messages[0].content).toBe('Ship phase 3')
  })

  it('marks task completed and records endTime', () => {
    const store = useChatStore.getState()
    const taskId = store.createTask('project-2', 'Finish tests')

    expect(useChatStore.getState().tasks[taskId].endTime).toBeUndefined()
    store.setTaskStatus(taskId, 'completed')

    const task = useChatStore.getState().tasks[taskId]
    expect(task.status).toBe('completed')
    expect(typeof task.endTime).toBe('number')
  })

  it('deduplicates artifacts by id and applies updates', () => {
    const store = useChatStore.getState()
    const taskId = store.createTask('project-3', 'Generate report')

    store.addArtifact(taskId, {
      id: 'artifact-1',
      type: 'file',
      name: 'report.md',
      contentUrl: '/files/report.md',
    })
    store.addArtifact(taskId, {
      id: 'artifact-1',
      type: 'file',
      name: 'report-v2.md',
      contentUrl: '/files/report-v2.md',
    })

    const task = useChatStore.getState().tasks[taskId]
    expect(task.artifacts).toHaveLength(1)
    expect(task.artifacts[0].name).toBe('report-v2.md')
    expect(task.artifacts[0].contentUrl).toBe('/files/report-v2.md')
  })

  it('updates activeProjectId when switching active task', () => {
    const store = useChatStore.getState()
    const firstTaskId = store.createTask('project-alpha', 'First')
    const secondTaskId = store.createTask('project-beta', 'Second')

    expect(useChatStore.getState().activeTaskId).toBe(secondTaskId)
    expect(useChatStore.getState().activeProjectId).toBe('project-beta')

    store.setActiveTask(firstTaskId)

    expect(useChatStore.getState().activeTaskId).toBe(firstTaskId)
    expect(useChatStore.getState().activeProjectId).toBe('project-alpha')
  })

  it('clears activeProjectId when removing the active task', () => {
    const store = useChatStore.getState()
    const taskId = store.createTask('project-zeta', 'Delete me')

    store.removeTask(taskId)

    expect(useChatStore.getState().activeTaskId).toBeNull()
    expect(useChatStore.getState().activeProjectId).toBeNull()
  })

  it('persists tasks and prunes stale tasks from hydrated state', () => {
    const now = Date.now()
    const oneDayMs = 24 * 60 * 60 * 1000

    const store = useChatStore.getState()
    const staleTaskId = store.createTask('project-old', 'Old task')
    const freshTaskId = store.createTask('project-new', 'Fresh task')

    const staleTask = {
      ...useChatStore.getState().tasks[staleTaskId],
      startTime: now - oneDayMs - 60_000,
    }
    const freshTask = {
      ...useChatStore.getState().tasks[freshTaskId],
      startTime: now - 60_000,
    }

    const persistOptions = useChatStore.persist.getOptions()
    const partial = persistOptions.partialize(useChatStore.getState())

    expect('tasks' in partial).toBe(true)
    expect(typeof persistOptions.merge).toBe('function')

    if (typeof persistOptions.merge === 'function') {
      const merged = persistOptions.merge(
        {
          activeProjectId: staleTask.projectId,
          activeTaskId: staleTaskId,
          tasks: {
            [staleTaskId]: staleTask,
            [freshTaskId]: freshTask,
          },
        },
        useChatStore.getState()
      )

      expect(merged.activeTaskId).toBeNull()
      expect(merged.activeProjectId).toBeNull()
      expect(Object.keys(merged.tasks)).toEqual([freshTaskId])
    }
  })
})
