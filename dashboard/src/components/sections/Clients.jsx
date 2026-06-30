import { useEffect, useState, useRef } from 'react'
import { fetchRows, AGENTS_SERVER } from '../../api'

function esc(s) {
  if (s == null) return ''
  return String(s).replace(/[&<>"']/g, c => ({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;' }[c]))
}

const AGENT_LABELS = {
  content_creator:'A21 content_creator', text_humanizer:'A19 text_humanizer',
  trend_scraper:'A20 trend_scraper', ads_auditor:'A22 ads_auditor',
  youtube_creator:'A23 youtube_creator', obsidian_brain:'A24 obsidian_brain',
  compliance_gate:'A25 compliance_gate', publer_publisher:'A26 publer_publisher',
  spy_analyzer:'A27 spy_analyzer', warmup_manager:'A28 warmup_manager',
  prelanding_generator:'A29 prelanding_generator', higgsfield_agent:'A30 higgsfield',
}

export default function Clients({ goToLaunch }) {
  const [projects,  setProjects]  = useState([])
  const [current,   setCurrent]   = useState(null)
  const [knowledge, setKnowledge] = useState([])
  const [history,   setHistory]   = useState([])
  const [input,     setInput]     = useState('')
  const [sending,   setSending]   = useState(false)
  const logRef = useRef(null)

  useEffect(() => {
    fetchRows('vertical_configs', 'select=id,name,category,config_yaml&order=created_at.asc').then(setProjects)
  }, [])

  async function openProject(p) {
    setCurrent(p)
    const [k, h] = await Promise.all([
      fetchRows('knowledge_entries', `select=type,content,created_at&vertical=eq.${p.id}&order=created_at.desc&limit=5`),
      fetchRows('chat_messages', `select=role,content,created_at&vertical_id=eq.${p.id}&order=created_at.asc&limit=30`),
    ])
    setKnowledge(k)
    setHistory(h)
  }

  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight
  }, [history])

  async function send() {
    if (!input.trim() || !current) return
    const msg = input.trim()
    setHistory(h => [...h, { role:'user', content:msg }])
    setInput('')
    setSending(true)
    try {
      const res = await fetch(`${AGENTS_SERVER}/orchestrator/chat`, {
        method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({ vertical_id: current.id, message: msg }),
      })
      const data = await res.json()
      setHistory(h => [...h, { role:'assistant', content: data.reply || data.error || 'Ошибка ответа' }])
    } catch(e) {
      setHistory(h => [...h, { role:'assistant', content:'⚠️ Не удалось связаться: ' + e.message }])
    }
    setSending(false)
  }

  return (
    <>
      <div className="card">
        <div className="card-header">
          <div className="card-title">📂 Проекты</div>
          <span className="live-tag">live · {projects.length}</span>
        </div>
        <div style={{ padding:'14px 18px', display:'flex', gap:10, flexWrap:'wrap' }}>
          {projects.length === 0 && <div className="note-box">Нет проектов в vertical_configs.</div>}
          {projects.map(p => (
            <div key={p.id} onClick={() => openProject(p)}
              style={{
                flex:'1', minWidth:180, cursor:'pointer', borderRadius:10, padding:'14px 16px',
                background: current?.id === p.id ? 'var(--indigo-bg)' : 'var(--surface2)',
                border: `1px solid ${current?.id === p.id ? 'var(--indigo-bd)' : 'var(--border)'}`,
                borderLeft: `3px solid ${current?.id === p.id ? 'var(--indigo)' : '#60a5fa'}`,
              }}>
              <div style={{ fontWeight:600, color:'var(--text)' }}>{p.name}</div>
              <div style={{ fontSize:11, color:'var(--faint)', marginTop:5 }}>{p.category}</div>
            </div>
          ))}
        </div>
      </div>

      {current && (
        <>
          <div className="card">
            <div className="card-header">
              <div className="card-title">⚙️ Конфигурация: {current.name}</div>
              <span className="ref-tag">справка</span>
            </div>
            <div className="card-body">
              <pre style={{ margin:0, fontSize:11, fontFamily:"'IBM Plex Mono',monospace", color:'var(--muted)', whiteSpace:'pre-wrap', wordBreak:'break-word' }}>
                {JSON.stringify(current.config_yaml, null, 2)}
              </pre>
            </div>
          </div>

          <div className="card">
            <div className="card-header">
              <div className="card-title">🧠 База знаний проекта</div>
              <span className="live-tag">live · {knowledge.length}</span>
            </div>
            <div className="card-body" style={{ paddingTop:8 }}>
              {knowledge.length === 0
                ? <div className="note-box">Пока нет записей для этого проекта.</div>
                : <table>
                    <thead><tr><th>Тип</th><th>Содержание</th><th>Дата</th></tr></thead>
                    <tbody>
                      {knowledge.map((k,i)=>(
                        <tr key={i}>
                          <td><span className="badge badge-indigo">{k.type}</span></td>
                          <td style={{ fontSize:12 }}>{(k.content||'').slice(0,90)}…</td>
                          <td className="mono">{(k.created_at||'').slice(0,10)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
              }
            </div>
          </div>

          <div className="card">
            <div className="card-header">
              <div className="card-title">💬 Чат с оркестратором</div>
              <span className="live-tag">live</span>
            </div>
            <div className="card-body">
              <div ref={logRef} className="chat-log" style={{ marginBottom:12 }}>
                {history.map((m,i) => (
                  <div key={i} className={`chat-msg ${m.role === 'user' ? 'user' : 'assist'}`}>
                    {m.content}
                  </div>
                ))}
              </div>
              <div style={{ display:'flex', gap:8 }}>
                <textarea value={input} onChange={e=>setInput(e.target.value)}
                  onKeyDown={e => e.key==='Enter' && !e.shiftKey && (e.preventDefault(), send())}
                  rows={2} placeholder="Спроси оркестратора об этом проекте…"
                  className="form-control" style={{ flex:1, resize:'vertical' }} />
                <button onClick={send} disabled={sending}
                  className="btn btn-primary" style={{ alignSelf:'flex-end', padding:'8px 18px' }}>
                  {sending ? '…' : 'Отправить'}
                </button>
              </div>
            </div>
          </div>
        </>
      )}
    </>
  )
}
