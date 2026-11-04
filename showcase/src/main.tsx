import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import TelegramDemo from './scenes/TelegramDemo'
import WebDemo from './scenes/WebDemo'
import './page.css'

const SCENES = { web: WebDemo, telegram: TelegramDemo } as const
type Name = keyof typeof SCENES

// ?capture=<scene> renders one stage alone on a white page, for filming.
const capture = new URLSearchParams(location.search).get('capture') as Name | null

function Page() {
  if (capture && capture in SCENES) {
    const Scene = SCENES[capture]
    return (
      <div id="example" className="capture">
        <Scene />
      </div>
    )
  }
  return (
    <main className="page">
      {(Object.keys(SCENES) as Name[]).map((name) => {
        const Scene = SCENES[name]
        return (
          <section key={name}>
            <a href={`?capture=${name}`}>{name}</a>
            <Scene />
          </section>
        )
      })}
    </main>
  )
}

const root = document.getElementById('root')
if (root) createRoot(root).render(<StrictMode><Page /></StrictMode>)
