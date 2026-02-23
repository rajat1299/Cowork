import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { HistoryTask } from '../api/coreApi'
import { history } from '../api/coreApi'
import { useChatStore } from './chatStore'
import { useSessionStore } from './sessionStore'

vi.mock('../api/coreApi', () => ({
  history: {
    list: vi.fn(),
    delete: vi.fn(),
  },
}))

function makeHistoryTask(overrides: Partial<HistoryTask>): HistoryTask {
  const now = new Date().toISOString()
  return {
    id: 1,
    task_id: 'task-1',
    project_id: 'project-1',
    question: 'Question',
    tokens: 0,
    status: 2,
    created_at: now,
    updated_at: now,
    ...overrides,
  }
}

describe('sessionStore task identity and recents merge', () => {
  beforeEach(() => {
    localStorage.clear()
    useChatStore.getState().clearTasks()
    useSessionStore.setState({
      sessions: [],
      isLoading: false,
      error: null,
      hasMore: true,
      page: 1,
    })
    vi.mocked(history.list).mockReset()
    vi.mocked(history.delete).mockReset()
  })

  it('dedupes local and remote recents by task id', async () => {
    const chatStore = useChatStore.getState()
    const taskId = chatStore.createTask('project-1', 'Create password generator')
    chatStore.setTaskStatus(taskId, 'running')

    vi.mocked(history.list).mockResolvedValue([
      makeHistoryTask({
        id: 10,
        task_id: taskId,
        project_id: 'project-1',
        question: 'Create password generator',
        status: 2,
      }),
    ])

    await useSessionStore.getState().fetchSessions()
    const sessions = useSessionStore.getState().sessions

    expect(sessions).toHaveLength(1)
    expect(sessions[0].taskId).toBe(taskId)
    expect(sessions[0].id).toBe(taskId)
    expect(sessions[0].status).toBe('ongoing')
  })

  it('keeps recents at task granularity instead of grouped project rows', async () => {
    vi.mocked(history.list).mockResolvedValue([
      makeHistoryTask({
        id: 21,
        task_id: 'task-a',
        project_id: 'project-shared',
        question: 'First task',
      }),
      makeHistoryTask({
        id: 22,
        task_id: 'task-b',
        project_id: 'project-shared',
        question: 'Second task',
      }),
    ])

    await useSessionStore.getState().fetchSessions()
    const sessions = useSessionStore.getState().sessions

    expect(sessions).toHaveLength(2)
    expect(sessions.map((item) => item.taskId).sort()).toEqual(['task-a', 'task-b'])
    expect(new Set(sessions.map((item) => item.projectId))).toEqual(new Set(['project-shared']))
  })
})
