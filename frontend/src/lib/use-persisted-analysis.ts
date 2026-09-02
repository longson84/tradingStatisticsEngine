import { useCallback, useEffect, useState } from "react"
import { useMutation } from "@tanstack/react-query"

const CACHE_PREFIX = "tse.analysis-result."
const CACHE_VERSION = 1
const CACHE_MAX_AGE_MS = 12 * 60 * 60 * 1000

interface CacheEnvelope<TData> {
  version: number
  savedAt: number
  data: TData
}

export function usePersistedAnalysis<TData, TVariables>({
  storageKey,
  mutationFn,
}: {
  storageKey: string
  mutationFn: (variables: TVariables) => Promise<TData>
}) {
  const fullKey = `${CACHE_PREFIX}${storageKey}`
  const [cachedData, setCachedData] = useState<TData | undefined>(() => readCache(fullKey))
  const mutation = useMutation<TData, Error, TVariables>({ mutationFn })

  useEffect(() => {
    if (mutation.data === undefined) return
    setCachedData(mutation.data)
    writeCache(fullKey, mutation.data)
  }, [fullKey, mutation.data])

  const reset = useCallback(() => {
    mutation.reset()
    setCachedData(undefined)
    window.sessionStorage.removeItem(fullKey)
  }, [fullKey, mutation])

  return {
    ...mutation,
    data: mutation.data ?? cachedData,
    reset,
  }
}

function readCache<TData>(key: string): TData | undefined {
  try {
    const value = window.sessionStorage.getItem(key)
    if (!value) return undefined
    const envelope = JSON.parse(value) as CacheEnvelope<TData>
    if (
      envelope.version !== CACHE_VERSION
      || Date.now() - envelope.savedAt > CACHE_MAX_AGE_MS
    ) {
      window.sessionStorage.removeItem(key)
      return undefined
    }
    return envelope.data
  } catch {
    window.sessionStorage.removeItem(key)
    return undefined
  }
}

function writeCache<TData>(key: string, data: TData): void {
  try {
    const envelope: CacheEnvelope<TData> = {
      version: CACHE_VERSION,
      savedAt: Date.now(),
      data,
    }
    window.sessionStorage.setItem(key, JSON.stringify(envelope))
  } catch {
    // Analysis still succeeds when browser storage is unavailable or full.
  }
}
