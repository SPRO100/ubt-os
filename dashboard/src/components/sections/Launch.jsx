import { useState } from 'react'
import { runAgentAPI, postAgents } from '../../api'

// Провайдеры видеогенерации: '' = авто-цепочка из env VIDEO_PROVIDER_CHAIN
const VIDEO_PROVIDERS = [
  { value: '',           label: '⚙️ Авто (stock → fal → higgsfield)' },
  { value: 'stock',      label: '🆓 Stock — бесплатно (Pexels + edge-tts)' },
  { value: 'fal',        label: '💸 fal.ai — Wan 2.5 (~$0.25/ролик)' },
  { value: 'higgsfield', label: '💎 Higgsfield — кредиты' },
]

function PipelineCard() {
  const [vert, setVert]         = useState('nutra')
  const [geo, setGeo]           = useState('US')
  const [offer, setOffer]       = useState('')
  const [count, setCount]       = useState('1')
  const [provider, setProvider] = useState(localStorage.getItem('video_provider') || '')
  const [loading, setLoading]   = useState(false)
  const [result, setResult]     = useState(null)
  const [error, setError]       = useState(null)

  function changeProvider(v) {
    setProvider(v)
    localStorage.setItem('video_provider', v)
  }

  async function launch() {
    setLoading(true); setResult(null); setError(null)
    try {
      const path = vert === 'betting' ? '/run/ubt' : '/run/nutra'
      const data = await postAgents(path, { geo, offer, count: Number(count) || 1, provider }, 300000)
      setResult(data)
    } catch (e) { setError(e.message) }
    setLoading(false)
  }

  return (
    <div className="agent-card" style={{ gridColumn: '1 / -1', borderColor: 'var(--indigo-bd)' }}>
      <div className="agent-card-head">
        <span className="agent-id-tag">PIPELINE</span>
        <span className="agent-name">Видео-пайплайн: контент → compliance → генерация</span>
      </div>
      <div className="agent-desc">
        A21 скрипт → A25 проверка → очередь генерации. Публикации нет — черновик на одобрение.
      </div>
      <div style={{ display:'grid', gridTemplateColumns:'repeat(auto-fit,minmax(160px,1fr))', gap:8 }}>
        <div>
          <label className="form-label">Вертикаль</label>
          <select className="form-control" value={vert} onChange={e=>setVert(e.target.value)}>
            <option value="nutra">Nutra</option><option value="betting">Betting (UBT)</option>
          </select>
        </div>
        <div>
          <label className="form-label">GEO</label>
          <select className="form-control" value={geo} onChange={e=>setGeo(e.target.value)}>
            {['US','BR','MX','DE','PL'].map(g=><option key={g}>{g}</option>)}
          </select>
        </div>
        <div>
          <label className="form-label">Оффер</label>
          <input className="form-control" value={offer} onChange={e=>setOffer(e.target.value)} placeholder="Dr.Cash / 1win" />
        </div>
        <div>
          <label className="form-label">Кол-во</label>
          <input className="form-control" type="number" min="1" max="10" value={count} onChange={e=>setCount(e.target.value)} />
        </div>
        <div style={{ gridColumn:'1 / -1' }}>
          <label className="form-label">Провайдер генерации видео</label>
          <select className="form-control" value={provider} onChange={e=>changeProvider(e.target.value)}>
            {VIDEO_PROVIDERS.map(p=><option key={p.value} value={p.value}>{p.label}</option>)}
          </select>
        </div>
      </div>
      <button className="btn btn-primary btn-block" disabled={loading} style={{ marginTop:10 }}
        onClick={launch}>
        {loading ? '⏳ Работает…' : '▶ Запустить пайплайн'}
      </button>
      {error && <div className="agent-result"><span style={{ color:'var(--red)' }}>⚠️ {error}</span></div>}
      {result && (
        <div className="agent-result">
          <pre style={{ margin:0, fontSize:11 }}>{JSON.stringify(result, null, 2)}</pre>
        </div>
      )}
    </div>
  )
}

