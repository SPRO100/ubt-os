import { useEffect, useState } from 'react'
import { countOf } from '../../api'
import CollapsibleCard from '../CollapsibleCard'

const PIPELINE = [
  { step:'Spy-анализ крипов',      tool:'A27 spy_analyzer.py (PiPiAds/AdHeart)', plat:'TikTok/FB',     status:'готов',         color:'var(--green)' },
  { step:'Тренды / конкуренты',    tool:'A20 trend_scraper.py (Firecrawl)',       plat:'Все',           status:'нужен FIRECRAWL_API_KEY', color:'var(--amber)' },
  { step:'Контент-план',           tool:'A21 content_creator.py',                 plat:'Все',           status:'готов',         color:'var(--green)' },
  { step:'Очистка AI-маркеров',    tool:'A19 text_humanizer.py (Stop-Slop)',      plat:'Все',           status:'готов',         color:'var(--green)' },
  { step:'Видеогенерация',         tool:'A30 higgsfield_agent.py',                plat:'TikTok/IG',     status:'нужен API ключ',color:'var(--amber)' },
  { step:'Озвучка',                tool:'edge-tts (установлен)',                  plat:'Все',           status:'готов',         color:'var(--green)' },
  { step:'Прелендинг',             tool:'A29 prelanding_generator.py',            plat:'Все воронки',   status:'готов',         color:'var(--green)' },
  { step:'Compliance Gate',        tool:'A25 compliance_gate.py (regex + LLM)',   plat:'Все',           status:'готов',         color:'var(--green)' },
  { step:'Keitaro UTM',            tool:'_build_utm() в A26',                     plat:'Все',           status:'готов',         color:'var(--green)' },
  { step:'Публикация',             tool:'A26 publer_publisher.py ($12/мес)',       plat:'TikTok/FB/IG/Pinterest', status:'нужен PUBLER_API_KEY', color:'var(--amber)' },
]

export default function Content() {
  const [videos, setVideos] = useState(0)

  useEffect(() => {
    countOf('videos').then(setVideos)
  }, [])

  return (
    <>
      <div className="stat-grid">
        <div className="stat-card c-indigo">
          <div className="stat-left">
            <div className="stat-label">Произведено видео</div>
            <div className="stat-value">{videos}</div>
            <div className="stat-note">из таблицы videos</div>
          </div>
          <div className="stat-icon" style={{ background:'var(--indigo-bg)' }}>🎬</div>
        </div>
      </div>

      <CollapsibleCard title="⚙️ Производственный пайплайн A19–A30" tag="архитектура" count={PIPELINE.length} defaultOpen>
        <table>
          <thead><tr><th>Этап</th><th>Инструмент</th><th>Платформы</th><th>Статус</th></tr></thead>
          <tbody>
            {PIPELINE.map(p => (
              <tr key={p.step}>
                <td className="primary">{p.step}</td>
                <td style={{ fontFamily:"'IBM Plex Mono',monospace", fontSize:11.5 }}>{p.tool}</td>
                <td style={{ color:'var(--faint)', fontSize:12 }}>{p.plat}</td>
                <td>
                  <span className="badge" style={{ color:p.color, background:p.color+'1a' }}>{p.status}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </CollapsibleCard>
    </>
  )
}
