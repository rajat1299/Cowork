import { describe, expect, it } from 'vitest'

import { chooseFollowUpRoute, chooseSendProjectId } from './useChat'

describe('useChat routing helpers', () => {
  it('reuses the active project id for a new send when available', () => {
    const projectId = chooseSendProjectId({
      explicitProjectId: undefined,
      activeProjectId: 'project-existing',
      createId: () => 'project-generated',
    })

    expect(projectId).toBe('project-existing')
  })

  it('prefers an explicit project id when provided', () => {
    const projectId = chooseSendProjectId({
      explicitProjectId: 'project-explicit',
      activeProjectId: 'project-existing',
      createId: () => 'project-generated',
    })

    expect(projectId).toBe('project-explicit')
  })

  it('creates a new project id only when no project context exists', () => {
    const projectId = chooseSendProjectId({
      explicitProjectId: undefined,
      activeProjectId: null,
      createId: () => 'project-generated',
    })

    expect(projectId).toBe('project-generated')
  })

  it('routes follow-up to same-project new task when task id is missing', () => {
    const route = chooseFollowUpRoute({
      activeProjectId: 'project-existing',
      activeTaskId: null,
    })

    expect(route).toBe('reuse_project_new_task')
  })

  it('routes follow-up as existing task when both project and task are present', () => {
    const route = chooseFollowUpRoute({
      activeProjectId: 'project-existing',
      activeTaskId: 'task-existing',
    })

    expect(route).toBe('existing_task')
  })

  it('routes follow-up to new chat when no project exists', () => {
    const route = chooseFollowUpRoute({
      activeProjectId: null,
      activeTaskId: null,
    })

    expect(route).toBe('new_chat')
  })
})