function AgentResult({ data, agent }) {
  if (!data) return null
  if (data.error) return <div style={{ color:'var(--red)' }}>Ошибка: {data.error}</div>

  const copyBtn = (
    <button className="copy-btn" onClick={() => navigator.clipboard.writeText(JSON.stringify(data, null, 2)).catch(()=>{})}>
      Скопировать
    </button>
  )

  if (agent === 'content_creator' || agent === 'text_humanizer') {
    const score = data.score ?? 0; const pct = Math.min(100, Math.round((score/50)*100))
    const sc = data.passed ? 'var(--green)' : score < 40 ? 'var(--red)' : 'var(--amber)'
    return <div>
      {copyBtn}
      <div style={{ marginBottom:10 }}>
        <div style={{ fontSize:11, color:'var(--faint)', marginBottom:4 }}>
          Stop-Slop: <b style={{ color:sc }}>{score}/50</b> ·{' '}
          {data.passed ? <span style={{ color:'var(--green)' }}>✅ Прошёл</span> : <span style={{ color:'var(--red)' }}>❌ Доработать</span>}
        </div>
        <div className="score-bar"><div className="score-fill" style={{ width:pct+'%', background:sc }} /></div>
      </div>
      <div style={{ whiteSpace:'pre-wrap', lineHeight:1.65 }}>{data.result || ''}</div>
    </div>
  }

  if (agent === 'ads_auditor') {
    const score = data.health_score ?? 0; const grade = String(data.grade ?? '—')
    const gc = {'A+':'var(--green)','A':'var(--green)','B':'var(--indigo)','C':'var(--amber)','D':'var(--red)','F':'var(--red)'}[grade]||'var(--muted)'
    return <div>
      {copyBtn}
      <div style={{ display:'flex', alignItems:'center', gap:16, marginBottom:12 }}>
        <div>
          <div style={{ fontSize:28, fontWeight:700, fontFamily:"'IBM Plex Mono',monospace", color:gc }}>{grade}</div>
          <div style={{ fontSize:10, color:'var(--faint)' }}>GRADE</div>
        </div>
        <div style={{ flex:1 }}>
          <div style={{ fontSize:11, color:'var(--faint)', marginBottom:4 }}>Health Score: <b style={{ color:gc }}>{score}/100</b></div>
          <div className="score-bar"><div className="score-fill" style={{ width:score+'%', background:gc }} /></div>
        </div>
      </div>
      <div style={{ marginBottom:8 }}>
        <b style={{ color:'var(--red)', fontSize:11 }}>КРИТИЧЕСКИЕ ПРОБЛЕМЫ</b><br/>
        {(data.critical_issues||[]).map((i,k)=><div key={k} style={{ padding:'3px 0', borderBottom:'1px solid var(--border)' }}>• {i}</div>)||<span style={{ color:'var(--faint)' }}>нет</span>}
      </div>
      <div><b style={{ color:'var(--green)', fontSize:11 }}>QUICK WINS</b><br/>
        {(data.quick_wins||[]).map((i,k)=><div key={k} style={{ padding:'3px 0', borderBottom:'1px solid var(--border)' }}>• {i}</div>)||<span style={{ color:'var(--faint)' }}>нет</span>}
      </div>
    </div>
  }

  if (agent === 'obsidian_brain') {
    return <div>
      {copyBtn}
      {data.answer && <div style={{ whiteSpace:'pre-wrap', lineHeight:1.65, marginBottom:10 }}>{data.answer}</div>}
      {data.confidence !== undefined && (
        <div style={{ fontSize:11, color:'var(--faint)', marginBottom:8 }}>
          Уверенность: <b style={{ color: (data.confidence||0) > 0.7 ? 'var(--green)' : 'var(--amber)' }}>
            {Math.round((data.confidence||0)*100)}%
          </b>
        </div>
      )}
      {(data.sources||[]).length > 0 && <div>
        <b style={{ fontSize:11, color:'var(--indigo)' }}>ИСТОЧНИКИ</b>
        {data.sources.map((s,i) => <div key={i} style={{ padding:'2px 0', fontSize:11, color:'var(--faint)' }}>• {s}</div>)}
      </div>}
      {!data.answer && <pre style={{ margin:0, fontSize:11 }}>{JSON.stringify(data, null, 2)}</pre>}
    </div>
  }

  if (agent === 'compliance_gate') {
    const risk = data.risk_level ?? '—'; const score = data.score ?? 0
    const rc = risk==='safe'?'var(--green)':risk==='warning'?'var(--amber)':'var(--red)'
    const rl = {'safe':'✅ БЕЗОПАСНО','warning':'⚠️ ПРЕДУПРЕЖДЕНИЕ','blocked':'🚫 ЗАБЛОКИРОВАНО'}[risk]||risk
    return <div>
      {copyBtn}
      <div style={{ display:'flex', alignItems:'center', gap:12, marginBottom:12 }}>
        <b style={{ color:rc, fontSize:15 }}>{rl}</b>
        <span style={{ fontSize:11, color:'var(--faint)' }}>Score: <b style={{ color:rc }}>{score}/100</b></span>
      </div>
      {data.violations?.length ? <div style={{ marginBottom:8 }}>
        <b style={{ fontSize:11, color:'var(--red)' }}>НАРУШЕНИЯ</b><br/>
        {data.violations.map((v,i)=><div key={i} style={{ padding:'3px 0', borderBottom:'1px solid var(--border)', fontSize:12 }}>
          <span style={{ color:v.severity==='hard'?'var(--red)':'var(--amber)' }}>[{v.severity}]</span>{' '}
          <b>{v.rule}</b>: «{v.text}»
        </div>)}
      </div> : null}
      {data.clean_version ? <div>
        <b style={{ fontSize:11, color:'var(--green)' }}>ИСПРАВЛЕННАЯ ВЕРСИЯ</b>
        <div style={{ marginTop:4, whiteSpace:'pre-wrap' }}>{data.clean_version}</div>
      </div> : null}
    </div>
  }

  if (agent === 'publer_publisher') {
    const status = data.status ?? '—'
    const sc = {'published':'var(--green)','dry_run':'var(--indigo)','blocked':'var(--red)','failed':'var(--red)'}[status]||'var(--muted)'
    const sl = {'published':'✅ Опубликовано','dry_run':'🔵 Dry Run','blocked':'🚫 Заблокировано','failed':'❌ Ошибка'}[status]||status
    return <div>
      {copyBtn}
      <div style={{ marginBottom:10 }}><b style={{ color:sc }}>{sl}</b></div>
      <div style={{ fontSize:11, color:'var(--faint)' }}>
        Платформа: <b style={{ color:'var(--text)' }}>{data.platform||'—'}</b><br/>
        Compliance: <b style={{ color:'var(--green)' }}>{data.compliance_score??'—'}/100</b><br/>
        {data.url && <>URL: <a href={data.url} target="_blank" rel="noopener noreferrer">{data.url}</a><br/></>}
        {data.error && <span style={{ color:'var(--red)' }}>{data.error}</span>}
      </div>
    </div>
  }

  if (agent === 'warmup_manager') {
    if (data.accounts) {
      return <div>
        {copyBtn}
        <b style={{ fontSize:11 }}>Аккаунты в системе: {data.accounts.length}</b>
        {data.accounts.map((a,i)=>{
          const pct=a.progress||0; const sc=a.status==='ready'?'var(--green)':a.status==='blocked'?'var(--red)':'var(--indigo)'
          return <div key={i} style={{ padding:'6px 0', borderBottom:'1px solid var(--border)' }}>
            <span style={{ color:'var(--text)', fontWeight:600 }}>{a.account_id}</span>
            <span className="badge" style={{ marginLeft:8, color:sc, background:sc+'22' }}>{a.status}</span>
            <span style={{ float:'right', fontSize:11, color:'var(--faint)' }}>День {a.day}/{a.total} · {a.geo}</span>
            <div style={{ height:3, background:'var(--border)', borderRadius:2, marginTop:4 }}>
              <div style={{ height:3, width:pct+'%', background:sc, borderRadius:2 }} />
            </div>
          </div>
        })}
      </div>
    }
    const status=data.status||'—'; const pct=data.progress_pct||0
    const sc=status==='ready'?'var(--green)':status==='blocked'?'var(--red)':'var(--indigo)'
    return <div>
      {copyBtn}
      <div style={{ display:'flex', alignItems:'center', gap:10, marginBottom:8 }}>
        <b style={{ color:sc }}>{status.toUpperCase()}</b>
        <span style={{ fontSize:12, color:'var(--muted)' }}>День {data.current_day}/{data.total_days} ({pct}%)</span>
      </div>
      <div style={{ height:4, background:'var(--border)', borderRadius:2, marginBottom:12 }}>
        <div style={{ height:4, width:pct+'%', background:sc, borderRadius:2 }} />
      </div>
      {data.next_action && <div style={{ padding:8, background:'var(--surface2)', borderRadius:6, fontSize:12 }}>
        <b style={{ color:'var(--text)' }}>Следующее действие:</b><br/>{data.next_action}
      </div>}
    </div>
  }

  if (agent === 'prelanding_generator') {
    return <div>
      {copyBtn}
      <div style={{ display:'flex', gap:12, flexWrap:'wrap', marginBottom:10, fontSize:12 }}>
        <span>Формат: <b style={{ color:'var(--text)' }}>{data.format||'?'}</b></span>
        <span>CR: <b style={{ color:'var(--green)' }}>{data.estimated_cr||'?'}</b></span>
        <span>Слов: <b style={{ color:'var(--text)' }}>{data.word_count||0}</b></span>
      </div>
      {data.html_content && <div>
        <b style={{ fontSize:11, color:'var(--text)' }}>HTML КОД</b>
        <pre style={{ margin:'6px 0 0', padding:10, background:'var(--surface2)', borderRadius:6, fontSize:10, maxHeight:280, overflowY:'auto', whiteSpace:'pre-wrap', wordBreak:'break-all' }}>
          {data.html_content.substring(0,2000)}{data.html_content.length>2000?'\n…ещё '+(data.html_content.length-2000)+' символов':''}
        </pre>
      </div>}
    </div>
  }

  if (agent === 'spy_analyzer') {
    const hooks=(data.hook_patterns||[])
    return <div>
      {copyBtn}
      <div style={{ fontSize:11, color:'var(--faint)', marginBottom:10 }}>Проанализировано крипов: <b style={{ color:'var(--text)' }}>{data.creatives_analyzed||0}</b></div>
      {hooks.length ? <div style={{ marginBottom:10 }}>
        <b style={{ fontSize:11, color:'var(--green)' }}>ПАТТЕРНЫ ХУКОВ</b>
        {hooks.map((h,i)=><div key={i} style={{ padding:'4px 0', borderBottom:'1px solid var(--border)', fontSize:12 }}>
          <span style={{ color:'var(--text)' }}>{h.pattern||''}</span>
          {h.example && <><br/><span style={{ color:'var(--faint)', fontStyle:'italic' }}>«{h.example}»</span></>}
        </div>)}
      </div> : null}
      {data.creative_brief && <div style={{ marginTop:8, padding:10, background:'var(--surface2)', borderRadius:6, fontSize:12, whiteSpace:'pre-wrap', lineHeight:1.6 }}>
        <b style={{ color:'var(--text)', fontSize:11 }}>CREATIVE BRIEF для A21</b><br/>{data.creative_brief}
      </div>}
    </div>
  }

  if (agent === 'higgsfield_agent') {
    const status=data.status??'—'
    const sc={completed:'var(--green)',dry_run:'var(--indigo)',failed:'var(--red)',timeout:'var(--amber)'}[status]||'var(--muted)'
    const sl={completed:'✅ Готово',dry_run:'🔵 Dry Run (нет API ключа)',failed:'❌ Ошибка',timeout:'⏱ Timeout',pending:'⏳ Ожидает'}[status]||status
    if (data.video_url) return <div>
      {copyBtn}
      <div style={{ marginBottom:10 }}><b style={{ color:sc }}>{sl}</b></div>
      <video src={data.video_url} controls style={{ maxWidth:'100%', borderRadius:8, background:'#000' }} />
      <div style={{ marginTop:8, fontSize:11, color:'var(--faint)' }}>
        <a href={data.video_url} target="_blank" rel="noopener noreferrer" style={{ color:'var(--indigo)' }}>Открыть видео ↗</a>
      </div>
    </div>
    return <div>
      {copyBtn}
      <div style={{ marginBottom:8 }}><b style={{ color:sc }}>{sl}</b></div>
      {data.job_id && <div style={{ fontSize:11, color:'var(--faint)' }}>Job ID: <span className="mono">{data.job_id}</span></div>}
      {data.error && <div style={{ color:'var(--red)', fontSize:12, marginTop:6 }}>{data.error}</div>}
    </div>
  }

  if (agent === 'post_analytics') {
    return <div>
      {copyBtn}
      <div style={{ display:'flex', gap:16, marginBottom:10, fontSize:12 }}>
        <span>Синхронизировано: <b style={{ color:'var(--green)' }}>{data.synced ?? 0}</b></span>
        <span>Ошибок: <b style={{ color:'var(--red)' }}>{data.failed ?? 0}</b></span>
        <span>Пропущено: <b style={{ color:'var(--faint)' }}>{data.skipped ?? 0}</b></span>
        <span>Всего: <b style={{ color:'var(--text)' }}>{data.total ?? 0}</b></span>
      </div>
      {(data.details || []).length > 0 && (
        <div>
          {data.details.map((d, i) => (
            <div key={i} style={{ padding:'4px 0', borderBottom:'1px solid var(--border)', fontSize:11 }}>
              <span style={{ color:'var(--text)' }}>{d.platform}</span>{' '}
              {d.error
                ? <span style={{ color:'var(--red)' }}>{d.error}</span>
                : <span style={{ color:'var(--green)' }}>ER {d.engagement_rate}%</span>}
            </div>
          ))}
        </div>
      )}
    </div>
  }

  return <div>{copyBtn}<pre style={{ margin:0, fontSize:11 }}>{JSON.stringify(data, null, 2)}</pre></div>
}

