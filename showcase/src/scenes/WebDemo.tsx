import { useLayoutEffect, useRef, type ReactNode } from 'react'
import { ImageUp } from 'lucide-react'

import { Bar, Spinner, Stage, States, Window, type Act, type Point } from '../../kit'
import { Candles } from './Candles'
import './web.css'

// finchart-notes, web. Corner bleed (from the Upload gold): a screenshot sits on
// the desktop beside the app. It is dragged onto the upload bar, which lights up;
// on the drop a new card takes the first slot of the grid and the other cards
// make room. The card first shows the whole screenshot, then a crop frame finds
// the main chart and the card zooms to it, and the analysis lands as its title.
// Cmd+Z takes the card back, which is where the loop began.
//
// Real words: the address, the upload hint, three boards, the file name, and the
// new card's title and meta. Every other card is filler.

type Ghost = { on: boolean; dropped: boolean; off: Point; at: Point }
type Crop = 'none' | 'frame' | 'zoom'
type S = { added: boolean; crop: Crop; done: boolean; ghost: Ghost }

const GHOST: Ghost = { on: false, dropped: false, off: { x: 0, y: 0 }, at: { x: 0, y: 0 } }
const initial: S = { added: false, crop: 'none', done: false, ghost: GHOST }
const poster: S = { added: true, crop: 'zoom', done: true, ghost: GHOST }

const FILE = 'KOSPI.png'
const COL = 190
const GAP = 14
const GRID_TOP = 128
const ROW = 198
const FILLERS = [
  { seed: 11, title: 104, meta: 72 },
  { seed: 23, title: 88, meta: 64 },
  { seed: 5, title: 116, meta: 58 },
  { seed: 41, title: 96, meta: 70 },
  { seed: 17, title: 110, meta: 66 },
]

function slot(k: number) {
  return { left: 20 + (k % 3) * (COL + GAP), top: GRID_TOP + Math.floor(k / 3) * ROW }
}

async function script(a: Act<S>) {
  await a.wait(700)

  // 1. Pick the screenshot up off the desktop
  a.mark('grab')
  const icon = a.rect('desk-icon')
  const file = a.rect('desk-file')
  const grab = { x: icon.x + icon.width / 2, y: icon.y + icon.height * 0.55 }
  await a.move(grab)
  await a.wait(220)
  const off = { x: grab.x - file.x, y: grab.y - file.y }

  // 2. Carry it onto the upload bar; the bar lights up under it
  a.mark('drag')
  const drop = a.rect('drop')
  await a.drag(
    { x: drop.x + drop.width * 0.42, y: drop.y + drop.height * 0.34 },
    (at) => {
      a.put({ ghost: { on: true, dropped: false, off, at } })
    },
    { duration: 1300, cursor: 'preserve' },
  )

  // 3. Drop: a card takes the first slot, showing the whole screenshot
  a.mark('drop')
  await a.set((s) => ({ added: true, ghost: { ...s.ghost, dropped: true } }))
  await a.wait(900)

  // 4. A frame finds the main chart, then the card zooms to it
  a.mark('crop')
  await a.set({ crop: 'frame' })
  await a.wait(1000)
  await a.set({ crop: 'zoom' })
  await a.wait(800)

  // 5. The analysis lands as the card's title
  a.mark('done')
  await a.set({ done: true })
  await a.wait(2800)

  // 6. Cmd+Z takes the card back: the start
  a.mark('undo')
  await a.key('cmd+z')
  await a.set({ added: false, ghost: GHOST })
  await a.wait(700)
  await a.snap({ crop: 'none', done: false })
  await a.wait(300)
}

