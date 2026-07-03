import { useEffect, useState } from 'react'
import { countOf, fetchRows } from '../../api'
import CollapsibleCard from '../CollapsibleCard'

const STATUS_META = {
  ready:      { label: '✅ Готово',    color: 'var(--green)' },
  queued:     { label: '⏳ В очереди',  color: 'var(--amber)' },
  generating: { label: '🎬 Генерация', color: 'var(--indigo)' },
  failed:     { label: '❌ Ошибка',    color: 'var(--red)' },
}

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
  const [videos, setVideos]   = useState(0)
  const [clips, setClips]     = useState([])
  const [plans, setPlans]     = useState({})
  const [loading, setLoading] = useState(true)

  async function loadGallery() {
    setLoading(true)
    const [count, vids, planRows] = await Promise.all([
      countOf('videos'),
      fetchRows('videos', 'select=id,status,storage_url,duration_sec,created_at,content_plan_id&order=created_at.desc&limit=60'),
      fetchRows('content_plans', 'select=id,title,vertical,format&order=created_at.desc&limit=200'),
    ])
    setVideos(count)
    setClips(vids || [])
    setPlans(Object.fromEntries((planRows || []).map(p => [p.id, p])))
    setLoading(false)
  }

  useEffect(() => { loadGallery() }, [])

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

      <CollapsibleCard title="🎞 Галерея видео" count={clips.length} defaultOpen
        headerRight={
          <button onClick={loadGallery} disabled={loading}
            style={{ fontSize:11, padding:'3px 10px', borderRadius:6, background:'var(--surface2)',
              border:'1px solid var(--border)', color:'var(--muted)', cursor:'pointer' }}>
            ↻ Обновить
          </button>}>
        {loading && <div className="note-box">Загрузка…</div>}
        {!loading && clips.length === 0 && (
          <div className="note-box">
            Видео пока нет. Запусти пайплайн с профилем <b>video</b> (раздел «Запуск агентов» или чат
            оркестратора) — готовые ролики появятся здесь из таблицы <code>videos</code>.
          </div>
        )}
        {!loading && clips.length > 0 && (
          <div style={{ display:'grid', gridTemplateColumns:'repeat(auto-fill,minmax(200px,1fr))', gap:12 }}>
            {clips.map(v => {
              const plan = plans[v.content_plan_id] || {}
              const st = STATUS_META[v.status] || { label: v.status, color: 'var(--faint)' }
              return (
                <div key={v.id} style={{ background:'var(--surface2)', border:'1px solid var(--border)',
                  borderRadius:10, overflow:'hidden', display:'flex', flexDirection:'column' }}>
                  {v.status === 'ready' && v.storage_url
                    ? <video src={v.storage_url} controls preload="metadata"
                        style={{ width:'100%', aspectRatio:'9/16', objectFit:'cover', background:'#000' }} />
                    : <div style={{ width:'100%', aspectRatio:'9/16', display:'flex', alignItems:'center',
                        justifyContent:'center', background:'var(--surface3, #1a1a2e)', color:st.color, fontSize:13 }}>
                        {st.label}
                      </div>}
                  <div style={{ padding:'8px 10px' }}>
                    <div style={{ fontSize:12, fontWeight:600, color:'var(--text)', overflow:'hidden',
                      textOverflow:'ellipsis', whiteSpace:'nowrap' }}>
                      {plan.title || '—'}
                    </div>
                    <div style={{ display:'flex', gap:5, flexWrap:'wrap', marginTop:5, alignItems:'center' }}>
                      {plan.vertical && <span className="badge badge-indigo" style={{ fontSize:9 }}>{plan.vertical}</span>}
                      {plan.format && <span style={{ fontSize:10, color:'var(--faint)' }}>{plan.format}</span>}
                      <span style={{ fontSize:10, color:st.color, marginLeft:'auto' }}>{st.label}</span>
                    </div>
                    <div style={{ fontSize:10, color:'var(--faint)', marginTop:4 }}>
                      {v.duration_sec ? `${v.duration_sec}с · ` : ''}{(v.created_at || '').slice(0,10)}
                      {v.status === 'ready' && v.storage_url && (
                        <> · <a href={v.storage_url} target="_blank" rel="noreferrer" style={{ color:'var(--indigo)' }}>↗</a></>
                      )}
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </CollapsibleCard>

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
