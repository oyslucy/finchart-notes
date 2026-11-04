import { cx } from '../../design/cx.ts'

/** Crop-frame corners around a rising line: "cut out the chart, then annotate it". */
export function LogoMark({ size = 18, className }: { size?: number; className?: string }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      fill="none"
      aria-hidden="true"
      className={cx('shrink-0', className)}
    >
      <path
        d="M6 12V6h6M20 6h6v6M26 20v6h-6M12 26H6v-6"
        stroke="var(--text-muted)"
        strokeWidth="2.25"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M10 20l4-4.5 3.5 3 4.5-6"
        stroke="var(--accent)"
        strokeWidth="2.25"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

export function Logo({ className }: { className?: string }) {
  return (
    <span className={cx('inline-flex items-center gap-2', className)}>
      <LogoMark />
      <span className="text-[14px] font-semibold tracking-[-0.01em] text-text">finchart-notes</span>
    </span>
  )
}
