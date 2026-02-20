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
})