function AgentCard({ id, name, desc, children }) {
  const [open,    setOpen]    = useState(false) // свёрнута по умолчанию — ровная сетка
  const [result,  setResult]  = useState(null)
  const [loading, setLoading] = useState(false)
  const [error,   setError]   = useState(null)

  async function run(agent, params) {
    setLoading(true); setResult(null); setError(null)
    try {
      const data = await runAgentAPI(agent, params)
      setResult({ data, agent, params })
    } catch(e) { setError(e.message) }
    setLoading(false)
  }

  return (
    <div className={`agent-card${open ? '' : ' collapsed'}`}>
      <button className="agent-card-head agent-toggle" onClick={() => setOpen(o => !o)} aria-expanded={open}>
        <span className="agent-id-tag">{id}</span>
        <span className="agent-name">{name}</span>
        {loading && <span style={{ fontSize:11 }}>⏳</span>}
        <span className="agent-chevron">{open ? '▾' : '▸'}</span>
      </button>
      <div className="agent-desc">{desc}</div>
      {open && <>
        {typeof children === 'function' ? children(run, loading) : children}
        {error && <div className="agent-result"><span style={{ color:'var(--red)' }}>⚠️ {error}</span></div>}
        {result && (
          <div className="agent-result">
            <AgentResult data={result.data} agent={result.agent} params={result.params} />
          </div>
        )}
      </>}
    </div>
  )
}

