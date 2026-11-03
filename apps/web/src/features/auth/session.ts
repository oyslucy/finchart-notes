import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api, ApiError, type Me } from '../../lib/api.ts'

export const USERNAME_PATTERN = /^[a-z0-9_]{3,20}$/
export const MIN_PASSWORD_LENGTH = 8

const meKey = ['auth', 'me'] as const

/** Resolves to the signed-in user, or null when there is no valid session. */
export function useMe() {
  return useQuery({
    queryKey: meKey,
    queryFn: async (): Promise<Me | null> => {
      try {
        return await api.me()
      } catch (error) {
        if (error instanceof ApiError && error.status === 401) return null
        throw error
      }
    },
    staleTime: Infinity,
    retry: false,
  })
}

export function useSignIn(mode: 'signin' | 'signup') {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ username, password }: { username: string; password: string }) =>
      mode === 'signin' ? api.login(username, password) : api.signup(username, password),
    onSuccess: (me) => {
      qc.setQueryData(meKey, me)
    },
  })
}

export function useSignOut() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: api.logout,
    onSettled: () => {
      // Update "me" in place so mounted observers redirect; clear() would orphan them.
      qc.setQueryData(meKey, null)
      qc.removeQueries({ predicate: (query) => query.queryKey[0] !== 'auth' })
    },
  })
}
