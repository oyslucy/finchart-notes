import { Avatar, Bar, Bubble, Fly, Phone, Stage, Thread, Window, type Act, type Rect } from '../../kit'
import { Candles } from './Candles'
import './telegram.css'

// finchart-notes, Telegram. A device pair (from the Device pair gold): the web
// board is pinned top-left and runs off the bottom; the phone straddles its right
// edge over filler cards. A chart screenshot is sent to the bot with #반도체; the
// bot answers in place of its typing dots with the title, one takeaway and the
// board, offering other boards as buttons. Then the result lands somewhere else:
// the chart flies from the chat into the first slot of the board.
//
// Real words: the board title, the bot's name, the caption, the reply and its
// buttons.

type Fl = { from: Rect; to: Rect; go: boolean }
type S = {
  sent: boolean
  typing: boolean
  replied: boolean
  flying: boolean
  fly: Fl
  room: boolean
  landed: boolean
}

const ZERO: Rect = { x: 0, y: 0, width: 0, height: 0 }
const NO_FLY: Fl = { from: ZERO, to: ZERO, go: false }
const initial: S = { sent: false, typing: false, replied: false, flying: false, fly: NO_FLY, room: false, landed: false }
const poster: S = { ...initial, sent: true, replied: true, room: true, landed: true }

const COL = 176
const GAP = 14
const GRID_TOP = 70
const ROW = 188
const FILLERS = [
  { seed: 11, title: 96, meta: 64 },
  { seed: 23, title: 84, meta: 58 },
  { seed: 5, title: 108, meta: 52 },
  { seed: 41, title: 90, meta: 66 },
  { seed: 17, title: 102, meta: 60 },
]

function slot(k: number) {
  return { left: 20 + (k % 3) * (COL + GAP), top: GRID_TOP + Math.floor(k / 3) * ROW }
}

async function script(a: Act<S>) {
  await a.wait(800)

  // 1. The screenshot goes out with its board tag
  a.mark('send')
  await a.set({ sent: true })
  await a.wait(900)

  // 2. The bot is working
  a.mark('typing')
  await a.set({ typing: true })
  await a.wait(1500)

  // 3. Its dots grow into the answer, with other boards as buttons
  a.mark('reply')
  await a.set({ typing: false, replied: true })
  await a.wait(1300)

  // 4. The chart buds off the sent photo and flies to the board's first slot;
  //    the other cards make room while it travels, and it lands as the card's
  //    thumbnail, the card arriving whole around it
  a.mark('fly')
  const from = a.rect('sent-chart')
  const to = a.rect('new-thumb')
  await a.set({ flying: true, fly: { from, to, go: false } })
  await a.wait(300)
  await a.set({ fly: { from, to, go: true }, room: true })
  await a.wait(950)
  // The card fades in under the landed chart, which matches its thumbnail; then the flyer goes
  await a.set({ landed: true })
  await a.wait(320)
  await a.set({ flying: false })
  await a.snap({ fly: NO_FLY })
  a.mark('done')
  await a.wait(3000)
}

export default function TelegramDemo() {
  return (
    <Stage<S> width={760} height={440} initial={initial} poster={poster} script={script} play="once" accent="#7266d6" className="tgd">
      {(s) => (
        <>
          <Window url="finchart-notes.duckdns.org" className="tgd-window" body={{ className: 'tgd-body', 'data-crop': true }}>
            <div className="tgd-board">
              <span className="tgd-board__title">반도체</span>
              <Bar w={40} h={7} tone={2} />
            </div>

            {FILLERS.map((f, i) => (
              <div key={i} className="tgd-card" style={slot(i + (s.room ? 1 : 0))}>
                <div className="tgd-thumb">
                  <Candles width={COL - 20} height={100} seed={f.seed} muted />
                </div>
                <div className="tgd-text">
                  <Bar w={f.title} h={7} tone={3} />
                  <Bar w={f.meta} h={6} tone={2} />
                </div>
              </div>
            ))}

            {/* The landing card: its thumbnail is the Fly's target and it shows once the chart lands */}
            <div className="tgd-card tgd-new" data-target="new-card" data-show={s.landed || undefined} style={slot(0)}>
              <NewCard />
            </div>
          </Window>

          <Phone width={268} frame="pro" className="tgd-phone">
            <div className="tgd-paper" aria-hidden />
            <div className="tgd-head">
              <Avatar name="F" size={30} className="tgd-avatar" />
              <span className="tgd-name">
                Finchart Note Bot
                <span className="tgd-status">bot</span>
              </span>
            </div>
            <Thread className="tgd-thread">
              <Bubble from="them">스크린샷을 보내면 카드로 저장합니다.</Bubble>
              {s.sent && (
                <Bubble from="me" className="tgd-photo">
                  <span className="tgd-photo__img" data-target="sent-chart">
                    <Candles width={160} height={96} seed={7} count={30} />
                  </span>
                  <span className="tgd-caption">#반도체</span>
                </Bubble>
              )}
              {(s.typing || s.replied) && (
                <Bubble from="them" typing={s.typing} className="tgd-reply">
                  <span className="tgd-line tgd-reply__title">KOSPI 일봉</span>
                  <span className="tgd-line">• 약 3,100선 회복</span>
                  <span className="tgd-line tgd-reply__board">보드: 반도체</span>
                </Bubble>
              )}
              {s.replied && (
                <div className="tgd-buttons">
                  <span>IT</span>
                  <span>2차전지</span>
                </div>
              )}
            </Thread>
          </Phone>

          {s.flying && (
            <div className="tgd-flywrap" data-out={s.landed || undefined}>
              {/* The wrapper fades the flyer out over the card that has faded in under it */}
              <Fly from={s.fly.from} to={s.fly.to} go={s.fly.go} held duration={900} className="tgd-fly">
                <span className="tgd-fly__card">
                  {/* The phone scales its content, so draw at the start box measured in stage px */}
                  <Candles width={Math.round(s.fly.from.width)} height={Math.round(s.fly.from.height)} seed={7} count={30} />
                </span>
              </Fly>
            </div>
          )}
        </>
      )}
    </Stage>
  )
}

/** The card the analysis becomes; also what flies from the chat to the board. */
function NewCard() {
  return (
    <>
      <div className="tgd-thumb tgd-thumb--new" data-target="new-thumb">
        <Candles width={COL - 20} height={100} seed={7} count={30} />
      </div>
      <div className="tgd-text">
        <span className="tgd-title">KOSPI 일봉</span>
        <span className="tgd-meta">캔들스틱 · 텔레그램에서 추가</span>
      </div>
    </>
  )
}