function Sel({ id, value, onChange, children }) {
  return <select id={id} className="form-control" value={value} onChange={e=>onChange(e.target.value)} style={{ marginBottom:6 }}>{children}</select>
}
function GEO({ value, onChange }) {
  return <Sel value={value} onChange={onChange}>{['US','BR','MX','DE','PL'].map(g=><option key={g}>{g}</option>)}</Sel>
}
function Vertical({ value, onChange }) {
  return <Sel value={value} onChange={onChange}><option value="nutra">Nutra</option><option value="betting">Betting</option></Sel>
}

/* ── INDIVIDUAL AGENT FORMS ── */

function A21Card() {
  const [fmt, setFmt] = useState('hook_problem')
  const [vert, setVert] = useState('nutra')
  const [geo, setGeo] = useState('US')
  const [offer, setOffer] = useState('')
  return (
    <AgentCard id="A21" name="content_creator" desc="Генерирует before/after, хуки, UGC по Brand Voice">
      {(run, loading) => <>
        <label className="form-label">Формат</label>
        <Sel value={fmt} onChange={setFmt}>
          <option value="hook_problem">Hook + Problem</option><option value="before_after">Before / After</option>
          <option value="ugc_reaction">UGC Reaction</option><option value="series_day">Series Day</option>
          <option value="seo_article">SEO Article</option><option value="caption">Caption</option>
        </Sel>
        <label className="form-label">Вертикаль</label><Vertical value={vert} onChange={setVert} />
        <label className="form-label">GEO</label><GEO value={geo} onChange={setGeo} />
        <label className="form-label">Оффер (необязательно)</label>
        <input className="form-control" value={offer} onChange={e=>setOffer(e.target.value)} placeholder="Dr.Cash / 1win" style={{ marginBottom:8 }} />
        <button className="btn btn-primary btn-block" disabled={loading}
          onClick={() => run('content_creator', { format:fmt, vertical:vert, geo, offer })}>
          {loading ? '⏳ Работает…' : '▶ Запустить'}
        </button>
      </>}
    </AgentCard>
  )
}

function A19Card() {
  const [text, setText] = useState('')
  const [geo, setGeo] = useState('US')
  const [vert, setVert] = useState('nutra')
  return (
    <AgentCard id="A19" name="text_humanizer" desc="Stop-Slop фильтр: убирает AI-маркеры, оценивает текст 0–50">
      {(run, loading) => <>
        <label className="form-label">Текст для очистки</label>
        <textarea className="form-control" value={text} onChange={e=>setText(e.target.value)}
          placeholder="Вставь текст — получишь очищенную версию…" rows={3} style={{ marginBottom:6 }} />
        <label className="form-label">GEO</label><GEO value={geo} onChange={setGeo} />
        <label className="form-label">Вертикаль</label><Vertical value={vert} onChange={setVert} />
        <button className="btn btn-primary btn-block" disabled={loading || !text.trim()} style={{ marginTop:2 }}
          onClick={() => { if (!text.trim()) return; run('text_humanizer', { text, geo, vertical:vert }) }}>
          {loading ? '⏳ Работает…' : '▶ Запустить'}
        </button>
      </>}
    </AgentCard>
  )
}

function A20Card() {
  const [url, setUrl] = useState('')
  const [vert, setVert] = useState('nutra')
  const [geo, setGeo] = useState('US')
  return (
    <AgentCard id="A20" name="trend_scraper" desc="Анализ конкурентов по URL или поиск трендов через Firecrawl">
      {(run, loading) => <>
        <label className="form-label">URL конкурента (или пусто — поиск трендов)</label>
        <input className="form-control" value={url} onChange={e=>setUrl(e.target.value)}
          placeholder="https://competitor.com/post/…" style={{ marginBottom:6 }} />
        <label className="form-label">Вертикаль</label><Vertical value={vert} onChange={setVert} />
        <label className="form-label">GEO</label><GEO value={geo} onChange={setGeo} />
        <button className="btn btn-primary btn-block" disabled={loading} style={{ marginTop:2 }}
          onClick={() => run('trend_scraper', { url, vertical:vert, geo })}>
          {loading ? '⏳ Работает…' : '▶ Запустить'}
        </button>
      </>}
    </AgentCard>
  )
}

function A22Card() {
  const [platform, setPlatform] = useState('tiktok')
  const [vert, setVert] = useState('nutra')
  const [geo, setGeo] = useState('US')
  return (
    <AgentCard id="A22" name="ads_auditor" desc="250+ проверок. Health Score 0–100 и quick wins">
      {(run, loading) => <>
        <label className="form-label">Платформа</label>
        <Sel value={platform} onChange={setPlatform}>
          <option value="tiktok">TikTok</option><option value="meta">Meta (FB/IG)</option><option value="youtube">YouTube</option>
        </Sel>
        <label className="form-label">Вертикаль</label><Vertical value={vert} onChange={setVert} />
        <label className="form-label">GEO</label><GEO value={geo} onChange={setGeo} />
        <button className="btn btn-primary btn-block" disabled={loading} style={{ marginTop:2 }}
          onClick={() => run('ads_auditor', { platform, vertical:vert, geo, account_data:{} })}>
          {loading ? '⏳ Работает…' : '▶ Запустить аудит'}
        </button>
      </>}
    </AgentCard>
  )
}

