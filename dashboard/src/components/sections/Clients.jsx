import { useEffect, useState, useRef } from 'react'
import { fetchRows, AGENTS_SERVER } from '../../api'

function parseTaskFromReply(reply, verticalName) {
  // Extract key params from orchestrator reply using simple heuristics
  const geoMatch      = reply.match(/\b(US|BR|MX|DE|PL|UK|RU)\b/i)
  const countMatch    = reply.match(/(\d+)\s*(видео|роликов|video)/i)
  const formatMatch   = reply.match(/(before.?after|ugc|vsl|quiz|story|article|shorts|carousel)/i)
  const vertMatch     = reply.match(/(betting|nutra|gambling|crypto|cod|trial)/i)

  return {
    id:          crypto.randomUUID(),
    title:       `Контент: ${verticalName}${countMatch ? ' · ' + countMatch[1] + ' видео' : ''}`,
    description: reply,
    plan:        reply,
    status:      'pending',
    createdAt:   new Date().toISOString(),
    params: {
      vertical:  vertMatch?.[1] || verticalName || '',
      geo:       geoMatch?.[1]?.toUpperCase() || '',
      count:     countMatch?.[1] || '',
      format:    formatMatch?.[1] || '',
    },
  }
}

export default function Clients({ onCreateTask }) {
  const [projects,  setProjects]  = useState([])
  const [loading,   setLoading]   = useState(true)
  const [current,   setCurrent]   = useState(null)
  const [knowledge, setKnowledge] = useState([])
  const [history,   setHistory]   = useState([])
  const [input,     setInput]     = useState('')
  const [sending,   setSending]   = useState(false)
  const [pendingTask, setPendingTask] = useState(null)
  const [cfgOpen, setCfgOpen] = useState(false)
  const logRef = useRef(null)

  useEffect(() => {
    fetchRows('vertical_configs', 'select=id,name,category,config_yaml&order=created_at.asc')
      .then(rows => { setProjects(rows); setLoading(false) })
      .catch(() => setLoading(false))
  }, [])

  async function openProject(p) {
    setCurrent(p)
    setPendingTask(null)
    setCfgOpen(false)
    const [k, h] = await Promise.all([
      fetchRows('knowledge_entries', `select=type,content,created_at&vertical=eq.${p.id}&order=created_at.desc&limit=5`),
      fetchRows('chat_messages',     `select=role,content,created_at&vertical_id=eq.${p.id}&order=created_at.asc&limit=30`),
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
    setPendingTask(null)
    try {
      const res = await fetch(`${AGENTS_SERVER}/orchestrator/chat`, {
        method:'POST', headers: {'Content-Type':'application/json'},
        body: JSON.stringify({
          vertical_id: current.id,
          message: msg,
          history: history.slice(-20).map(h => ({ role: h.role, content: h.content })),
        }),
      })
      if (res.status === 403) throw new Error('HTTP 403 — нет доступа к серверу')
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      const reply = data.reply || data.error || 'Ошибка ответа'
      setHistory(h => [...h, { role:'assistant', content: reply }])
      // Offer to create a task if reply looks like a plan
      if (reply.length > 80) setPendingTask(reply)
    } catch(e) {
      const errMsg = '⚠️ Не удалось связаться с оркестратором: ' + e.message
      setHistory(h => [...h, { role:'assistant', content: errMsg }])
    }
    setSending(false)
  }

  function createTask() {
    if (!pendingTask || !onCreateTask) return
    const task = parseTaskFromReply(pendingTask, current?.name || '')
    onCreateTask(task)
    setPendingTask(null)
    setHistory(h => [...h, {
      role: 'assistant',
      content: `✅ Задание #${task.id.slice(-6).toUpperCase()} создано и отправлено на согласование → раздел «Задания»`,
    }])
  }

  return (
    <>
      <div className="card">
        <div className="card-header">
          <div className="card-title">📂 Проекты</div>
          <span className="live-tag">live · {projects.length}</span>
        </div>
        <div style={{ padding:'14px 18px', display:'flex', gap:10, flexWrap:'wrap' }}>
          {loading && <div className="note-box">Загрузка проектов…</div>}
          {!loading && projects.length === 0 && (
            <div className="note-box">Нет проектов в vertical_configs.</div>
          )}
          {projects.map(p => (
            <div key={p.id} onClick={() => openProject(p)}
              style={{
                flex:'1', minWidth:180, cursor:'pointer', borderRadius:10, padding:'14px 16px',
                background: current?.id === p.id ? 'var(--indigo-bg)' : 'var(--surface2)',
                border: `1px solid ${current?.id === p.id ? 'var(--indigo-bd)' : 'var(--border)'}`,
                borderLeft: `3px solid ${current?.id === p.id ? 'var(--indigo)' : '#60a5fa'}`,
                transition: 'all .15s',
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
            <div className="card-header" onClick={() => setCfgOpen(o => !o)}
              style={{ cursor:'pointer', userSelect:'none' }}
              role="button" aria-expanded={cfgOpen}>
              <div className="card-title">⚙️ Конфигурация: {current.name}</div>
              <span className="ref-tag">{cfgOpen ? 'скрыть ▴' : 'справка ▾'}</span>
            </div>
            {cfgOpen && (
              <div className="card-body">
                <pre style={{ margin:0, fontSize:11, fontFamily:"'IBM Plex Mono',monospace",
                  color:'var(--muted)', whiteSpace:'pre-wrap', wordBreak:'break-word',
                  maxHeight:320, overflowY:'auto' }}>
                  {JSON.stringify(current.config_yaml, null, 2)}
                </pre>
              </div>
            )}
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
                      {knowledge.map((k,i) => (
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
            </div>
            <div className="card-body">
              <div ref={logRef} className="chat-log" style={{ marginBottom:12 }}>
                {history.length === 0 && (
                  <div style={{ textAlign:'center', padding:'20px 0', color:'var(--faint)', fontSize:13 }}>
                    Напиши задачу оркестратору, например:<br/>
                    <span style={{ color:'var(--indigo)' }}>«Создай 5 видео, вертикаль betting, гео US, формат before/after»</span>
                  </div>
                )}
                {history.map((m,i) => (
                  <div key={i} className={`chat-msg ${m.role === 'user' ? 'user' : 'assist'}`}>
                    {m.content}
                  </div>
                ))}
              </div>

              {/* Pending task banner */}
              {pendingTask && (
                <div style={{
                  marginBottom:12, padding:'12px 14px', borderRadius:8,
                  background:'var(--indigo-bg)', border:'1px solid var(--indigo-bd)',
                  display:'flex', alignItems:'center', justifyContent:'space-between', gap:12,
                }}>
                  <div style={{ fontSize:12, color:'var(--text)' }}>
                    📋 Оркестратор предложил план. Добавить в очередь заданий?
                  </div>
                  <div style={{ display:'flex', gap:8, flexShrink:0 }}>
                    <button onClick={createTask}
                      style={{ fontSize:12, padding:'6px 14px', borderRadius:6,
                        background:'var(--indigo)', border:'none', color:'#fff',
                        cursor:'pointer', fontWeight:600, whiteSpace:'nowrap' }}>
                      ✓ Создать задание
                    </button>
                    <button onClick={() => setPendingTask(null)}
                      style={{ fontSize:12, padding:'6px 10px', borderRadius:6,
                        background:'transparent', border:'1px solid var(--border)',
                        color:'var(--faint)', cursor:'pointer' }}>
                      ✕
                    </button>
                  </div>
                </div>
              )}

              <div style={{ display:'flex', gap:8 }}>
                <textarea value={input} onChange={e => setInput(e.target.value)}
                  onKeyDown={e => e.key==='Enter' && !e.shiftKey && (e.preventDefault(), send())}
                  rows={2} placeholder="Спроси оркестратора об этом проекте…"
                  className="form-control" style={{ flex:1, resize:'vertical' }} />
                <button onClick={send} disabled={sending || !input.trim()}
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
