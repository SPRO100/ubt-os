import { useEffect, useRef, useState } from 'react'
import { fetchRows, insertRows, AGENTS_SERVER, agentsHeaders } from '../../api'
import CollapsibleCard from '../CollapsibleCard'

const PLATFORMS_TABS = [
  { id: 'all',       label: 'Все',       color: 'var(--muted)' },
  { id: 'tiktok',    label: 'TikTok',    color: 'var(--red)' },
  { id: 'facebook',  label: 'Facebook',  color: 'var(--indigo)' },
  { id: 'instagram', label: 'Instagram', color: 'var(--pink)' },
  { id: 'pinterest', label: 'Pinterest', color: '#e60023' },
]

const WARMUP_ROWS = [
  ['1',   'Скролль FYP 20–30 мин. Только просмотры.',             'Просмотр ленты, лайки (10–15). Без постов.'],
  ['2–3', 'Лайки (30), подписки (10), 2 комментария. Без постов.','Лайки (20–30), репосты. 1 нейтральный пост.'],
  ['4–5', 'Первый НЕЙТРАЛЬНЫЙ пост (не по офферу).',              '1–2 поста по нише без CTA.'],
  ['6–7', 'Нишевый пост без прямого CTA.',                        'Первый CTA-пост. Facebook Pixel.'],
  ['8+',  'Полноценная публикация через A26 (Publer).',           'Регулярные посты с аффилиат-ссылками.'],
]