function A23Card() {
  const [fmt, setFmt] = useState('shorts')
  const [topic, setTopic] = useState('')
  const [vert, setVert] = useState('nutra')
  const [geo, setGeo] = useState('US')
  return (
    <AgentCard id="A23" name="youtube_creator" desc="Retention-инжиниринг: Shorts/Long-form, хуки, metadata, calendar">
      {(run, loading) => <>
        <label className="form-label">Формат</label>
        <Sel value={fmt} onChange={setFmt}>
          <option value="shorts">Shorts (15–60 сек)</option><option value="long_form">Long-form</option>
          <option value="hook">5 вариантов хука</option><option value="metadata">SEO metadata</option>
          <option value="thumbnail">Thumbnail A/B</option><option value="ideate">10 идей</option>
          <option value="calendar">Месячный календарь</option><option value="repurpose">Repurpose → TikTok/IG</option>
        </Sel>
        <label className="form-label">Тема / оффер</label>
        <input className="form-control" value={topic} onChange={e=>setTopic(e.target.value)}
          placeholder="Похудение за 30 дней…" style={{ marginBottom:6 }} />
        <label className="form-label">Вертикаль</label><Vertical value={vert} onChange={setVert} />
        <label className="form-label">GEO</label><GEO value={geo} onChange={setGeo} />
        <button className="btn btn-primary btn-block" disabled={loading || !topic.trim()} style={{ marginTop:2 }}
          onClick={() => { if (!topic.trim()) return; run('youtube_creator', { format:fmt, topic, vertical:vert, geo }) }}>
          {loading ? '⏳ Работает…' : '▶ Создать'}
        </button>
      </>}
    </AgentCard>
  )
}

function A24Card() {
  const [action, setAction] = useState('query')
  const [question, setQuestion] = useState('')
  const [text, setText] = useState('')
  const [source, setSource] = useState('')

  function runA24(run) {
    const params = { action }
    if (action === 'query')  params.question = question
    if (action === 'ingest') { params.text = text; params.source_name = source || 'dashboard' }
    run('obsidian_brain', params)
  }

  return (
    <AgentCard id="A24" name="obsidian_brain" desc="Запрос к базе знаний, добавление источника или health check">
      {(run, loading) => <>
        <label className="form-label">Действие</label>
        <Sel value={action} onChange={setAction}>
          <option value="query">Задать вопрос</option>
          <option value="ingest">Добавить источник</option>
          <option value="health">Health check</option>
        </Sel>
        {action === 'query' && <>
          <label className="form-label">Вопрос</label>
          <input className="form-control" value={question} onChange={e=>setQuestion(e.target.value)}
            placeholder="Что мы знаем о прогреве TikTok?" style={{ marginBottom:6 }} />
        </>}
        {action === 'ingest' && <>
          <label className="form-label">Текст источника</label>
          <textarea className="form-control" value={text} onChange={e=>setText(e.target.value)}
            rows={3} placeholder="Вставь статью, пост, исследование…" style={{ marginBottom:6 }} />
          <label className="form-label">Название источника</label>
          <input className="form-control" value={source} onChange={e=>setSource(e.target.value)}
            placeholder="competitor-analysis-june" style={{ marginBottom:6 }} />
        </>}
        <button className="btn btn-primary btn-block" disabled={loading} style={{ marginTop:2 }}
          onClick={() => runA24(run)}>
          {loading ? '⏳ Работает…' : '▶ Запустить'}
        </button>
      </>}
    </AgentCard>
  )
}

function A25Card() {
  const [text, setText] = useState('')
  const [vert, setVert] = useState('nutra')
  const [geo, setGeo] = useState('US')
  return (
    <AgentCard id="A25" name="compliance_gate" desc="3-уровневая проверка. Блокирует медицинские и беттинг-нарушения">
      {(run, loading) => <>
        <label className="form-label">Текст для проверки</label>
        <textarea className="form-control" value={text} onChange={e=>setText(e.target.value)}
          rows={3} placeholder="Вставь текст для проверки…" style={{ marginBottom:6 }} />
        <label className="form-label">Вертикаль</label><Vertical value={vert} onChange={setVert} />
        <label className="form-label">GEO</label><GEO value={geo} onChange={setGeo} />
        <button className="btn btn-primary btn-block" disabled={loading} style={{ marginTop:2 }}
          onClick={() => run('compliance_gate', { text, vertical:vert, geo })}>
          {loading ? '⏳ Проверяет…' : '▶ Проверить'}
        </button>
      </>}
    </AgentCard>
  )
}

function A26Card() {
  const [text, setText] = useState('')
  const [platform, setPlatform] = useState('tiktok')
  const [url, setUrl] = useState('')
  const [vert, setVert] = useState('nutra')
  const [geo, setGeo] = useState('US')
  return (
    <AgentCard id="A26" name="publer_publisher" desc="TikTok / Facebook / Instagram / Pinterest через Publer. Compliance + UTM автоматически">
      {(run, loading) => <>
        <label className="form-label">Текст поста</label>
        <textarea className="form-control" value={text} onChange={e=>setText(e.target.value)}
          rows={3} placeholder="Готовый текст для публикации…" style={{ marginBottom:6 }} />
        <label className="form-label">Платформа</label>
        <Sel value={platform} onChange={setPlatform}>
          <option value="tiktok">TikTok</option><option value="facebook">Facebook</option>
          <option value="instagram">Instagram</option><option value="pinterest">Pinterest</option>
        </Sel>
        <label className="form-label">Affiliate URL</label>
        <input className="form-control" value={url} onChange={e=>setUrl(e.target.value)}
          placeholder="https://1win.com/promo/…" style={{ marginBottom:6 }} />
        <label className="form-label">Вертикаль</label><Vertical value={vert} onChange={setVert} />
        <label className="form-label">GEO</label><GEO value={geo} onChange={setGeo} />
        <div style={{ fontSize:11, color:'var(--faint)', padding:'4px 0 6px' }}>Требуется: PUBLER_API_KEY на сервере</div>
        <button className="btn btn-primary btn-block" disabled={loading}
          onClick={() => run('publer_publisher', { text, platform, affiliate_url:url, vertical:vert, geo, dry_run:true })}>
          {loading ? '⏳ Работает…' : '▶ Проверить (dry run)'}
        </button>
      </>}
    </AgentCard>
  )
}

