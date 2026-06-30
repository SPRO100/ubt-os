import { useEffect, useState } from 'react'
import { fetchN8nWorkflows, toggleN8nWorkflow, N8N_URL, getN8nApiKey } from '../../api'

// Known workflows — merged with live n8n data by name match
const KNOWN = [
  { name:'obsidian-sync',          schedule:'каждый час',          desc:'Vault → GitHub коммит и пуш' },
  { name:'account-checker',        schedule:'каждые 6ч',           desc:'Проверка ER, прокси, теневой бан' },
  { name:'health-monitor',         schedule:'каждые 60 сек',       desc:'Health-check Supabase/Redis + Telegram-алерты' },
  { name:'knowledge-synthesizer',  schedule:'ежедневно 23:45',     desc:'Claude анализирует данные → Obsidian' },
  { name:'risk-engine-monitor',    schedule:'каждые 6ч',           desc:'Risk-скоринг аккаунтов 0–100' },
  { name:'strategy-engine-weekly', schedule:'воскресенье 20:00',   desc:'Недельный стратегический бриф' },
]

function StatusBadge({ active, loading }) {
  if (loading) return <span className="badge" style={{ color:'var(--faint)', background:'var(--surface3)' }}>…</span>
  return active
    ? <span className="badge badge-green">● активен</span>
    : <span className="badge badge-red">● остановлен</span>
}

