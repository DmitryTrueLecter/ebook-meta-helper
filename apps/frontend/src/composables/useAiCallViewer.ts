import { ref } from 'vue'

import {
  getActiveAiConfig,
  getAiCallDetail,
  listFileAiCalls,
} from '@/services/api'
import type { AICallDetail, AICallSummary, AIConfigVersionView } from '@/types'

// Lazy loaders for the file-detail AI panels: the call list, a selected call's
// full detail, and the active config. Each section fetches on first reveal.
export function useAiCallViewer(fileId: number) {
  const calls = ref<AICallSummary[]>([])
  const loadingCalls = ref(false)
  const callsError = ref<string | null>(null)

  const selectedCallId = ref<number | null>(null)
  const callDetail = ref<AICallDetail | null>(null)
  const loadingCallDetail = ref(false)
  const callDetailError = ref<string | null>(null)

  const activeConfig = ref<AIConfigVersionView | null>(null)
  const loadingConfig = ref(false)
  const configError = ref<string | null>(null)

  async function loadCalls(): Promise<void> {
    loadingCalls.value = true
    callsError.value = null
    try {
      calls.value = await listFileAiCalls(fileId)
    } catch (err) {
      callsError.value = err instanceof Error ? err.message : String(err)
    } finally {
      loadingCalls.value = false
    }
  }

  async function selectCall(callId: number): Promise<void> {
    selectedCallId.value = callId
    loadingCallDetail.value = true
    callDetailError.value = null
    try {
      callDetail.value = await getAiCallDetail(callId)
    } catch (err) {
      callDetailError.value = err instanceof Error ? err.message : String(err)
      callDetail.value = null
    } finally {
      loadingCallDetail.value = false
    }
  }

  async function loadConfig(): Promise<void> {
    loadingConfig.value = true
    configError.value = null
    try {
      activeConfig.value = await getActiveAiConfig()
    } catch (err) {
      configError.value = err instanceof Error ? err.message : String(err)
    } finally {
      loadingConfig.value = false
    }
  }

  return {
    calls,
    loadingCalls,
    callsError,
    loadCalls,
    selectedCallId,
    callDetail,
    loadingCallDetail,
    callDetailError,
    selectCall,
    activeConfig,
    loadingConfig,
    configError,
    loadConfig,
  }
}