function A27Card() {
  const [creatives, setCreatives] = useState('')
  const [vert, setVert] = useState('nutra')
  const [geo, setGeo] = useState('US')
  const [platform, setPlatform] = useState('tiktok')
  return (
    <AgentCard id="A27" name="spy_analyzer" desc="Анализ крипов конкурентов → паттерны хуков + creative brief для A21">
      {(run, loading) => <>
        <label className="form-label">Крипы конкурентов</label>
        <textarea className="form-control" value={creatives} onChange={e=>setCreatives(e.target.value)}
          rows={4} placeholder={"Описания рекламных крипов (каждый с новой строки)\n'I lost 23 lbs doing THIS one trick…'"} style={{ marginBottom:6 }} />
        <label className="form-label">Вертикаль</label><Vertical value={vert} onChange={setVert} />
        <label className="form-label">GEO</label><GEO value={geo} onChange={setGeo} />
        <label className="form-label">Платформа</label>
        <Sel value={platform} onChange={setPlatform}>
          <option value="tiktok">TikTok</option><option value="facebook">Facebook</option><option value="instagram">Instagram</option>
        </Sel>
        <button className="btn btn-primary btn-block" disabled={loading} style={{ marginTop:2 }}
          onClick={() => {
            const arr = creatives.split(/\n---\n|\n{2,}/).map(s=>s.trim()).filter(Boolean)
            run('spy_analyzer', { creatives:arr, vertical:vert, geo, platform, focus:'all' })
          }}>
          {loading ? '⏳ Анализирует…' : '▶ Анализировать крипы'}
        </button>
      </>}
    </AgentCard>
  )
}

function A28Card() {
  const [action, setAction] = useState('register')
  const [accountId, setAccountId] = useState('')
  const [geo, setGeo] = useState('US')
  const [accountType, setAccountType] = useState('new')
  const [device, setDevice] = useState('GLOBAL')
  const [proxy, setProxy] = useState('mobile')
  const [hasSim, setHasSim] = useState(false)

  function runA28(run) {
    const params = { action, account_id: accountId }
    if (action === 'register' || action === 'validate_infra') {
      params.geo = geo; params.account_type = accountType
      params.device_type = device.replace(/ .*/,''); params.proxy_type = proxy.replace(/ .*/,'')
      params.has_local_sim = hasSim
    }
    run('warmup_manager', params)
  }

  return (
    <AgentCard id="A28" name="warmup_manager" desc="14-дневный прогрев аккаунтов. Лимиты по дням, проверка GEO-инфраструктуры">
      {(run, loading) => <>
        <label className="form-label">Действие</label>
        <Sel value={action} onChange={setAction}>
          <option value="register">Зарегистрировать аккаунт</option>
          <option value="check">Проверить статус</option>
          <option value="list">Список всех аккаунтов</option>
          <option value="validate_infra">Проверить инфраструктуру</option>
        </Sel>
        <input className="form-control" value={accountId} onChange={e=>setAccountId(e.target.value)}
          placeholder="ID аккаунта (напр. tiktok_us_001)" style={{ marginBottom:6 }} />
        {(action === 'register' || action === 'validate_infra') && <>
          <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:6, marginBottom:6 }}>
            <div><label className="form-label">GEO</label><GEO value={geo} onChange={setGeo} /></div>
            <div><label className="form-label">Тип</label>
              <Sel value={accountType} onChange={setAccountType}>
                <option value="new">Новый (14 дней)</option><option value="aged">Aged (7 дней)</option>
              </Sel>
            </div>
            <div><label className="form-label">Устройство</label>
              <Sel value={device} onChange={setDevice}>
                <option value="GLOBAL">GLOBAL ✅</option><option value="US">US ✅</option>
                <option value="RU">RU ⚠️</option><option value="CN">CN ⚠️</option>
              </Sel>
            </div>
            <div><label className="form-label">Прокси</label>
              <Sel value={proxy} onChange={setProxy}>
                <option value="mobile">Mobile ✅</option><option value="residential">Residential ✅</option>
                <option value="datacenter">Datacenter ⚠️</option><option value="none">Нет прокси ❌</option>
              </Sel>
            </div>
          </div>
          <label style={{ display:'flex', alignItems:'center', gap:6, fontSize:12, color:'var(--muted)', marginBottom:6, cursor:'pointer' }}>
            <input type="checkbox" checked={hasSim} onChange={e=>setHasSim(e.target.checked)} />
            Есть US SIM/eSIM (Airalo)
          </label>
        </>}
        <button className="btn btn-primary btn-block" disabled={loading}
          onClick={() => runA28(run)}>
          {loading ? '⏳ Работает…' : '▶ Запустить'}
        </button>
      </>}
    </AgentCard>
  )
}

function A29Card() {
  const [offer, setOffer] = useState('')
  const [vert, setVert] = useState('nutra')
  const [geo, setGeo] = useState('US')
  const [billing, setBilling] = useState('COD')
  const [fmt, setFmt] = useState('story')
  const [benefits, setBenefits] = useState('')
  const [lander, setLander] = useState('')
  return (
    <AgentCard id="A29" name="prelanding_generator" desc="HTML прелендинги: quiz / story / native article / VSL · COD/Trial/SS">
      {(run, loading) => <>
        <input className="form-control" value={offer} onChange={e=>setOffer(e.target.value)}
          placeholder="Название оффера (напр. BloodSugarX)" style={{ marginBottom:6 }} />
        <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:6, marginBottom:6 }}>
          <div><label className="form-label">Вертикаль</label><Vertical value={vert} onChange={setVert} /></div>
          <div><label className="form-label">GEO</label><GEO value={geo} onChange={setGeo} /></div>
          <div><label className="form-label">Биллинг</label>
            <Sel value={billing} onChange={setBilling}>
              <option value="COD">COD (наложенный)</option><option value="Trial">Trial</option><option value="SS">SS (прямая)</option>
            </Sel>
          </div>
          <div><label className="form-label">Формат</label>
            <Sel value={fmt} onChange={setFmt}>
              <option value="story">Story</option><option value="native_article">Native Article</option>
              <option value="quiz">Quiz</option><option value="vsl">VSL</option>
            </Sel>
          </div>
        </div>
        <label className="form-label">Преимущества (по одному на строку)</label>
        <textarea className="form-control" value={benefits} onChange={e=>setBenefits(e.target.value)}
          rows={3} placeholder={"Натуральный состав\nЭффект за 30 дней\nТысячи клиентов"} style={{ marginBottom:6 }} />
        <input className="form-control" value={lander} onChange={e=>setLander(e.target.value)}
          placeholder="URL лендинга" style={{ marginBottom:8 }} />
        <button className="btn btn-primary btn-block" disabled={loading}
          onClick={() => run('prelanding_generator', {
            offer_name: offer||'Product', vertical:vert, geo, billing_model:billing, format:fmt,
            product_benefits: benefits.split('\n').map(s=>s.trim()).filter(Boolean),
            lander_url: lander||'LANDER_URL',
          })}>
          {loading ? '⏳ Генерирует…' : '▶ Генерировать прелендинг'}
        </button>
      </>}
    </AgentCard>
  )
}

