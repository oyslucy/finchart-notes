import type { Session } from '@supabase/supabase-js'
import { useEffect, useState } from 'react'

import { supabase } from '../../lib/supabase.ts'

export type SessionState = { status: 'loading' } | { status: 'ready'; session: Session | null }

export function useSession(): SessionState {
  const [state, setState] = useState<SessionState>({ status: 'loading' })

  useEffect(() => {
    void supabase.auth.getSession().then(({ data }) => {
      setState({ status: 'ready', session: data.session })
    })
    const { data } = supabase.auth.onAuthStateChange((_event, session) => {
      setState({ status: 'ready', session })
    })
    return () => {
      data.subscription.unsubscribe()
    }
  }, [])

  return state
}
