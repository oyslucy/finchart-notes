import { LogIn, UserPlus } from 'lucide-react'
import { motion } from 'motion/react'
import { useState, type SyntheticEvent } from 'react'
import { Navigate } from 'react-router'

import { Button } from '../components/ui/Button.tsx'
import { Input } from '../components/ui/Field.tsx'
import { cx } from '../design/cx.ts'
import { appear } from '../design/motion.ts'
import { useSession } from '../features/auth/session.ts'
import {
  MIN_PASSWORD_LENGTH,
  USERNAME_PATTERN,
  normalizeUsername,
  usernameToEmail,
} from '../features/auth/username.ts'
import { supabase, supabaseConfigured } from '../lib/supabase.ts'

type Mode = 'signin' | 'signup'

function authErrorMessage(message: string): string {
  if (/invalid login credentials/i.test(message)) return '아이디 또는 비밀번호가 맞지 않습니다.'
  if (/already registered|already exists/i.test(message)) return '이미 사용 중인 아이디입니다.'
  if (/password/i.test(message)) return '비밀번호 조건을 확인해 주세요.'
  if (/rate limit|too many/i.test(message))
    return '요청이 너무 많습니다. 잠시 후 다시 시도해 주세요.'
  return message
}

function validate(mode: Mode, username: string, password: string, confirm: string): string | null {
  if (!USERNAME_PATTERN.test(username)) return '아이디는 영문 소문자, 숫자, _ 로 3~20자입니다.'
  if (password.length < MIN_PASSWORD_LENGTH)
    return `비밀번호는 ${String(MIN_PASSWORD_LENGTH)}자 이상이어야 합니다.`
  if (mode === 'signup' && password !== confirm) return '비밀번호가 서로 다릅니다.'
  return null
}

export default function LoginPage() {
  const session = useSession()
  const [mode, setMode] = useState<Mode>('signin')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  if (session.status === 'ready' && session.session) return <Navigate to="/" replace />

  const submit = async (event: SyntheticEvent) => {
    event.preventDefault()
    const name = normalizeUsername(username)
    const invalid = validate(mode, name, password, confirm)
    if (invalid) {
      setError(invalid)
      return
    }
    setBusy(true)
    setError(null)
    const credentials = { email: usernameToEmail(name), password }
    const result =
      mode === 'signin'
        ? await supabase.auth.signInWithPassword(credentials)
        : await supabase.auth.signUp({ ...credentials, options: { data: { username: name } } })
    setBusy(false)
    if (result.error) {
      setError(authErrorMessage(result.error.message))
    } else if (!result.data.session) {
      setError(
        '가입은 됐지만 바로 로그인되지 않았습니다. Supabase에서 이메일 확인 설정을 꺼 주세요.',
      )
    }
  }

  const switchMode = (next: Mode) => {
    setMode(next)
    setError(null)
    setConfirm('')
  }

  return (
    <main className="grid min-h-dvh place-items-center px-6">
      <motion.div {...appear} className="flex w-full max-w-[360px] flex-col gap-8">
        <div className="flex flex-col gap-2">
          <h1 className="text-[26px]">finchart-notes</h1>
          <p className="text-[14px] text-text-muted">
            차트 스크린샷을 올리면 메인 차트만 잘라 해설을 붙여 둡니다.
          </p>
        </div>

        <div className="flex flex-col gap-5 border-t border-border pt-6">
          <div role="tablist" aria-label="로그인 방식" className="flex gap-4 text-[14px]">
            {(
              [
                ['signin', '로그인'],
                ['signup', '회원가입'],
              ] as const
            ).map(([value, label]) => (
              <button
                key={value}
                type="button"
                role="tab"
                aria-selected={mode === value}
                onClick={() => {
                  switchMode(value)
                }}
                className={cx(
                  '-mb-px border-b pb-1.5 transition-colors duration-150',
                  mode === value
                    ? 'border-text font-medium text-text'
                    : 'border-transparent text-text-muted hover:text-text',
                )}
              >
                {label}
              </button>
            ))}
          </div>

          <form
            onSubmit={(e) => {
              void submit(e)
            }}
            className="flex flex-col gap-4"
            noValidate
          >
            <Input
              label="아이디"
              autoComplete="username"
              autoCapitalize="none"
              spellCheck={false}
              autoFocus
              required
              value={username}
              placeholder="영문 소문자, 숫자, _ 3~20자"
              onChange={(e) => {
                setUsername(e.target.value)
              }}
              disabled={!supabaseConfigured}
            />
            <Input
              label="비밀번호"
              type="password"
              autoComplete={mode === 'signin' ? 'current-password' : 'new-password'}
              required
              value={password}
              placeholder={`${String(MIN_PASSWORD_LENGTH)}자 이상`}
              onChange={(e) => {
                setPassword(e.target.value)
              }}
              disabled={!supabaseConfigured}
            />
            {mode === 'signup' && (
              <Input
                label="비밀번호 확인"
                type="password"
                autoComplete="new-password"
                required
                value={confirm}
                onChange={(e) => {
                  setConfirm(e.target.value)
                }}
              />
            )}
            {error && (
              <p role="alert" className="text-[13px] text-danger">
                {error}
              </p>
            )}
            {!supabaseConfigured && (
              <p className="text-[13px] text-text-muted">
                VITE_SUPABASE_URL이 설정되지 않았습니다.
              </p>
            )}
            <Button
              type="submit"
              variant="primary"
              icon={mode === 'signin' ? LogIn : UserPlus}
              disabled={busy || !supabaseConfigured}
            >
              {busy ? '잠시만요' : mode === 'signin' ? '로그인' : '가입하고 시작하기'}
            </Button>
          </form>
        </div>
      </motion.div>
    </main>
  )
}