function A30Card() {
  const [fmt, setFmt] = useState('ugc')
  const [hook, setHook] = useState('')
  const [story, setStory] = useState('')
  const [cta, setCta] = useState('')
  const [vert, setVert] = useState('nutra')
  const [geo, setGeo] = useState('US')
  const [avatar, setAvatar] = useState('authentic')
  const [aspect, setAspect] = useState('9:16')
  const [offerName, setOfferName] = useState('')
  const [carouselBenefits, setCarouselBenefits] = useState('')
  const [carouselStyle, setCarouselStyle] = useState('minimal')
  const [slideCount, setSlideCount] = useState(5)
  const carouselAspect = '1:1'

  function runA30(run) {
    if (fmt === 'carousel') {
      run('higgsfield_agent', {
        format:'carousel', offer_name: offerName||'Product',
        benefits: carouselBenefits.split('\n').map(s=>s.trim()).filter(Boolean),
        carousel_style: carouselStyle, slide_count: slideCount,
        aspect_ratio: carouselAspect, vertical:'white',
      })
    } else {
      run('higgsfield_agent', { format:fmt, hook, story, cta, vertical:vert, geo, avatar_style:avatar, aspect_ratio:aspect })
    }
  }

  return (
    <AgentCard id="A30" name="higgsfield_agent" desc="UGC 9:16, Shorts 15–60с, Карусели через Higgsfield AI. Требует HIGGSFIELD_API_KEY.">
      {(run, loading) => <>
        <label className="form-label">Формат</label>
        <Sel value={fmt} onChange={setFmt}>
          <option value="ugc">UGC 9:16 (TikTok / Instagram)</option>
          <option value="shorts">Shorts 15–60с</option>
          <option value="carousel">Карусель (Facebook / Instagram)</option>
        </Sel>
        {fmt !== 'carousel' ? <>
          <label className="form-label">Hook (0–3 сек)</label>
          <input className="form-control" value={hook} onChange={e=>setHook(e.target.value)}
            placeholder="Doctors HATE this woman for discovering…" style={{ marginBottom:6 }} />
          <label className="form-label">Story (3–22 сек)</label>
          <textarea className="form-control" value={story} onChange={e=>setStory(e.target.value)}
            rows={2} placeholder="Я попробовала это средство и за 30 дней…" style={{ marginBottom:6 }} />
          <label className="form-label">CTA (последние 5 сек)</label>
          <input className="form-control" value={cta} onChange={e=>setCta(e.target.value)}
            placeholder="Ссылка в bio → получи -50%" style={{ marginBottom:6 }} />
          <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:6, marginBottom:6 }}>
            <div><label className="form-label">Вертикаль</label>
              <Sel value={vert} onChange={setVert}>
                <option value="nutra">Nutra</option><option value="betting">Betting</option><option value="white">White</option>
              </Sel>
            </div>
            <div><label className="form-label">GEO</label><GEO value={geo} onChange={setGeo} /></div>
            <div><label className="form-label">Аватар</label>
              <Sel value={avatar} onChange={setAvatar}>
                <option value="authentic">Authentic</option><option value="professional">Professional</option><option value="friendly">Friendly</option>
              </Sel>
            </div>
            <div><label className="form-label">Ориентация</label>
              <Sel value={aspect} onChange={setAspect}>
                <option value="9:16">9:16 Вертикальное</option><option value="16:9">16:9 Горизонтальное</option>
              </Sel>
            </div>
          </div>
        </> : <>
          <input className="form-control" value={offerName} onChange={e=>setOfferName(e.target.value)}
            placeholder="Название оффера (BloodSugarX)" style={{ marginBottom:6 }} />
          <textarea className="form-control" value={carouselBenefits} onChange={e=>setCarouselBenefits(e.target.value)}
            rows={3} placeholder={"Снижает сахар за 14 дней\nНатуральный состав\nКлинически подтверждено"} style={{ marginBottom:6 }} />
          <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:6, marginBottom:6 }}>
            <div><label className="form-label">Стиль</label>
              <Sel value={carouselStyle} onChange={setCarouselStyle}>
                <option value="minimal">Minimal</option><option value="lifestyle">Lifestyle</option>
                <option value="testimonial">Testimonial</option><option value="edu">Edu</option>
              </Sel>
            </div>
            <div><label className="form-label">Слайдов</label>
              <Sel value={slideCount} onChange={setSlideCount}>
                {[3,4,5,6,7].map(n=><option key={n} value={n}>{n}</option>)}
              </Sel>
            </div>
          </div>
        </>}
        <div style={{ fontSize:11, color:'var(--faint)', padding:'4px 0 6px' }}>Требуется: HIGGSFIELD_API_KEY на сервере</div>
        <button className="btn btn-primary btn-block" disabled={loading} onClick={() => runA30(run)}>
          {loading ? '⏳ Генерирует…' : '▶ Генерировать'}
        </button>
      </>}
    </AgentCard>
  )
}

function splitLines(t) {
  return (t || '').split(/[\n,]+/).map(s => s.trim()).filter(Boolean)
}

function A31Card() {
  const [vert, setVert] = useState('nutra')
  return (
    <AgentCard id="A31" name="competitor_analyst" desc="Проактивный анализ хуков конкурентов из competitor_signals → тренды (дополняет A27)">
      {(run, loading) => <>
        <label className="form-label">Вертикаль</label>
        <Vertical value={vert} onChange={setVert} />
        <button className="btn btn-primary" disabled={loading}
          onClick={() => run('competitor_analyst', { vertical: vert })}>
          {loading ? 'Анализирую…' : 'Анализировать конкурентов'}
        </button>
      </>}
    </AgentCard>
  )
}