export default function Pipeline() {
  const [apiKey,    setApiKey]    = useState(getN8nApiKey)
  const [keyInput,  setKeyInput]  = useState('')
  const [workflows, setWorkflows] = useState([])
  const [error,     setError]     = useState(null)
  const [loading,   setLoading]   = useState(false)
  const [toggling,  setToggling]  = useState(null)
  const [lastSync,  setLastSync]  = useState(null)

  async function load() {
    if (!getN8nApiKey()) return
    setLoading(true)
    const { error: err, workflows: wf } = await fetchN8nWorkflows()
    setError(err)
    setWorkflows(wf)
    if (!err) setLastSync(new Date())
    setLoading(false)
  }

  useEffect(() => {
    load()
    const id = setInterval(load, 30000)
    return () => clearInterval(id)
  }, [apiKey])

  function saveKey() {
    const k = keyInput.trim()
    if (!k) return
    localStorage.setItem('n8n_api_key', k)
    setApiKey(k)
    setKeyInput('')
  }

  function clearKey() {
    localStorage.removeItem('n8n_api_key')
    setApiKey('')
    setWorkflows([])
    setError(null)
  }

  async function toggle(wf) {
    setToggling(wf.id)
    try {
      await toggleN8nWorkflow(wf.id, !wf.active)
      await load()
    } catch(e) {
      setError(e.message)
    }
    setToggling(null)
  }

  // Merge known metadata with live data
  const merged = KNOWN.map(k => {
    const live = workflows.find(w =>
      w.name.toLowerCase().includes(k.name.toLowerCase()) ||
      k.name.toLowerCase().includes(w.name.toLowerCase())
    )
    return { ...k, live, id: live?.id, active: live?.active }
  })

  // Workflows in n8n not in our known list
  const unknown = workflows.filter(w =>
    !KNOWN.some(k =>
      w.name.toLowerCase().includes(k.name.toLowerCase()) ||
      k.name.toLowerCase().includes(w.name.toLowerCase())
    )
  )

  const activeCount = workflows.filter(w => w.active).length

  return (
    <>
      {/* API Key setup */}
      {!apiKey ? (
        <div className="card">
          <div className="card-header">
            <div className="card-title">🔑 n8n API ключ</div>
          </div>
          <div className="card-body">
            <div className="note-box" style={{ marginBottom:14 }}>
              Для живых статусов нужен API ключ n8n.<br/>
              Открой <b>n8n → Settings → API → Create API Key</b>
            </div>
            <div style={{ display:'flex', gap:8 }}>
              <input
                className="form-control"
                value={keyInput}
                onChange={e => setKeyInput(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && saveKey()}
                placeholder="n8n_api_......"
                type="password"
                style={{ flex:1 }}
              />
              <button className="btn btn-primary" onClick={saveKey} disabled={!keyInput.trim()}>
                Сохранить
              </button>
              <a href={`${N8N_URL}/settings/api`} target="_blank" rel="noopener noreferrer"
                className="btn btn-outline">
                Открыть n8n →
              </a>
            </div>
          </div>
        </div>
      ) : (
        <>
          {/* Live status header */}
          <div style={{ display:'grid', gridTemplateColumns:'repeat(3,1fr)', gap:12, marginBottom:4 }}>
            <div style={{ background:'var(--surface)', border:'1px solid var(--border)', borderTop:'3px solid var(--green)', borderRadius:10, padding:'16px 20px' }}>
              <div style={{ fontSize:11, color:'var(--faint)', marginBottom:4 }}>Активных</div>
              <div style={{ fontSize:32, fontWeight:700, fontFamily:"'IBM Plex Mono',monospace", color:'var(--green)' }}>
                {loading ? '…' : activeCount}
              </div>
            </div>
            <div style={{ background:'var(--surface)', border:'1px solid var(--border)', borderTop:'3px solid var(--indigo)', borderRadius:10, padding:'16px 20px' }}>
              <div style={{ fontSize:11, color:'var(--faint)', marginBottom:4 }}>Всего воркфлоу</div>
              <div style={{ fontSize:32, fontWeight:700, fontFamily:"'IBM Plex Mono',monospace" }}>
                {loading ? '…' : workflows.length}
              </div>
            </div>
            <div style={{ background:'var(--surface)', border:'1px solid var(--border)', borderTop:'3px solid var(--faint)', borderRadius:10, padding:'16px 20px' }}>
              <div style={{ fontSize:11, color:'var(--faint)', marginBottom:4 }}>Синхронизация</div>
              <div style={{ fontSize:13, fontWeight:600, fontFamily:"'IBM Plex Mono',monospace", color:'var(--muted)', marginTop:6 }}>
                {lastSync ? lastSync.toLocaleTimeString('ru-RU', { hour:'2-digit', minute:'2-digit', second:'2-digit' }) : '—'}
              </div>
              <div style={{ fontSize:10, color:'var(--faint)' }}>обновление каждые 30с</div>
            </div>
          </div>

          {error && (
            <div className="note-box" style={{ borderColor:'var(--red)', color:'var(--red)', marginBottom:4 }}>
              ⚠️ Ошибка n8n API: {error}
            </div>
          )}

          {/* Main workflows table */}
          <div className="card">
            <div className="card-header">
              <div className="card-title">🔄 Воркфлоу</div>
              <div style={{ display:'flex', gap:8, alignItems:'center' }}>
                {loading && <span style={{ fontSize:11, color:'var(--faint)' }}>обновление…</span>}
                <button onClick={load} disabled={loading}
                  style={{ fontSize:11, padding:'3px 10px', borderRadius:6, background:'var(--surface2)',
                    border:'1px solid var(--border)', color:'var(--muted)', cursor:'pointer' }}>
                  ↻ Обновить
                </button>
                <a href={`${N8N_URL}/workflows`} target="_blank" rel="noopener noreferrer"
                  style={{ fontSize:11, padding:'3px 10px', borderRadius:6, background:'var(--indigo-bg)',
                    border:'1px solid var(--indigo-bd)', color:'var(--indigo)', textDecoration:'none' }}>
                  Открыть n8n →
                </a>
              </div>
            </div>
            <div className="card-body" style={{ paddingTop:8 }}>
              <table>
                <thead>
                  <tr>
                    <th>Воркфлоу</th>
                    <th>Расписание</th>
                    <th>Что делает</th>
                    <th>Статус</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {merged.map(w => (
                    <tr key={w.name}>
                      <td className="primary mono">{w.name}</td>
                      <td className="mono" style={{ fontSize:11 }}>{w.schedule}</td>
                      <td style={{ fontSize:12, color:'var(--muted)' }}>{w.desc}</td>
                      <td>
                        {w.live
                          ? <StatusBadge active={w.active} loading={toggling === w.id} />
                          : <span className="badge" style={{ color:'var(--faint)', background:'var(--surface3)' }}>не найден</span>
                        }
                      </td>
                      <td>
                        {w.live && (
                          <button
                            onClick={() => toggle(w.live)}
                            disabled={toggling === w.id}
                            style={{
                              fontSize:10, padding:'3px 8px', borderRadius:5, cursor:'pointer',
                              background: w.active ? '#ef444418' : '#22c55e18',
                              border: `1px solid ${w.active ? '#ef444444' : '#22c55e44'}`,
                              color: w.active ? 'var(--red)' : 'var(--green)',
                            }}>
                            {toggling === w.id ? '…' : w.active ? 'Стоп' : 'Старт'}
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}

                  {unknown.map(w => (
                    <tr key={w.id}>
                      <td className="primary mono">{w.name}</td>
                      <td className="mono" style={{ fontSize:11, color:'var(--faint)' }}>—</td>
                      <td style={{ fontSize:12, color:'var(--faint)' }}>из n8n</td>
                      <td><StatusBadge active={w.active} loading={toggling === w.id} /></td>
                      <td>
                        <button
                          onClick={() => toggle(w)}
                          disabled={toggling === w.id}
                          style={{
                            fontSize:10, padding:'3px 8px', borderRadius:5, cursor:'pointer',
                            background: w.active ? '#ef444418' : '#22c55e18',
                            border: `1px solid ${w.active ? '#ef444444' : '#22c55e44'}`,
                            color: w.active ? 'var(--red)' : 'var(--green)',
                          }}>
                          {toggling === w.id ? '…' : w.active ? 'Стоп' : 'Старт'}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Key management */}
          <div className="card">
            <div className="card-header">
              <div className="card-title">🔑 API ключ n8n</div>
              <span className="badge badge-green">● подключён</span>
            </div>
            <div className="card-body">
              <div style={{ display:'flex', gap:8, alignItems:'center' }}>
                <span style={{ fontSize:12, color:'var(--faint)', fontFamily:"'IBM Plex Mono',monospace" }}>
                  {apiKey.slice(0,8)}{'*'.repeat(Math.max(0, apiKey.length - 8))}
                </span>
                <button onClick={clearKey}
                  style={{ fontSize:11, padding:'4px 10px', borderRadius:6,
                    background:'#ef444418', border:'1px solid #ef444444',
                    color:'var(--red)', cursor:'pointer' }}>
                  Сбросить ключ
                </button>
              </div>
            </div>
          </div>
        </>
      )}
    </>
  )
}
