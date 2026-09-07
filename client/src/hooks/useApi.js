import { useState, useEffect, useCallback, useRef } from 'react'
import { api } from '../services/api'

function useFetch(fetcher, deps = []) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const fetch = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      setData(await fetcher())
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)

  useEffect(() => { fetch() }, [fetch])
  return { data, loading, error, refetch: fetch }
}

export function useHealth() {
  return useFetch(api.getHealth)
}

export function useModelInfo() {
  return useFetch(api.getModelInfo)
}

export function useStations() {
  return useFetch(api.getStations)
}

export function useAnomalies() {
  return useFetch(api.getAnomalies)
}

export function useStationHistory(stationId) {
  return useFetch(() => api.getStationHistory(stationId), [stationId])
}

export function usePolling(fetcher, intervalMs = 60000) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [lastSync, setLastSync] = useState(null)
  const timerRef = useRef(null)

  const run = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      setData(await fetcher())
      setLastSync(new Date())
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [fetcher])

  useEffect(() => {
    run()
    timerRef.current = setInterval(run, intervalMs)
    return () => clearInterval(timerRef.current)
  }, [run, intervalMs])

  return { data, loading, error, lastSync, refetch: run }
}

export function usePredict() {
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [steps, setSteps] = useState([])

  const STEPS = [
    'Analyzing AWS observation...',
    'Evaluating temporal consistency...',
    'Checking station baseline...',
    'Evaluating multivariate consistency...',
    'Generating anomaly assessment...',
  ]

  const predict = useCallback(async (observation) => {
    setLoading(true)
    setError(null)
    setResult(null)
    setSteps([])

    let i = 0
    const interval = setInterval(() => {
      if (i < STEPS.length) setSteps(prev => [...prev, STEPS[i++]])
    }, 200)

    try {
      const data = await api.predict(observation)
      setResult(data)
    } catch (e) {
      setError(e.message)
    } finally {
      clearInterval(interval)
      setSteps(STEPS)
      setLoading(false)
    }
  }, [])

  return { result, loading, error, steps, predict }
}