function A32Card() {
  const [vert, setVert] = useState('nutra')
  const [geo, setGeo] = useState('US')
  const [hashtags, setHashtags] = useState('')
  const [sounds, setSounds] = useState('')
  return (
    <AgentCard id="A32" name="trend_radar" desc="Ранжирует трендовые звуки/хэштеги под vertical/GEO — на чём ехать сейчас">
      {(run, loading) => <>
        <label className="form-label">Вертикаль</label><Vertical value={vert} onChange={setVert} />
        <label className="form-label">GEO</label><GEO value={geo} onChange={setGeo} />
        <label className="form-label">Хэштеги (по строке/запятой)</label>
        <textarea className="form-control" rows={3} value={hashtags} onChange={e => setHashtags(e.target.value)}
          placeholder="#glowup, #detox" style={{ marginBottom: 6 }} />
        <label className="form-label">Звуки</label>
        <textarea className="form-control" rows={2} value={sounds} onChange={e => setSounds(e.target.value)}
          placeholder="original sound - x" style={{ marginBottom: 6 }} />
        <button className="btn btn-primary" disabled={loading}
          onClick={() => run('trend_radar', { vertical: vert, geo, hashtags: splitLines(hashtags), sounds: splitLines(sounds) })}>
          {loading ? 'Анализирую…' : 'Проанализировать тренды'}
        </button>
      </>}
    </AgentCard>
  )
}

function A33Card() {
  const [vert, setVert] = useState('nutra')
  const [geo, setGeo] = useState('US')
  const [query, setQuery] = useState('')
  return (
    <AgentCard id="A33" name="competitor_scraper" desc="Авто-сбор крипов по хэштегу/ключу в competitor_signals (кормит A31). Нужен TIKTOK_SCRAPER_URL">
      {(run, loading) => <>
        <label className="form-label">Хэштег / ключ</label>
        <input className="form-control" value={query} onChange={e => setQuery(e.target.value)}
          placeholder="weightloss" style={{ marginBottom: 6 }} />
        <label className="form-label">Вертикаль</label><Vertical value={vert} onChange={setVert} />
        <label className="form-label">GEO</label><GEO value={geo} onChange={setGeo} />
        <button className="btn btn-primary" disabled={loading}
          onClick={() => { if (!query.trim()) return; run('competitor_scraper', { query: query.trim(), vertical: vert, geo }) }}>
          {loading ? 'Собираю…' : 'Собрать крипы'}
        </button>
      </>}
    </AgentCard>
  )
}

function A34Card() {
  const [videoUrl, setVideoUrl] = useState('')
  const [style, setStyle] = useState('tiktok')
  return (
    <AgentCard id="A34" name="caption_agent" desc="Стилизованные субтитры (ASS/SRT, TikTok-style) + ffmpeg burn. Нужен DEEPGRAM_API_KEY">
      {(run, loading) => <>
        <label className="form-label">URL видео</label>
        <input className="form-control" value={videoUrl} onChange={e => setVideoUrl(e.target.value)}
          placeholder="https://…/video.mp4" style={{ marginBottom: 6 }} />
        <label className="form-label">Стиль</label>
        <Sel value={style} onChange={setStyle}>{['tiktok', 'bold_yellow', 'minimal'].map(s => <option key={s}>{s}</option>)}</Sel>
        <button className="btn btn-primary" disabled={loading}
          onClick={() => { if (!videoUrl.trim()) return; run('caption_agent', { video_url: videoUrl.trim(), style }) }}>
          {loading ? 'Строю…' : 'Сделать субтитры'}
        </button>
      </>}
    </AgentCard>
  )
}

function A35Card() {
  const [text, setText] = useState('')
  const [voice, setVoice] = useState('')
  return (
    <AgentCard id="A35" name="tts_agent" desc="Озвучка faceless-видео: self-hosted TTS → ElevenLabs">
      {(run, loading) => <>
        <label className="form-label">Скрипт</label>
        <textarea className="form-control" rows={4} value={text} onChange={e => setText(e.target.value)}
          placeholder="Текст закадрового голоса…" style={{ marginBottom: 6 }} />
        <label className="form-label">Voice ID (опц.)</label>
        <input className="form-control" value={voice} onChange={e => setVoice(e.target.value)}
          placeholder="default" style={{ marginBottom: 6 }} />
        <button className="btn btn-primary" disabled={loading}
          onClick={() => { if (!text.trim()) return; run('tts_agent', { text: text.trim(), voice: voice.trim() || undefined }) }}>
          {loading ? 'Озвучиваю…' : 'Озвучить'}
        </button>
      </>}
    </AgentCard>
  )
}

function A36Card() {
  const [platform, setPlatform] = useState('')
  const [limit, setLimit] = useState(100)
  return (
    <AgentCard id="A36" name="post_analytics_agent" desc="Синхронизирует нативные метрики (impressions/reach/likes/comments/shares) с площадок для опубликованных постов">
      {(run, loading) => <>
        <label className="form-label">Платформа (пусто = все)</label>
        <Sel value={platform} onChange={setPlatform}>
          <option value="">Все платформы</option>
          {['tiktok','youtube','instagram','facebook','pinterest','threads','twitter','linkedin'].map(p => <option key={p}>{p}</option>)}
        </Sel>
        <label className="form-label">Лимит постов</label>
        <input className="form-control" type="number" value={limit} onChange={e => setLimit(Number(e.target.value) || 100)}
          style={{ marginBottom: 6 }} />
        <button className="btn btn-primary btn-block" disabled={loading}
          onClick={() => run('post_analytics', { platform: platform || undefined, limit })}>
          {loading ? '⏳ Синхронизирует…' : '↻ Синхронизировать метрики'}
        </button>
      </>}
    </AgentCard>
  )
}

export default function Launch() {
  return (
    <div className="agent-grid">
      <PipelineCard />
      <A21Card />
      <A19Card />
      <A20Card />
      <A22Card />
      <A23Card />
      <A24Card />
      <A25Card />
      <A26Card />
      <A27Card />
      <A28Card />
      <A29Card />
      <A30Card />
      <A31Card />
      <A32Card />
      <A33Card />
      <A34Card />
      <A35Card />
      <A36Card />
    </div>
  )
}
