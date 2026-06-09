import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { useAiCallViewer } from '@/composables/useAiCallViewer'
import * as api from '@/services/api'

const FILE_ID = 7

describe('useAiCallViewer', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('loads the call list into calls', async () => {
    const summaries = [{ id: 1, file_id: FILE_ID, sequence: 1, tier: 'cheap' }]
    vi.spyOn(api, 'listFileAiCalls').mockResolvedValue(summaries as never)

    const viewer = useAiCallViewer(FILE_ID)
    await viewer.loadCalls()

    expect(api.listFileAiCalls).toHaveBeenCalledWith(FILE_ID)
    expect(viewer.calls.value).toEqual(summaries)
    expect(viewer.callsError.value).toBeNull()
  })

  it('records an error message when the call list fails', async () => {
    vi.spyOn(api, 'listFileAiCalls').mockRejectedValue(new Error('boom'))

    const viewer = useAiCallViewer(FILE_ID)
    await viewer.loadCalls()

    expect(viewer.callsError.value).toContain('boom')
    expect(viewer.calls.value).toEqual([])
  })

  it('loads a call detail and tracks the selected id', async () => {
    const detail = { id: 2, file_id: FILE_ID, sequence: 2, tier: 'expensive' }
    vi.spyOn(api, 'getAiCallDetail').mockResolvedValue(detail as never)

    const viewer = useAiCallViewer(FILE_ID)
    await viewer.selectCall(2)

    expect(api.getAiCallDetail).toHaveBeenCalledWith(2)
    expect(viewer.selectedCallId.value).toBe(2)
    expect(viewer.callDetail.value).toEqual(detail)
  })

  it('clears the call detail and records an error when detail load fails', async () => {
    vi.spyOn(api, 'getAiCallDetail').mockRejectedValue(new Error('detail down'))

    const viewer = useAiCallViewer(FILE_ID)
    await viewer.selectCall(2)

    expect(viewer.callDetail.value).toBeNull()
    expect(viewer.callDetailError.value).toContain('detail down')
  })

  it('loads the active config', async () => {
    const config = { id: 5, version: 3, is_active: true }
    vi.spyOn(api, 'getActiveAiConfig').mockResolvedValue(config as never)

    const viewer = useAiCallViewer(FILE_ID)
    await viewer.loadConfig()

    expect(viewer.activeConfig.value).toEqual(config)
    expect(viewer.configError.value).toBeNull()
  })

  it('keeps activeConfig null when there is no active config', async () => {
    vi.spyOn(api, 'getActiveAiConfig').mockResolvedValue(null)

    const viewer = useAiCallViewer(FILE_ID)
    await viewer.loadConfig()

    expect(viewer.activeConfig.value).toBeNull()
    expect(viewer.configError.value).toBeNull()
  })
})
