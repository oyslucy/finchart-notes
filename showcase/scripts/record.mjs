// Record one stage to a GIF for the README: the stage's clock and every CSS
// transition run --slow times slower while element screenshots are taken, so a
// slow machine still lands one frame every 1000 / --fps ms of scene time.
// ffmpeg comes from imageio-ffmpeg (uv run --with imageio-ffmpeg).
//
//   node scripts/record.mjs <url> --out ../docs/assets/web.gif [--ms 11000]
//        [--fps 20] [--slow 8] [--width 880] [--select "#example .ss-stage"]
import { execFileSync } from 'node:child_process'
import { mkdirSync, rmSync } from 'node:fs'
import { resolve } from 'node:path'

import { launch } from './browser.mjs'

const args = process.argv.slice(2)
const url = args[0]
const opt = (name, fallback) => {
  const i = args.indexOf(`--${name}`)
  return i === -1 ? fallback : args[i + 1]
}
const out = resolve(opt('out', 'shots/stage.gif'))
const ms = Number(opt('ms', 11000))
const fps = Number(opt('fps', 20))
const slow = Number(opt('slow', 8))
const width = Number(opt('width', 880))
const select = opt('select', '#example .ss-stage')
const dir = resolve('frames')

rmSync(dir, { recursive: true, force: true })
mkdirSync(dir, { recursive: true })

const browser = await launch()
const page = await browser.newPage({ viewport: { width: 1000, height: 700 }, deviceScaleFactor: 2 })
await page.addInitScript((slow) => {
  window.__stageshow = { slow }
}, slow)
const cdp = await page.context().newCDPSession(page)
await cdp.send('Animation.enable')
await cdp.send('Animation.setPlaybackRate', { playbackRate: 1 / slow })
await page.goto(url)
const stage = page.locator(select).first()
await stage.waitFor({ state: 'visible' })
await page.evaluate(() => document.fonts.ready)

const step = 1000 / fps
const start = Date.now()
const frames = Math.round(ms / step)
for (let i = 0; i < frames; i++) {
  await page.waitForTimeout(Math.max(0, start + i * step * slow - Date.now()))
  await stage.screenshot({ path: `${dir}/${String(i).padStart(4, '0')}.png`, animations: 'allow' })
}
await browser.close()

const ffmpeg = execFileSync('uv', ['run', '--quiet', '--with', 'imageio-ffmpeg', 'python', '-c', 'import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())']).toString().trim()
const filter = `scale=${width}:-1:flags=lanczos,split[a][b];[a]palettegen=stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle`
mkdirSync(resolve(out, '..'), { recursive: true })
execFileSync(ffmpeg, ['-y', '-loglevel', 'error', '-framerate', String(fps), '-i', `${dir}/%04d.png`, '-filter_complex', filter, '-loop', '0', out])
console.log(`${frames} frames -> ${out}`)
