/** A small candlestick chart: the content every finchart card carries. Deterministic data. */

type Candle = { o: number; c: number; h: number; l: number }

function series(seed: number, n: number, drift: number): Candle[] {
  let x = seed
  const rand = () => {
    x = (x * 16807) % 2147483647
    return x / 2147483647
  }
  let price = 100
  return Array.from({ length: n }, () => {
    const o = price
    const c = o + (rand() - 0.5 + drift) * 6
    const h = Math.max(o, c) + rand() * 2.5
    const l = Math.min(o, c) - rand() * 2.5
    price = c
    return { o, c, h, l }
  })
}

interface CandlesProps {
  width: number
  height: number
  seed?: number
  count?: number
  drift?: number
  /** Gray candles for filler cards; red/blue (Korean convention) for the subject. */
  muted?: boolean
  grid?: boolean
}

export function Candles({ width, height, seed = 7, count = 36, drift = 0.12, muted, grid = true }: CandlesProps) {
  const data = series(seed, count, drift)
  const hi = Math.max(...data.map((d) => d.h))
  const lo = Math.min(...data.map((d) => d.l))
  const pad = 4
  const y = (v: number) => pad + ((hi - v) / (hi - lo)) * (height - pad * 2)
  const step = width / count
  const up = muted ? '#c9c4bd' : '#d64545'
  const down = muted ? '#e1ddd8' : '#3f74d6'
  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} aria-hidden style={{ display: 'block' }}>
      {grid &&
        [0.25, 0.5, 0.75].map((t) => (
          <line key={t} x1={0} x2={width} y1={height * t} y2={height * t} stroke="#efedea" strokeWidth={1} />
        ))}
      {data.map((d, i) => {
        const cx = i * step + step / 2
        const color = d.c >= d.o ? up : down
        const top = y(Math.max(d.o, d.c))
        const bottom = y(Math.min(d.o, d.c))
        return (
          <g key={i}>
            <line x1={cx} x2={cx} y1={y(d.h)} y2={y(d.l)} stroke={color} strokeWidth={1} />
            <rect x={cx - step * 0.32} y={top} width={step * 0.64} height={Math.max(1, bottom - top)} fill={color} />
          </g>
        )
      })}
    </svg>
  )
}
