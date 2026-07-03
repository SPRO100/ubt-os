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
  const [openClip, setOpenClip] = useState(null)

  useEffect(() => {
    if (!openClip) return
    const onKey = e => { if (e.key === 'Escape') setOpenClip(null) }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [openClip])

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
          <div style={{ display:'grid', gridTemplateColumns:'repeat(auto-fill,minmax(110px,1fr))', gap:8 }}>
            {clips.map(v => {
              const plan = plans[v.content_plan_id] || {}
              const st = STATUS_META[v.status] || { label: v.status, color: 'var(--faint)' }
              const ready = v.status === 'ready' && v.storage_url
              return (
                <div key={v.id} onClick={() => setOpenClip(v)}
                  role="button" tabIndex={0}
                  title={plan.title || v.id}
                  style={{ background:'var(--surface2)', border:'1px solid var(--border)',
                    borderRadius:8, overflow:'hidden', cursor:'pointer', position:'relative' }}>
                  {ready
                    ? <video src={v.storage_url + '#t=0.5'} preload="metadata" muted
                        style={{ width:'100%', aspectRatio:'9/16', objectFit:'cover', background:'#000', display:'block' }} />
                    : <div style={{ width:'100%', aspectRatio:'9/16', display:'flex', alignItems:'center',
                        justifyContent:'center', background:'var(--surface3, #1a1a2e)', color:st.color, fontSize:10,
                        textAlign:'center', padding:4 }}>
                        {st.label}
                      </div>}
                  {ready && (
                    <div style={{ position:'absolute', inset:0, display:'flex', alignItems:'center',
                      justifyContent:'center', background:'rgba(0,0,0,.15)', opacity:0,
                      transition:'opacity .15s', fontSize:20 }}
                      onMouseEnter={e => e.currentTarget.style.opacity = 1}
                      onMouseLeave={e => e.currentTarget.style.opacity = 0}>
                      ▶
                    </div>
                  )}
                  <div style={{ position:'absolute', bottom:0, left:0, right:0, padding:'3px 5px',
                    background:'linear-gradient(transparent, rgba(0,0,0,.75))', fontSize:9, color:'#fff',
                    overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>
                    {plan.vertical || plan.title || '—'}
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </CollapsibleCard>

      {openClip && (() => {
        const plan = plans[openClip.content_plan_id] || {}
        const st = STATUS_META[openClip.status] || { label: openClip.status, color: 'var(--faint)' }
        const ready = openClip.status === 'ready' && openClip.storage_url
        return (
          <div onClick={() => setOpenClip(null)}
            style={{ position:'fixed', inset:0, background:'rgba(0,0,0,.75)', zIndex:1000,
              display:'flex', alignItems:'center', justifyContent:'center', padding:20 }}>
            <div onClick={e => e.stopPropagation()}
              style={{ background:'var(--surface)', borderRadius:12, overflow:'hidden',
                maxWidth:420, width:'100%', maxHeight:'90vh', display:'flex', flexDirection:'column' }}>
              {ready
                ? <video src={openClip.storage_url} controls autoPlay
                    style={{ width:'100%', maxHeight:'70vh', background:'#000', display:'block' }} />
                : <div style={{ width:'100%', aspectRatio:'9/16', display:'flex', alignItems:'center',
                    justifyContent:'center', background:'var(--surface3, #1a1a2e)', color:st.color, fontSize:16 }}>
                    {st.label}
                  </div>}
              <div style={{ padding:'12px 16px' }}>
                <div style={{ fontSize:14, fontWeight:600, color:'var(--text)' }}>{plan.title || '—'}</div>
                <div style={{ display:'flex', gap:6, flexWrap:'wrap', marginTop:6, alignItems:'center' }}>
                  {plan.vertical && <span className="badge badge-indigo" style={{ fontSize:10 }}>{plan.vertical}</span>}
                  {plan.format && <span style={{ fontSize:11, color:'var(--faint)' }}>{plan.format}</span>}
                  <span style={{ fontSize:11, color:st.color }}>{st.label}</span>
                </div>
                <div style={{ fontSize:11, color:'var(--faint)', marginTop:6 }}>
                  {openClip.duration_sec ? `${openClip.duration_sec}с · ` : ''}{(openClip.created_at || '').slice(0,10)}
                  {ready && (
                    <> · <a href={openClip.storage_url} target="_blank" rel="noreferrer" style={{ color:'var(--indigo)' }}>открыть в новой вкладке ↗</a></>
                  )}
                </div>
              </div>
              <button onClick={() => setOpenClip(null)}
                style={{ position:'absolute', top:10, right:10, width:28, height:28, borderRadius:'50%',
                  background:'rgba(0,0,0,.5)', border:'none', color:'#fff', fontSize:15, cursor:'pointer' }}>
                ✕
              </button>
            </div>
          </div>
        )
      })()}

      <CollapsibleCard title="⚙️ Производственный пайплайн A19–A30" tag="архитектура" count={PIPELINE.length}>
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
