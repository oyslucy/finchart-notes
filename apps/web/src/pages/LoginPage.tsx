import { Mail } from 'lucide-react'
import { motion } from 'motion/react'
import { useState, type SyntheticEvent } from 'react'
import { Navigate } from 'react-router'

import { Button } from '../components/ui/Button.tsx'
import { Input } from '../components/ui/Field.tsx'
import { appear } from '../design/motion.ts'
import { useSession } from '../features/auth/session.ts'
import { supabase, supabaseConfigured } from '../lib/supabase.ts'

type Status =
  | { kind: 'idle' }
  | { kind: 'sending' }
  | { kind: 'sent'; email: string }
  | { kind: 'error'; message: string }

export default function LoginPage() {
  const session = useSession()
  const [email, setEmail] = useState('')
  const [status, setStatus] = useState<Status>({ kind: 'idle' })

  if (session.status === 'ready' && session.session) return <Navigate to="/" replace />

  const submit = async (event: SyntheticEvent) => {
    event.preventDefault()
    setStatus({ kind: 'sending' })
    const { error } = await supabase.auth.signInWithOtp({
      email,
      options: { emailRedirectTo: window.location.origin },
    })
    setStatus(error ? { kind: 'error', message: error.message } : { kind: 'sent', email })
  }

  return (
    <main className="grid min-h-dvh place-items-center px-6">
      <motion.div {...appear} className="flex w-full max-w-[360px] flex-col gap-8">
        <div className="flex flex-col gap-2">
          <h1 className="text-[26px]">finchart-notes</h1>
          <p className="text-[14px] text-text-muted">
            차트 스크린샷을 올리면 메인 차트만 잘라 해설을 붙여 둔다.
          </p>
        </div>

        {status.kind === 'sent' ? (
          <div className="flex flex-col gap-1.5 border-t border-border pt-6">
            <p className="font-medium">메일을 확인해 주세요</p>
            <p className="text-[14px] text-text-muted">
              <span className="text-text">{status.email}</span>로 보낸 로그인 링크를 누르면 바로
              들어온다.
            </p>
          </div>
        ) : (
          <form
            onSubmit={(e) => {
              void submit(e)
            }}
            className="flex flex-col gap-4 border-t border-border pt-6"
          >
            <Input
              label="이메일"
              type="email"
              autoComplete="email"
              required
              autoFocus
              value={email}
              onChange={(e) => {
                setEmail(e.target.value)
              }}
              placeholder="you@example.com"
              error={status.kind === 'error' ? status.message : undefined}
              disabled={!supabaseConfigured}
              hint={supabaseConfigured ? undefined : 'VITE_SUPABASE_URL이 설정되지 않았다.'}
            />
            <Button
              type="submit"
              variant="primary"
              icon={Mail}
              disabled={status.kind === 'sending' || !supabaseConfigured}
            >
              {status.kind === 'sending' ? '보내는 중' : '로그인 링크 받기'}
            </Button>
          </form>
        )}
      </motion.div>
    </main>
  )
}
