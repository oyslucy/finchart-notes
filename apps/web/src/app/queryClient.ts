import { MutationCache, QueryCache, QueryClient } from '@tanstack/react-query'

import { ApiError } from '../lib/api.ts'

// An expired session surfaces as 401 on any call; dropping "me" sends the user to /login.
function onAuthError(error: Error) {
  if (error instanceof ApiError && error.status === 401) {
    queryClient.setQueryData(['auth', 'me'], null)
  }
}

export const queryClient: QueryClient = new QueryClient({
  queryCache: new QueryCache({ onError: onAuthError }),
  mutationCache: new MutationCache({ onError: onAuthError }),
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: (count, error) => !(error instanceof ApiError && error.status < 500) && count < 1,
      refetchOnWindowFocus: false,
    },
  },
})
