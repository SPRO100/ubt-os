import { useEffect, useState } from 'react'
import { postAgents, fetchRows } from '../../api'

const VERTICALS = ['nutra', 'betting']
const GEOS = ['US', 'BR', 'MX', 'DE', 'PL', 'TR']

const FIT_COLOR = { high: 'var(--green)', medium: 'var(--amber)', low: 'var(--faint)' }

function splitLines(text) {
  return text.split(/[\n,]+/).map(s => s.trim()).filter(Boolean)
}

export default function Trends() {
  const [vertical, setVertical] = useState('nutra')
  const [geo, setGeo] = useState('US')

  // Trend Radar
  const [hashtags, setHashtags] = useState('')
  const [sounds, setSounds] = useState('')
  const [radar, setRadar] = useState(null)
  const [radarBusy, setRadarBusy] = useState(false)
  const [radarErr, setRadarErr] = useState('')

  // Competitor scrape
  const [query, setQuery] = useState('')
  const [signals, setSignals] = useState([])
  const [scrapeBusy, setScrapeBusy] = useState(false)
  const [scrapeMsg, setScrapeMsg] = useState('')

  async function loadSignals() {
    const rows = await fetchRows('competitor_signals',
      'select=platform,title,account_name,views,er,video_url,scraped_at&order=scraped_at.desc&limit=25')
    setSignals(rows || [])
  }
  useEffect(() => { loadSignals() }, [])

  async function runRadar() {
    setRadarBusy(true); setRadarErr(''); setRadar(null)
    try {
      const data = await postAgents('/trends/radar', {
        vertical, geo,
        hashtags: splitLines(hashtags),
        sounds: splitLines(sounds),
      })
      if (data.error) setRadarErr(data.error)
      else setRadar(data)
    } catch (e) { setRadarErr(e.message) }
    setRadarBusy(false)
  }

  async function runScrape() {
    if (!query.trim()) { setScrapeMsg('❌ Укажи хэштег или ключ'); return }
    setScrapeBusy(true); setScrapeMsg('Собираю крипы…')
    try {
      const data = await postAgents('/competitor/scrape', { query: query.trim(), vertical, geo })
      if (data.error) setScrapeMsg('❌ ' + data.error)
      else { setScrapeMsg(`✅ Собрано ${data.scraped}, записано ${data.inserted}`); await loadSignals() }
    } catch (e) { setScrapeMsg('❌ ' + e.message) }
    setScrapeBusy(false)
  }

  return (
    <>
      {/* Общие настройки */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 14, flexWrap: 'wrap' }}>
        <select className="form-control" style={{ maxWidth: 160 }} value={vertical} onChange={e => setVertical(e.target.value)}>
          {VERTICALS.map(v => <option key={v} value={v}>{v}</option>)}
        </select>
        <select className="form-control" style={{ maxWidth: 120 }} value={geo} onChange={e => setGeo(e.target.value)}>
          {GEOS.map(g => <option key={g} value={g}>{g}</option>)}
        </select>
      </div>

      {/* Trend Radar (A32) */}
      <div className="card">
        <div className="card-header">
          <div className="card-title">📡 Trend Radar <span className="ref-tag">A32</span></div>
        </div>
        <div className="card-body">
          <div className="note-box" style={{ marginBottom: 12 }}>
            Вставь трендовые хэштеги и звуки (по одному в строке) — агент проранжирует их под {vertical}/{geo}
            и скажет, на чём ехать. Пусто + заданный <code>TREND_SOURCE_URL</code> → возьмёт из источника.
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
            <div>
              <label className="form-label">Хэштеги</label>
              <textarea className="form-control" rows={5} value={hashtags} onChange={e => setHashtags(e.target.value)}
                placeholder={'#glowup\n#weightloss\n#detox'} />
            </div>
            <div>
              <label className="form-label">Звуки</label>
              <textarea className="form-control" rows={5} value={sounds} onChange={e => setSounds(e.target.value)}
                placeholder={'original sound - creator\ntrending beat 2026'} />
            </div>
          </div>
          <div style={{ marginTop: 10, display: 'flex', gap: 10, alignItems: 'center' }}>
            <button className="btn btn-primary" onClick={runRadar} disabled={radarBusy}>
              {radarBusy ? 'Анализирую…' : 'Проанализировать'}
            </button>
            {radarErr && <span style={{ color: 'var(--red)', fontSize: 12 }}>⚠️ {radarErr}</span>}
          </div>

          {radar && (
            <div style={{ marginTop: 14 }}>
              {radar.top_pick && (
                <div className="note-box" style={{ borderColor: 'var(--green)', color: 'var(--text)', marginBottom: 10 }}>
                  🎯 <b>Взять первым:</b> {radar.top_pick}
                </div>
              )}
              <table>
                <thead><tr><th>Тип</th><th>Название</th><th>Рост</th><th>Fit</th><th>Стадия</th><th>Как обыграть</th></tr></thead>
                <tbody>
                  {(radar.ranked || []).map((r, i) => (
                    <tr key={i}>
                      <td><span className="badge badge-indigo">{r.kind}</span></td>
                      <td className="primary mono">{r.name}</td>
                      <td className="mono">{r.growth_pct ? `${r.growth_pct}%` : '—'}</td>
                      <td style={{ color: FIT_COLOR[r.fit] || 'var(--faint)', fontWeight: 600 }}>{r.fit || '—'}</td>
                      <td style={{ fontSize: 12 }}>{r.stage || '—'}</td>
                      <td style={{ fontSize: 12, color: 'var(--muted)' }}>{r.recommendation || ''}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {(radar.avoid || []).length > 0 && (
                <div style={{ marginTop: 8, fontSize: 12, color: 'var(--faint)' }}>
                  🚫 Избегать: {radar.avoid.join(' · ')}
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Competitor feed (A33 → A31) */}
      <div className="card">
        <div className="card-header">
          <div className="card-title">🕵️ Крипы конкурентов <span className="ref-tag">A33 → A31</span></div>
          <span className="live-tag">live · {signals.length}</span>
        </div>
        <div className="card-body">
          <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
            <input className="form-control" style={{ flex: 1 }} value={query} onChange={e => setQuery(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && runScrape()} placeholder="хэштег или ключ, напр. weightloss" />
            <button className="btn btn-primary" onClick={runScrape} disabled={scrapeBusy}>
              {scrapeBusy ? 'Собираю…' : 'Собрать крипы'}
            </button>
          </div>
          {scrapeMsg && <div style={{ fontSize: 12, marginBottom: 10, color: 'var(--muted)' }}>{scrapeMsg}</div>}

          {signals.length === 0 ? (
            <div className="note-box">Пока нет собранных крипов. Задай <code>TIKTOK_SCRAPER_URL</code> и запусти сбор.</div>
          ) : (
            <table>
              <thead><tr><th>Платформа</th><th>Аккаунт</th><th>Заголовок</th><th>Views</th><th>ER</th><th></th></tr></thead>
              <tbody>
                {signals.map((s, i) => (
                  <tr key={i}>
                    <td><span className="badge badge-muted">{s.platform}</span></td>
                    <td className="mono" style={{ fontSize: 12 }}>{s.account_name || '—'}</td>
                    <td style={{ fontSize: 12, maxWidth: 320, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{s.title || '—'}</td>
                    <td className="mono">{(s.views || 0).toLocaleString('ru')}</td>
                    <td className="mono">{s.er ? `${(s.er * 100).toFixed(1)}%` : '—'}</td>
                    <td>{s.video_url && <a href={s.video_url} target="_blank" rel="noreferrer" style={{ color: 'var(--indigo)', fontSize: 12 }}>открыть →</a>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </>
  )
}
