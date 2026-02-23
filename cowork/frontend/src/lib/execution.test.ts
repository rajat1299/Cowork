import { describe, expect, it } from 'vitest'

import type { ProgressStep } from '../types/chat'
import { buildTurnExecutionView } from './execution'

function makeStep(
  step: ProgressStep['step'],
  data: Record<string, unknown> = {},
  status: ProgressStep['status'] = 'completed'
): ProgressStep {
  return {
    step,
    label: step,
    status,
    data,
    timestamp: Date.now(),
  }
}

describe('buildTurnExecutionView subtask finalization', () => {
  it('auto-completes unresolved subtasks when turn ends without failures', () => {
    const view = buildTurnExecutionView([
      makeStep('confirmed'),
      makeStep('to_sub_tasks', {
        sub_tasks: [
          { id: 'task-1', content: 'First task' },
          { id: 'task-2', content: 'Second task' },
        ],
      }),
      makeStep('task_state', { task_id: 'task-1', state: 'running' }),
      makeStep('end'),
    ])

    expect(view.subtasks).toEqual([
      expect.objectContaining({ id: 'task-1', status: 'completed' }),
      expect.objectContaining({ id: 'task-2', status: 'completed' }),
    ])
    expect(view.checkpoints).toEqual([
      expect.objectContaining({ id: 'task-1', status: 'completed' }),
      expect.objectContaining({ id: 'task-2', status: 'completed' }),
    ])
  })

  it('keeps failed subtasks failed when terminal errors occur', () => {
    const view = buildTurnExecutionView([
      makeStep('confirmed'),
      makeStep('to_sub_tasks', {
        sub_tasks: [
          { id: 'task-1', content: 'First task' },
          { id: 'task-2', content: 'Second task' },
        ],
      }),
      makeStep('task_state', { task_id: 'task-1', state: 'failed' }),
      makeStep('task_state', { task_id: 'task-2', state: 'running' }),
      makeStep('error', { message: 'boom' }, 'failed'),
      makeStep('end'),
    ])

    expect(view.subtasks).toEqual([
      expect.objectContaining({ id: 'task-1', status: 'failed' }),
      expect.objectContaining({ id: 'task-2', status: 'running' }),
    ])
    expect(view.checkpoints).toEqual([
      expect.objectContaining({ id: 'task-1', status: 'failed' }),
      expect.objectContaining({ id: 'task-2', status: 'active' }),
    ])
  })

  it('does not coerce unfinished subtasks when a subtask explicitly failed', () => {
    const view = buildTurnExecutionView([
      makeStep('confirmed'),
      makeStep('to_sub_tasks', {
        sub_tasks: [
          { id: 'task-1', content: 'First task' },
          { id: 'task-2', content: 'Second task' },
        ],
      }),
      makeStep('task_state', { task_id: 'task-1', state: 'failed' }),
      makeStep('task_state', { task_id: 'task-2', state: 'running' }),
      makeStep('end'),
    ])

    expect(view.subtasks).toEqual([
      expect.objectContaining({ id: 'task-1', status: 'failed' }),
      expect.objectContaining({ id: 'task-2', status: 'running' }),
    ])
  })
})