export default function WebDemo() {
  return (
    <Stage<S>
      width={760}
      height={440}
      initial={initial}
      poster={poster}
      script={script}
      accent="#7266d6"
      keys="bottom-left"
      cursor={{ at: { at: 'drop', x: 0.42, y: 0.34 } }}
      className="wd"
    >
      {(s) => {
        const lifted = s.ghost.on && !s.ghost.dropped
        return (
          <>
            <div className="wd-desk" data-target="desk-file" data-lifted={lifted || undefined}>
              <span className="wd-desk__icon" data-target="desk-icon">
                <Screenshot scale={0.17} />
              </span>
              <span className="wd-desk__name">{FILE}</span>
            </div>

            <Window url="finchart-notes.duckdns.org" className="wd-window" body={{ className: 'wd-body', 'data-crop': true }}>
              <div className="wd-composer" data-target="drop" data-drop>
                <div className="wd-composer__top">
                  <ImageUp size={18} strokeWidth={1.5} className="wd-composer__icon" />
                  <span className="wd-composer__hint">스크린샷을 끌어다 놓으세요</span>
                  <Bar w={52} h={7} tone={2} style={{ marginLeft: 'auto' }} />
                </div>
                <div className="wd-chips">
                  <span className="wd-chip" data-on>
                    반도체
                  </span>
                  <span className="wd-chip">IT</span>
                  <span className="wd-chip">2차전지</span>
                </div>
              </div>

              <Bar w={56} h={7} tone={2} className="wd-label" />

              {FILLERS.map((f, i) => (
                <div key={i} className="wd-card" style={slot(i + (s.added ? 1 : 0))}>
                  <div className="wd-thumb">
                    <Candles width={COL - 20} height={110} seed={f.seed} muted />
                  </div>
                  <div className="wd-text">
                    <Bar w={f.title} h={7} tone={3} />
                    <Bar w={f.meta} h={6} tone={2} />
                  </div>
                </div>
              ))}

              <div className="wd-card wd-new" data-show={s.added || undefined} style={slot(0)}>
                <div className="wd-thumb wd-thumb--shot" data-crop>
                  <div className="wd-shot" data-crop={s.crop}>
                    <Screenshot scale={1} />
                  </div>
                  <span className="wd-frame" data-crop={s.crop} />
                </div>
                <div className="wd-text">
                  <States
                    value={s.done ? 'done' : 'pending'}
                    align="start"
                    states={{
                      pending: (
                        <span className="wd-pending">
                          <Spinner size={12} />
                          분석 중…
                        </span>
                      ),
                      done: <span className="wd-title">KOSPI 일봉</span>,
                    }}
                  />
                  <States
                    value={s.done ? 'done' : 'pending'}
                    align="start"
                    states={{
                      pending: <Bar w={84} h={6} tone={2} />,
                      done: <span className="wd-meta">캔들스틱 · 2026.05–10</span>,
                    }}
                  />
                </div>
              </div>
            </Window>

            <DragImage ghost={s.ghost}>
              <span className="wd-desk__icon">
                <Screenshot scale={0.17} />
              </span>
              <span className="wd-drag__name">{FILE}</span>
            </DragImage>
          </>
        )
      }}
    </Stage>
  )
}

/**
 * The captured page: a news site with a nav, an article column, the main chart
 * and an ad. Drawn at 380 × 260 and scaled; the chart panel is at (110, 40, 190, 160).
 */
function Screenshot({ scale }: { scale: number }) {
  return (
    <div className="wd-page" style={{ transform: `scale(${String(scale)})` }}>
      <div className="wd-page__nav" />
      <div className="wd-page__article">
        {[86, 70, 92, 64, 80, 74, 88, 60].map((w, i) => (
          <i key={i} style={{ width: w }} />
        ))}
      </div>
      <div className="wd-page__chart">
        <i className="wd-page__chart-title" />
        <Candles width={170} height={118} seed={7} count={30} />
      </div>
      <div className="wd-page__ad" />
      <div className="wd-page__mini">
        <Candles width={52} height={34} seed={29} count={14} muted grid={false} />
      </div>
    </div>
  )
}

/** From the Upload gold: the drag image rides the cursor and lights any [data-drop] under it. */
function DragImage({ ghost, children }: { ghost: Ghost; children: ReactNode }) {
  const ref = useRef<HTMLDivElement>(null)
  const over = useRef<HTMLElement | null>(null)
  const following = ghost.on && !ghost.dropped
  const { x: ox, y: oy } = ghost.off
  const { x, y } = ghost.at
  useLayoutEffect(() => {
    const root = ref.current?.closest<HTMLElement>('.ss-stage')
    let next: HTMLElement | null = null
    if (following && root) {
      const box = root.getBoundingClientRect()
      const scale = box.width / root.offsetWidth || 1
      const hit = document.elementFromPoint(box.left + x * scale, box.top + y * scale)?.closest<HTMLElement>('[data-drop]') ?? null
      if (hit && root.contains(hit)) next = hit
    }
    if (next !== over.current) {
      over.current?.removeAttribute('data-over')
      next?.setAttribute('data-over', '')
      over.current = next
    }
  }, [following, x, y])
  useLayoutEffect(() => () => over.current?.removeAttribute('data-over'), [])
  return (
    <div
      ref={ref}
      className="wd-drag"
      data-show={following || undefined}
      data-dropped={ghost.dropped || undefined}
      style={{ transform: `translate(${String(x - ox)}px, ${String(y - oy)}px)` }}
      aria-hidden
    >
      <div className="wd-drag__inner" style={{ transformOrigin: `${String(ox)}px ${String(oy)}px` }}>
        {children}
      </div>
    </div>
  )
}
