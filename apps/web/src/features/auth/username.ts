/**
 * Supabase password auth is keyed by email, so a username maps to an address on our own
 * domain. No mail is ever sent there; it only has to be unique and well-formed.
 */
export const USERNAME_EMAIL_DOMAIN = 'users.finchart-notes.duckdns.org'

export const USERNAME_PATTERN = /^[a-z0-9_]{3,20}$/
export const MIN_PASSWORD_LENGTH = 8

export function normalizeUsername(raw: string): string {
  return raw.trim().toLowerCase()
}

export function usernameToEmail(username: string): string {
  return `${normalizeUsername(username)}@${USERNAME_EMAIL_DOMAIN}`
}

export function usernameFromEmail(email: string | undefined): string {
  if (!email) return ''
  const [local, domain] = email.split('@')
  return domain === USERNAME_EMAIL_DOMAIN ? (local ?? email) : email
}
