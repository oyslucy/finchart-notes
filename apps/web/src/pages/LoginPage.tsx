import { LogIn, UserPlus } from 'lucide-react'
import { motion } from 'motion/react'
import { useState, type SyntheticEvent } from 'react'
import { Navigate } from 'react-router'

import { Button } from '../components/ui/Button.tsx'
import { Input } from '../components/ui/Field.tsx'
import { LogoMark } from '../components/ui/Logo.tsx'
import { cx } from '../design/cx.ts'
import { appear } from '../design/motion.ts'
import {
  MIN_PASSWORD_LENGTH,
  USERNAME_PATTERN,
  useMe,
  useSignIn,
} from '../features/auth/session.ts'
import { ApiError } from '../lib/api.ts'

type Mode = 'signin' | 'signup'

function authErrorMessage(error: unknown): string {
  if (!(error instanceof ApiError)) return '알 수 없는 오류가 발생했습니다.'
  if (error.status === 401) return '아이디 또는 비밀번호가 맞지 않습니다.'
  if (error.status === 403) return '사용이 허용되지 않은 아이디입니다.'
  if (error.status === 409) return '이미 사용 중인 아이디입니다.'
  if (error.status === 429) return '시도가 너무 많습니다. 잠시 후 다시 시도해 주세요.'
  if (error.status === 422) return '아이디와 비밀번호 조건을 확인해 주세요.'
  return error.message
}

function validate(mode: Mode, username: string, password: string, confirm: string): string | null {
  if (!USERNAME_PATTERN.test(username)) return '아이디는 영문 소문자, 숫자, _ 로 3~20자입니다.'
  if (password.length < MIN_PASSWORD_LENGTH)
    return `비밀번호는 ${String(MIN_PASSWORD_LENGTH)}자 이상이어야 합니다.`
  if (mode === 'signup' && password !== confirm) return '비밀번호가 서로 다릅니다.'
  return null
}

export default function LoginPage() {
  const me = useMe()
  const [mode, setMode] = useState<Mode>('signin')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState<string | null>(null)
  const signIn = useSignIn(mode)

  if (me.data) return <Navigate to="/" replace />

  const submit = (event: SyntheticEvent) => {
    event.preventDefault()
    const name = username.trim().toLowerCase()
    const invalid = validate(mode, name, password, confirm)
    if (invalid) {
      setError(invalid)
      return
    }
    setError(null)
    signIn.mutate(
      { username: name, password },
      {
        onError: (e) => {
          setError(authErrorMessage(e))
        },
      },
    )
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
          <h1 className="flex items-center gap-2.5 text-[26px]">
            <LogoMark size={28} />
            finchart-notes
          </h1>
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

          <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
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
            <Button
              type="submit"
              variant="primary"
              icon={mode === 'signin' ? LogIn : UserPlus}
              disabled={signIn.isPending}
            >
              {signIn.isPending ? '잠시만요' : mode === 'signin' ? '로그인' : '가입하고 시작하기'}
            </Button>
          </form>
        </div>
      </motion.div>
    </main>
  )
}