export default function Accounts() {
  const [accounts, setAccounts] = useState([])
  const [filter,   setFilter]   = useState('all')
  const [tab,      setTab]      = useState('single') // 'single' | 'bulk' | 'file'
  const [msg,      setMsg]      = useState('')
  const [bulkMsg,  setBulkMsg]  = useState('')
  const [bulkProg, setBulkProg] = useState('')

  // single form
  const [acctId,   setAcctId]   = useState('')
  const [platform, setPlatform] = useState('tiktok')
  const [proxy,    setProxy]    = useState('')
  const [publer,   setPubler]   = useState('')
  const [geo,      setGeo]      = useState('US')
  const [acctType, setAcctType] = useState('aged')
  const [doWarmup, setDoWarmup] = useState(true)

  // bulk CSV
  const [bulkCsv,    setBulkCsv]    = useState('')
  const [bulkWarmup, setBulkWarmup] = useState(true)

  // file import
  const fileRef = useRef(null)
  const [filePlatform, setFilePlatform] = useState('')   // hint (empty = auto)
  const [fileWarmup,   setFileWarmup]   = useState(true)
  const [fileMsg,      setFileMsg]      = useState('')
  const [fileParsed,   setFileParsed]   = useState(null) // { accounts, errors, raw_lines, parsed }
  const [fileImporting, setFileImporting] = useState(false)

  const load = async () => {
    const rows = await fetchRows('accounts', 'select=id,platform,status,proxy,publer_profile_id,created_at&order=created_at.desc&limit=50')
    setAccounts(rows)
  }

  useEffect(() => { load() }, [])

  const visible = filter === 'all' ? accounts : accounts.filter(a => a.platform === filter)

  async function addAccount() {
    if (!acctId.trim()) { setMsg('❌ Укажи ID аккаунта'); return }
    setMsg('Сохраняю…')
    try {
      await insertRows('accounts', { id: acctId, platform, status: 'new', proxy: proxy || null, publer_profile_id: publer || null })
      if (doWarmup) {
        setMsg('Регистрирую в A28…')
        try {
          const wr = await fetch(`${AGENTS_SERVER}/agents/run`, {
            method:'POST', headers: agentsHeaders({'Content-Type':'application/json'}),
            body: JSON.stringify({ agent:'warmup_manager', params:{ action:'register', account_id:acctId, geo, account_type:acctType, platform, proxy_type: proxy ? proxy.split(':')[0] : 'none' } }),
          })
          if (!wr.ok) throw new Error(`HTTP ${wr.status}`)
          setMsg('✅ Добавлен + прогрев A28 запущен')
        } catch(we) {
          setMsg(`✅ Добавлен (A28 недоступен: ${we.message})`)
        }
      } else {
        setMsg('✅ Добавлен')
      }
      setAcctId(''); setProxy(''); setPubler('')
      await load()
    } catch(e) { setMsg('❌ ' + e.message) }
  }

  async function bulkImport() {
    const raw = bulkCsv.trim()
    if (!raw) { setBulkMsg('❌ Вставь данные'); return }
    const VALID_PLATFORMS = ['tiktok','facebook','instagram','pinterest']
    const VALID_GEOS = ['US','BR','MX','DE','PL','TR','IN','NG']
    const lines = raw.split('\n').map(l => l.trim()).filter(l => l && !l.startsWith('#'))
    const records = []; const errors = []
    lines.forEach((line, i) => {
      const [id='',pl='',geo='US',prx='',pub='',type='aged'] = line.split(',').map(p => p.trim())
      if (!id) { errors.push(`Строка ${i+1}: пустой ID`); return }
      if (!VALID_PLATFORMS.includes(pl.toLowerCase())) { errors.push(`Строка ${i+1}: неверная платформа "${pl}"`); return }
      records.push({ id, platform:pl.toLowerCase(), geo: VALID_GEOS.includes(geo.toUpperCase()) ? geo.toUpperCase() : 'US', proxy: prx||null, publer_profile_id: pub||null, account_type: type||'aged', status:'new' })
    })
    if (errors.length) setBulkProg(errors.join('\n'))
    if (!records.length) { setBulkMsg('❌ Нет корректных строк'); return }
    setBulkMsg(`Загружаю ${records.length} аккаунтов…`)
    try {
      await insertRows('accounts', records, 'return=minimal,resolution=ignore-duplicates')
      setBulkMsg(`✅ Загружено ${records.length} аккаунтов`)
      if (bulkWarmup) {
        setBulkProg(`A28 прогрев: 0/${records.length}`)
        let done = 0
        for (const r of records) {
          try {
            const wr = await fetch(`${AGENTS_SERVER}/agents/run`, { method:'POST', headers: agentsHeaders({'Content-Type':'application/json'}),
              body: JSON.stringify({ agent:'warmup_manager', params:{ action:'register', account_id:r.id, geo:r.geo, account_type:r.account_type, platform:r.platform, proxy_type: r.proxy ? r.proxy.split(':')[0] : 'none' } }) })
            if (!wr.ok) throw new Error(`HTTP ${wr.status}`)
          } catch(we) { setBulkProg(p => p + ` (A28 err: ${we.message})`) }
          done++
          setBulkProg(`A28 прогрев: ${done}/${records.length}`)
        }
        setBulkMsg(`✅ ${records.length} аккаунтов + прогрев A28 запущен`)
        setBulkProg('')
      }
      setBulkCsv(''); await load()
    } catch(e) { setBulkMsg('❌ ' + e.message) }
  }

  async function fileParseAndPreview() {
    const files = fileRef.current?.files
    if (!files || !files.length) { setFileMsg('❌ Выбери файл'); return }
    const file = files[0]
    if (file.size > 10 * 1024 * 1024) { setFileMsg('❌ Файл > 10 МБ'); return }
    setFileMsg('Читаю файл…')
    setFileParsed(null)
    try {
      const buf = await file.arrayBuffer()
      const bytes = new Uint8Array(buf)
      let b64 = ''
      const chunk = 8192
      for (let i = 0; i < bytes.length; i += chunk) {
        b64 += String.fromCharCode(...bytes.subarray(i, i + chunk))
      }
      b64 = btoa(b64)
      const token = localStorage.getItem('agents_api_token') || ''
      const res = await fetch(`${AGENTS_SERVER}/accounts/parse-file`, {
        method: 'POST',
        headers: agentsHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ filename: file.name, content: b64, platform: filePlatform || null }),
      })
      const data = await res.json()
      if (data.error) { setFileMsg('❌ ' + data.error); return }
      setFileParsed(data)
      setFileMsg(`Распознано ${data.parsed} из ${data.raw_lines} строк`)
    } catch(e) { setFileMsg('❌ ' + e.message) }
  }

  async function fileDoImport() {
    if (!fileParsed?.accounts?.length) return
    setFileImporting(true)
    setFileMsg(`Загружаю ${fileParsed.accounts.length} аккаунтов…`)
    try {
      await insertRows('accounts', fileParsed.accounts, 'return=minimal,resolution=ignore-duplicates')
      setFileMsg(`✅ Загружено ${fileParsed.accounts.length} аккаунтов`)
      if (fileWarmup) {
        let done = 0
        for (const r of fileParsed.accounts) {
          try {
            const wr = await fetch(`${AGENTS_SERVER}/agents/run`, {
              method: 'POST', headers: agentsHeaders({ 'Content-Type': 'application/json' }),
              body: JSON.stringify({ agent: 'warmup_manager', params: {
                action: 'register', account_id: r.id, geo: r.geo,
                account_type: r.account_type, platform: r.platform,
                proxy_type: r.proxy ? r.proxy.split(':')[0] : 'none',
              }}),
            })
            if (!wr.ok) throw new Error(`HTTP ${wr.status}`)
          } catch(we) { /* продолжаем */ }
          done++
          if (done % 10 === 0) setFileMsg(`A28 прогрев: ${done}/${fileParsed.accounts.length}`)
        }
        setFileMsg(`✅ ${fileParsed.accounts.length} аккаунтов + прогрев A28 запущен`)
      }
      setFileParsed(null)
      if (fileRef.current) fileRef.current.value = ''
      await load()
    } catch(e) { setFileMsg('❌ ' + e.message) }
    setFileImporting(false)
  }

  const byCounts = id => accounts.filter(a => a.platform === id).length

  return (
    <>
      {/* Platform filter tabs */}
      <div style={{ display:'flex', gap:8, marginBottom:14, flexWrap:'wrap' }}>
        {PLATFORMS_TABS.map(t => (
          <button key={t.id} onClick={() => setFilter(t.id)}
            style={{
              padding:'6px 16px', borderRadius:8, cursor:'pointer', fontFamily:'inherit', fontSize:12,
              border: `1px solid ${filter===t.id ? t.color : 'var(--border2)'}`,
              background: filter===t.id ? `${t.color}1a` : 'transparent',
              color: filter===t.id ? t.color : 'var(--faint)',
            }}>
            {t.label} <span style={{ opacity:.6, fontSize:10 }}>{t.id==='all' ? accounts.length : byCounts(t.id)}</span>
          </button>
        ))}
      </div>

      {/* Accounts table */}
      <div className="card">
        <div className="card-header">
          <div className="card-title">Аккаунты</div>
          <span className="live-tag">live · {visible.length}</span>
        </div>
        <div className="card-body" style={{ paddingTop: 8 }}>
          {visible.length === 0 ? (
            <div className="note-box" style={{ padding:'8px 0' }}>Нет аккаунтов — добавь через форму ниже.</div>
          ) : (
            <table>
              <thead>
                <tr><th>ID</th><th>Платформа</th><th>Статус</th><th>Прокси</th><th>Publer ID</th><th>Добавлен</th></tr>
              </thead>
              <tbody>
                {visible.map(a => (
                  <tr key={a.id}>
                    <td className="primary mono">{a.id}</td>
                    <td>
                      <span className="badge badge-indigo">{a.platform}</span>
                    </td>
                    <td>
                      <span className={`badge ${a.status === 'warming_up' ? 'badge-amber' : a.status === 'ready' ? 'badge-green' : a.status === 'banned' ? 'badge-red' : 'badge-muted'}`}>
                        {a.status}
                      </span>
                    </td>
                    <td className="mono">{a.proxy || '—'}</td>
                    <td className="mono">{a.publer_profile_id || '—'}</td>
                    <td className="mono">{(a.created_at || '').slice(0,10)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {/* Warmup protocol */}
      <CollapsibleCard title="🔥 Протокол прогрева (aged аккаунты)" tag="A28 WarmupManager" count={WARMUP_ROWS.length}>
        <table>
          <thead><tr><th>День</th><th>TikTok (aged, 7 дней)</th><th>Facebook (aged, 5 дней)</th></tr></thead>
          <tbody>
            {WARMUP_ROWS.map(([d,tt,fb]) => (
              <tr key={d}>
                <td className="primary mono">{d}</td>
                <td>{tt}</td>
                <td>{fb}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </CollapsibleCard>

      {/* Add account form */}
      <div className="card">
        <div className="card-header">
          <div className="card-title">➕ Добавить аккаунты</div>
          <div style={{ display:'flex', gap:6 }}>
            {[['single','Одиночный'],['bulk','CSV'],['file','Файл / Архив']].map(([t,label]) => (
              <button key={t} onClick={() => setTab(t)}
                className={`btn btn-outline${tab===t?' active':''}`}
                style={{ padding:'4px 12px', fontSize:11 }}>
                {label}
              </button>
            ))}
          </div>
        </div>
        <div className="card-body">

          {tab === 'single' && (
            <>
              <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:10, marginBottom:10 }}>
                {[
                  ['ID аккаунта', <input key="acctId" className="form-control" value={acctId} onChange={e=>setAcctId(e.target.value)} placeholder="tiktok_us_001" />],
                  ['Платформа', <select key="platform" className="form-control" value={platform} onChange={e=>setPlatform(e.target.value)}>
                    <option value="tiktok">TikTok</option><option value="facebook">Facebook</option>
                    <option value="instagram">Instagram</option><option value="pinterest">Pinterest</option>
                  </select>],
                  ['Прокси', <input key="proxy" className="form-control" value={proxy} onChange={e=>setProxy(e.target.value)} placeholder="mobile:iproyal:us-pool" />],
                  ['Publer Profile ID', <input key="publer" className="form-control" value={publer} onChange={e=>setPubler(e.target.value)} placeholder="123456789" />],
                  ['GEO', <select key="geo" className="form-control" value={geo} onChange={e=>setGeo(e.target.value)}>
                    {['US','BR','MX','DE','PL'].map(g=><option key={g}>{g}</option>)}
                  </select>],
                  ['Тип аккаунта', <select key="acctType" className="form-control" value={acctType} onChange={e=>setAcctType(e.target.value)}>
                    <option value="aged">Aged (купленный)</option><option value="new">Новый</option>
                  </select>],
                ].map(([label, ctrl]) => (
                  <div key={label}><label className="form-label">{label}</label>{ctrl}</div>
                ))}
              </div>
              <div style={{ display:'flex', gap:10, alignItems:'center', flexWrap:'wrap' }}>
                <button className="btn btn-primary" onClick={addAccount}>+ Добавить аккаунт</button>
                <label style={{ display:'flex', alignItems:'center', gap:6, fontSize:12, color:'var(--muted)', cursor:'pointer' }}>
                  <input type="checkbox" checked={doWarmup} onChange={e=>setDoWarmup(e.target.checked)} />
                  Запустить прогрев A28 сразу
                </label>
                {msg && <span style={{ fontSize:12, color: msg.startsWith('✅') ? 'var(--green)' : msg.startsWith('❌') ? 'var(--red)' : 'var(--faint)' }}>{msg}</span>}
              </div>
            </>
          )}

          {tab === 'bulk' && (
            <>
              <div style={{ fontSize:11, color:'var(--faint)', marginBottom:8 }}>
                Формат: <code style={{ background:'var(--surface2)', padding:'1px 5px', borderRadius:3, fontFamily:"'IBM Plex Mono',monospace" }}>id,platform,geo,proxy,publer_id,type</code><br/>
                Платформы: tiktok / facebook / instagram / pinterest · GEO: US BR MX DE PL · Тип: aged / new
              </div>
              <div style={{ background:'var(--surface2)', border:'1px solid var(--border)', borderRadius:8, padding:'8px 12px', marginBottom:8, fontSize:11, color:'var(--muted)', fontFamily:"'IBM Plex Mono',monospace", lineHeight:1.8 }}>
                tiktok_br_001,tiktok,BR,mobile:iproyal:br-pool,111111,aged<br/>
                fb_us_002,facebook,US,,222222,aged<br/>
                ig_de_003,instagram,DE,,,new
              </div>
              <textarea className="form-control" rows={6} value={bulkCsv} onChange={e=>setBulkCsv(e.target.value)}
                placeholder="Вставь аккаунты (по одному в строке)…" style={{ fontFamily:"'IBM Plex Mono',monospace", marginBottom:8 }} />
              <div style={{ display:'flex', gap:10, alignItems:'center', flexWrap:'wrap' }}>
                <button className="btn btn-primary" onClick={bulkImport}>⬆ Импортировать всё</button>
                <label style={{ display:'flex', alignItems:'center', gap:6, fontSize:12, color:'var(--muted)', cursor:'pointer' }}>
                  <input type="checkbox" checked={bulkWarmup} onChange={e=>setBulkWarmup(e.target.checked)} />
                  Запустить прогрев A28 для всех
                </label>
                {bulkMsg && <span style={{ fontSize:12, color: bulkMsg.startsWith('✅') ? 'var(--green)' : bulkMsg.startsWith('❌') ? 'var(--red)' : 'var(--faint)' }}>{bulkMsg}</span>}
              </div>
              {bulkProg && <div style={{ marginTop:8, fontSize:11, color:'var(--faint)' }}>{bulkProg}</div>}
            </>
          )}

          {tab === 'file' && (
            <>
              <div style={{ fontSize:11, color:'var(--faint)', marginBottom:10, lineHeight:1.7 }}>
                Поддерживаемые форматы: <b>.txt</b>, <b>.csv</b>, <b>.zip</b> (до 10 МБ).<br/>
                Авто-определение: формат продавца <code style={{ background:'var(--surface2)', padding:'1px 4px', borderRadius:3, fontFamily:"'IBM Plex Mono',monospace" }}>login:password:email:proxy</code>,
                стандартный CSV <code style={{ background:'var(--surface2)', padding:'1px 4px', borderRadius:3, fontFamily:"'IBM Plex Mono',monospace" }}>id,platform,geo,proxy</code>,
                разделители: , | ; \t :<br/>
                В ZIP — все .txt/.csv файлы обрабатываются; платформа берётся из имени файла (tiktok_*.txt).
              </div>
              <div style={{ display:'grid', gridTemplateColumns:'1fr auto', gap:10, alignItems:'end', marginBottom:10 }}>
                <div>
                  <label className="form-label">Файл (.txt / .csv / .zip)</label>
                  <input ref={fileRef} type="file" accept=".txt,.csv,.zip"
                    className="form-control" style={{ cursor:'pointer' }}
                    onChange={() => { setFileParsed(null); setFileMsg('') }} />
                </div>
                <div>
                  <label className="form-label">Платформа (если не авто)</label>
                  <select className="form-control" value={filePlatform} onChange={e => setFilePlatform(e.target.value)}>
                    <option value="">— авто из файла —</option>
                    <option value="tiktok">TikTok</option>
                    <option value="facebook">Facebook</option>
                    <option value="instagram">Instagram</option>
                    <option value="pinterest">Pinterest</option>
                  </select>
                </div>
              </div>
              <div style={{ display:'flex', gap:10, alignItems:'center', flexWrap:'wrap', marginBottom:10 }}>
                <button className="btn btn-outline" onClick={fileParseAndPreview}>
                  🔍 Распознать файл
                </button>
                <label style={{ display:'flex', alignItems:'center', gap:6, fontSize:12, color:'var(--muted)', cursor:'pointer' }}>
                  <input type="checkbox" checked={fileWarmup} onChange={e => setFileWarmup(e.target.checked)} />
                  Прогрев A28 после импорта
                </label>
                {fileMsg && (
                  <span style={{ fontSize:12, color: fileMsg.startsWith('✅') ? 'var(--green)' : fileMsg.startsWith('❌') ? 'var(--red)' : 'var(--faint)' }}>
                    {fileMsg}
                  </span>
                )}
              </div>

              {fileParsed && fileParsed.accounts.length > 0 && (
                <div style={{ marginTop:4 }}>
                  <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:6 }}>
                    <span style={{ fontSize:12, color:'var(--muted)' }}>
                      Предпросмотр (первые {Math.min(20, fileParsed.accounts.length)} из {fileParsed.accounts.length}):
                    </span>
                    <button className="btn btn-primary" onClick={fileDoImport} disabled={fileImporting}>
                      {fileImporting ? 'Импортирую…' : `⬆ Импортировать ${fileParsed.accounts.length} аккаунтов`}
                    </button>
                  </div>
                  <div style={{ overflowX:'auto', borderRadius:8, border:'1px solid var(--border)' }}>
                    <table style={{ minWidth:600 }}>
                      <thead>
                        <tr><th>ID</th><th>Платформа</th><th>GEO</th><th>Прокси</th><th>Тип</th></tr>
                      </thead>
                      <tbody>
                        {fileParsed.accounts.slice(0, 20).map((a, i) => (
                          <tr key={i}>
                            <td className="primary mono" style={{ maxWidth:180, overflow:'hidden', textOverflow:'ellipsis' }}>{a.id}</td>
                            <td><span className="badge badge-indigo">{a.platform}</span></td>
                            <td className="mono">{a.geo}</td>
                            <td className="mono" style={{ maxWidth:160, overflow:'hidden', textOverflow:'ellipsis' }}>{a.proxy || '—'}</td>
                            <td><span className="badge badge-muted">{a.account_type}</span></td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  {fileParsed.errors.length > 0 && (
                    <div style={{ marginTop:8, fontSize:11, color:'var(--amber)', maxHeight:80, overflowY:'auto', lineHeight:1.6 }}>
                      {fileParsed.errors.map((e, i) => <div key={i}>{e}</div>)}
                    </div>
                  )}
                </div>
              )}
            </>
          )}
        </div>
      </div>

      {/* Alert thresholds */}
      <CollapsibleCard title="⚠️ Пороги тревоги Account Checker" tag="A14" count={4}>
        <table>
          <thead><tr><th>Метрика</th><th>Действие</th></tr></thead>
          <tbody>
            {[['ER < 2%','Алерт в Telegram'],['ER < 1%','Стоп публикаций + замена прокси'],['Бан зафиксирован','Запись в Knowledge Base'],['Proxy timeout','Автосмена прокси (IPRoyal)']].map(([m,a])=>(
              <tr key={m}><td className="primary">{m}</td><td>{a}</td></tr>
            ))}
          </tbody>
        </table>
      </CollapsibleCard>
    </>
  )
}
