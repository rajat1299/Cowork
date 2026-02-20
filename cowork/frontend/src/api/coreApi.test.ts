import { beforeEach, describe, expect, it, vi } from 'vitest'

const clientMocks = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  put: vi.fn(),
  del: vi.fn(),
  upload: vi.fn(),
}))

vi.mock('./client', () => ({
  CORE_API_URL: 'http://localhost:3001',
  coreApi: {
    get: clientMocks.get,
    post: clientMocks.post,
    put: clientMocks.put,
    delete: clientMocks.del,
    upload: clientMocks.upload,
  },
}))

import { history } from './coreApi'

describe('history api contract', () => {
  beforeEach(() => {
    clientMocks.get.mockReset()
    clientMocks.del.mockReset()
  })

  it('builds grouped history endpoint with include_tasks flag', async () => {
    clientMocks.get.mockResolvedValue({ projects: [], total_projects: 0, total_tasks: 0, total_tokens: 0 })

    await history.listGrouped(false)

    expect(clientMocks.get).toHaveBeenCalledWith('/chat/histories/grouped?include_tasks=false')
  })

  it('builds list query params for pagination and project filtering', async () => {
    clientMocks.get.mockResolvedValue([])

    await history.list(20, 40, 'project-123')

    expect(clientMocks.get).toHaveBeenCalledWith(
      '/chat/histories?limit=20&offset=40&project_id=project-123'
    )
  })

  it('uses flat history endpoint when no list params are supplied', async () => {
    clientMocks.get.mockResolvedValue([])

    await history.list()

    expect(clientMocks.get).toHaveBeenCalledWith('/chat/histories')
  })
})
