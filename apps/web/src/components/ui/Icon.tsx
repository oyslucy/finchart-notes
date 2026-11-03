import type { LucideIcon } from 'lucide-react'

interface IconProps {
  icon: LucideIcon
  size?: 14 | 16 | 18 | 20
  className?: string
}

/** All icons render with a fixed 1.5px stroke regardless of size. */
export function Icon({ icon: Glyph, size = 16, className }: IconProps) {
  return (
    <Glyph
      size={size}
      strokeWidth={1.5}
      nonScalingStroke
      aria-hidden="true"
      focusable="false"
      className={className}
    />
  )
}
