import { createClient } from '@supabase/supabase-js'

const url = import.meta.env.VITE_SUPABASE_URL
const anonKey = import.meta.env.VITE_SUPABASE_ANON_KEY

export const supabaseConfigured = Boolean(url && anonKey)

// The client is only used for auth; data goes through our API so the server can analyze images.
export const supabase = createClient(url || 'http://localhost', anonKey || 'missing', {
  auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: true },
})
