import { useCallback, useSyncExternalStore } from 'react'

export type ThemePreference = 'light' | 'dark' | 'system'

const STORAGE_KEY = 'finchart-theme'
const media = () => window.matchMedia('(prefers-color-scheme: dark)')
const listeners = new Set<() => void>()

function readPreference(): ThemePreference {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored === 'light' || stored === 'dark') return stored
  } catch {
    // Storage can be unavailable (private mode); fall back to the system theme.
  }
  return 'system'
}

export function applyTheme(preference: ThemePreference = readPreference()): void {
  const dark = preference === 'dark' || (preference === 'system' && media().matches)
  document.documentElement.dataset.theme = dark ? 'dark' : 'light'
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener)
  const onSystemChange = () => {
    applyTheme()
    listener()
  }
  media().addEventListener('change', onSystemChange)
  return () => {
    listeners.delete(listener)
    media().removeEventListener('change', onSystemChange)
  }
}

export function useTheme(): [ThemePreference, (next: ThemePreference) => void] {
  const preference = useSyncExternalStore(subscribe, readPreference, () => 'system' as const)
  const setPreference = useCallback((next: ThemePreference) => {
    try {
      if (next === 'system') localStorage.removeItem(STORAGE_KEY)
      else localStorage.setItem(STORAGE_KEY, next)
    } catch {
      // Ignore; the theme still applies for this session.
    }
    applyTheme(next)
    listeners.forEach((l) => {
      l()
    })
  }, [])
  return [preference, setPreference]
}
