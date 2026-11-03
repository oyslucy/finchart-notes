import { useId, type ComponentProps, type ReactNode } from 'react'

import { cx } from '../../design/cx.ts'

const control =
  'w-full rounded-md border border-border bg-surface px-3 text-[14px] text-text ' +
  'placeholder:text-text-faint transition-[border-color,box-shadow] duration-150 ease-out ' +
  'hover:border-border-strong focus:border-accent focus:shadow-[0_0_0_3px_var(--focus-ring)] focus:outline-none ' +
  'aria-[invalid=true]:border-danger disabled:cursor-not-allowed disabled:bg-bg-subtle disabled:text-text-faint'

interface FieldChrome {
  label?: ReactNode
  hint?: ReactNode
  error?: ReactNode
}

function FieldFrame({
  id,
  label,
  hint,
  error,
  children,
}: FieldChrome & { id: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-1.5">
      {label && (
        <label htmlFor={id} className="text-[13px] font-medium text-text-secondary">
          {label}
        </label>
      )}
      {children}
      {error ? (
        <p id={`${id}-msg`} className="text-[12px] text-danger">
          {error}
        </p>
      ) : (
        hint && (
          <p id={`${id}-msg`} className="text-[12px] text-text-muted">
            {hint}
          </p>
        )
      )}
    </div>
  )
}

export type InputProps = ComponentProps<'input'> & FieldChrome

export function Input({ label, hint, error, id, className, ...props }: InputProps) {
  const autoId = useId()
  const fieldId = id ?? autoId
  return (
    <FieldFrame id={fieldId} label={label} hint={hint} error={error}>
      <input
        id={fieldId}
        aria-invalid={error ? true : undefined}
        aria-describedby={hint || error ? `${fieldId}-msg` : undefined}
        className={cx(control, 'h-9', className)}
        {...props}
      />
    </FieldFrame>
  )
}

export type TextareaProps = ComponentProps<'textarea'> & FieldChrome

export function Textarea({ label, hint, error, id, className, rows = 4, ...props }: TextareaProps) {
  const autoId = useId()
  const fieldId = id ?? autoId
  return (
    <FieldFrame id={fieldId} label={label} hint={hint} error={error}>
      <textarea
        id={fieldId}
        rows={rows}
        aria-invalid={error ? true : undefined}
        aria-describedby={hint || error ? `${fieldId}-msg` : undefined}
        className={cx(control, 'resize-y py-2 leading-[1.6]', className)}
        {...props}
      />
    </FieldFrame>
  )
}
