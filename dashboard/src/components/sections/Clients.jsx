import { useEffect, useState, useRef } from 'react'
import { fetchRows, insertRows, SUPABASE_URL, SUPABASE_ANON_KEY, AGENTS_SERVER } from '../../api'

// ── Supabase helpers ─────────────────────────────────────────────────────────
const SB_HEADERS = {
  apikey: SUPABASE_ANON_KEY,
  Authorization: 'Bearer ' + SUPABASE_ANON_KEY,
  'Content-Type': 'application/json',
}

async function sbPatch(table, id, body) {
  const res = await fetch(`${SUPABASE_URL}/rest/v1/${table}?id=eq.${id}`, {
    method: 'PATCH',
    headers: { ...SB_HEADERS, Prefer: 'return=representation' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

async function sbDelete(table, id) {
  const res = await fetch(`${SUPABASE_URL}/rest/v1/${table}?id=eq.${id}`, {
    method: 'DELETE',
    headers: SB_HEADERS,
  })
  if (!res.ok) throw new Error(await res.text())
}

// ── Task parser ──────────────────────────────────────────────────────────────
function parseTaskFromReply(reply, verticalName) {
  const geoMatch    = reply.match(/\b(US|BR|MX|DE|PL|UK|RU)\b/i)
  const countMatch  = reply.match(/(\d+)\s*(видео|роликов|video)/i)
  const formatMatch = reply.match(/(before.?after|ugc|vsl|quiz|story|article|shorts|carousel)/i)
  const vertMatch   = reply.match(/(betting|nutra|gambling|crypto|cod|trial)/i)
  return {
    id:          crypto.randomUUID(),
    title:       `Контент: ${verticalName}${countMatch ? ' · ' + countMatch[1] + ' видео' : ''}`,
    description: reply,
    plan:        reply,
    status:      'pending',
    createdAt:   new Date().toISOString(),
    params: {
      vertical: vertMatch?.[1] || verticalName || '',
      geo:      geoMatch?.[1]?.toUpperCase() || '',
      count:    countMatch?.[1] || '',
      format:   formatMatch?.[1] || '',
    },
  }
}

// ── Component ────────────────────────────────────────────────────────────────
export default function Projects({ onCreateTask }) {
  const [projects,    setProjects]    = useState([])
  const [loading,     setLoading]     = useState(true)
  const [current,     setCurrent]     = useState(null)
  const [knowledge,   setKnowledge]   = useState([])
  const [history,     setHistory]     = useState([])
  const [input,       setInput]       = useState('')
  const [sending,     setSending]     = useState(false)
  const [pendingTask, setPendingTask] = useState(null)
  const [cfgOpen,     setCfgOpen]     = useState(false)

  // Create
  const [newOpen,     setNewOpen]     = useState(false)
  const [newName,     setNewName]     = useState('')
  const [newCategory, setNewCategory] = useState('')
  const [creating,    setCreating]    = useState(false)

  // Rename
  const [editId,      setEditId]      = useState(null)
  const [editName,    setEditName]    = useState('')
  const [renaming,    setRenaming]    = useState(false)

  // Delete
  const [deleteId,    setDeleteId]    = useState(null)
  const [deleting,    setDeleting]    = useState(false)

  const logRef = useRef(null)

  function loadProjects() {
    setLoading(true)
    fetchRows('vertical_configs', 'select=id,name,category,config_yaml&order=created_at.asc')
      .then(rows => { setProjects(rows); setLoading(false) })
      .catch(() => setLoading(false))
  }

  useEffect(loadProjects, [])

  async function openProject(p) {
    if (editId || deleteId) return
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

  // ── CREATE ───────────────────────────────────────────────────────────────
  async function createProject() {
    if (!newName.trim()) return
    setCreating(true)
    try {
      await insertRows('vertical_configs', {
        name:        newName.trim(),
        category:    newCategory.trim() || 'general',
        config_yaml: {},
      })
      setNewName(''); setNewCategory(''); setNewOpen(false)
      loadProjects()
    } catch (e) {
      alert('Ошибка создания: ' + e.message)
    }
    setCreating(false)
  }

  // ── RENAME ───────────────────────────────────────────────────────────────
  function startRename(e, p) {
    e.stopPropagation()
    setEditId(p.id)
    setEditName(p.name)
    setDeleteId(null)
  }

  async function confirmRename(e) {
    e?.stopPropagation()
    if (!editName.trim()) { setEditId(null); return }
    setRenaming(true)
    try {
      await sbPatch('vertical_configs', editId, { name: editName.trim() })
      setProjects(ps => ps.map(p => p.id === editId ? { ...p, name: editName.trim() } : p))
      if (current?.id === editId) setCurrent(c => ({ ...c, name: editName.trim() }))
    } catch (e) {
      alert('Ошибка переименования: ' + e.message)
    }
    setEditId(null); setRenaming(false)
  }

  // ── DELETE ───────────────────────────────────────────────────────────────
  function startDelete(e, p) {
    e.stopPropagation()
    setDeleteId(p.id)
    setEditId(null)
  }

  async function confirmDelete(e) {
    e?.stopPropagation()
    setDeleting(true)
    try {
      await sbDelete('vertical_configs', deleteId)
      setProjects(ps => ps.filter(p => p.id !== deleteId))
      if (current?.id === deleteId) { setCurrent(null); setHistory([]); setKnowledge([]) }
    } catch (e) {
      alert('Ошибка удаления: ' + e.message)
    }
    setDeleteId(null); setDeleting(false)
  }

  // ── CHAT ─────────────────────────────────────────────────────────────────
  async function send() {
    if (!input.trim() || !current) return
    const msg = input.trim()
    setHistory(h => [...h, { role: 'user', content: msg }])
    setInput('')
    setSending(true)
    setPendingTask(null)
    try {
      const res = await fetch(`${AGENTS_SERVER}/orchestrator/chat`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          vertical_id: current.id,
          message:     msg,
          history:     history.slice(-20).map(h => ({ role: h.role, content: h.content })),
        }),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data  = await res.json()
      const reply = data.reply || data.error || 'Ошибка ответа'
      setHistory(h => [...h, { role: 'assistant', content: reply }])
      if (reply.length > 80) setPendingTask(reply)
    } catch (e) {
      setHistory(h => [...h, { role: 'assistant', content: '⚠️ Ошибка: ' + e.message }])
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
      content: `✅ Задание #${task.id.slice(-6).toUpperCase()} создано → раздел «Задания»`,
    }])
  }

  // ── RENDER ────────────────────────────────────────────────────────────────
  const btnBase = { fontSize: 11, padding: '4px 10px', borderRadius: 6, cursor: 'pointer', border: 'none', fontWeight: 600 }

  return (
    <>
      {/* ── Project list ── */}
      <div className="card">
        <div className="card-header">
          <div className="card-title">📂 Проекты</div>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <span className="live-tag">live · {projects.length}</span>
            <button onClick={() => { setNewOpen(o => !o); setEditId(null); setDeleteId(null) }}
              style={{ ...btnBase, background: 'var(--indigo)', color: '#fff', padding: '5px 12px' }}>
              {newOpen ? '✕ Закрыть' : '+ Новый проект'}
            </button>
          </div>
        </div>

        {/* New project form */}
        {newOpen && (
          <div style={{ padding: '12px 18px', borderBottom: '1px solid var(--border)',
            background: 'var(--indigo-bg)', display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'flex-end' }}>
            <div style={{ flex: 2, minWidth: 160 }}>
              <div style={{ fontSize: 11, color: 'var(--faint)', marginBottom: 4 }}>Название *</div>
              <input value={newName} onChange={e => setNewName(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && createProject()}
                placeholder="например: Nutra US White"
                className="form-control" style={{ fontSize: 13 }} />
            </div>
            <div style={{ flex: 1, minWidth: 120 }}>
              <div style={{ fontSize: 11, color: 'var(--faint)', marginBottom: 4 }}>Категория</div>
              <input value={newCategory} onChange={e => setNewCategory(e.target.value)}
                placeholder="nutra / betting / …"
                className="form-control" style={{ fontSize: 13 }} />
            </div>
            <button onClick={createProject} disabled={creating || !newName.trim()}
              style={{ ...btnBase, background: 'var(--indigo)', color: '#fff', padding: '8px 16px',
                opacity: (!newName.trim() || creating) ? .5 : 1 }}>
              {creating ? '…' : 'Создать'}
            </button>
          </div>
        )}

        <div style={{ padding: '14px 18px', display: 'flex', gap: 10, flexWrap: 'wrap' }}>
          {loading && <div className="note-box">Загрузка проектов…</div>}
          {!loading && projects.length === 0 && (
            <div className="note-box">Нет проектов. Создай первый ↑</div>
          )}

          {projects.map(p => {
            const isEdit   = editId   === p.id
            const isDel    = deleteId === p.id
            const isActive = current?.id === p.id

            return (
              <div key={p.id} onClick={() => openProject(p)}
                style={{
                  flex: '1', minWidth: 180, borderRadius: 10, padding: '12px 14px',
                  background: isActive ? 'var(--indigo-bg)' : 'var(--surface2)',
                  border: `1px solid ${isActive ? 'var(--indigo-bd)' : 'var(--border)'}`,
                  borderLeft: `3px solid ${isActive ? 'var(--indigo)' : '#60a5fa'}`,
                  cursor: isEdit || isDel ? 'default' : 'pointer',
                  transition: 'all .15s',
                }}>

                {/* Rename mode */}
                {isEdit ? (
                  <div onClick={e => e.stopPropagation()} style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                    <input autoFocus value={editName}
                      onChange={e => setEditName(e.target.value)}
                      onKeyDown={e => { if (e.key === 'Enter') confirmRename(); if (e.key === 'Escape') setEditId(null) }}
                      className="form-control" style={{ fontSize: 13, flex: 1, padding: '4px 8px' }} />
                    <button onClick={confirmRename} disabled={renaming}
                      style={{ ...btnBase, background: 'var(--indigo)', color: '#fff' }}>
                      {renaming ? '…' : '✓'}
                    </button>
                    <button onClick={e => { e.stopPropagation(); setEditId(null) }}
                      style={{ ...btnBase, background: 'transparent', border: '1px solid var(--border)', color: 'var(--faint)' }}>
                      ✕
                    </button>
                  </div>
                ) : isDel ? (
                  /* Delete confirm */
                  <div onClick={e => e.stopPropagation()}>
                    <div style={{ fontSize: 12, color: '#ef4444', fontWeight: 600, marginBottom: 8 }}>
                      Удалить «{p.name}»?
                    </div>
                    <div style={{ display: 'flex', gap: 6 }}>
                      <button onClick={confirmDelete} disabled={deleting}
                        style={{ ...btnBase, background: '#ef4444', color: '#fff' }}>
                        {deleting ? '…' : 'Удалить'}
                      </button>
                      <button onClick={e => { e.stopPropagation(); setDeleteId(null) }}
                        style={{ ...btnBase, background: 'transparent', border: '1px solid var(--border)', color: 'var(--faint)' }}>
                        Отмена
                      </button>
                    </div>
                  </div>
                ) : (
                  /* Normal view */
                  <>
                    <div style={{ fontWeight: 600, color: 'var(--text)', marginBottom: 4 }}>{p.name}</div>
                    <div style={{ fontSize: 11, color: 'var(--faint)', marginBottom: 8 }}>{p.category}</div>
                    <div style={{ display: 'flex', gap: 6 }}>
                      <button onClick={e => startRename(e, p)}
                        style={{ ...btnBase, background: 'transparent', border: '1px solid var(--border)',
                          color: 'var(--muted)', fontSize: 10 }}>
                        ✏️ Переименовать
                      </button>
                      <button onClick={e => startDelete(e, p)}
                        style={{ ...btnBase, background: 'transparent', border: '1px solid #ef444440',
                          color: '#ef4444', fontSize: 10 }}>
                        🗑 Удалить
                      </button>
                    </div>
                  </>
                )}
              </div>
            )
          })}
        </div>
      </div>

      {/* ── Selected project detail ── */}
      {current && (
        <>
          <div className="card">
            <div className="card-header" onClick={() => setCfgOpen(o => !o)}
              style={{ cursor: 'pointer', userSelect: 'none' }} role="button" aria-expanded={cfgOpen}>
              <div className="card-title">⚙️ Конфигурация: {current.name}</div>
              <span className="ref-tag">{cfgOpen ? 'скрыть ▴' : 'справка ▾'}</span>
            </div>
            {cfgOpen && (
              <div className="card-body">
                <pre style={{ margin: 0, fontSize: 11, fontFamily: "'IBM Plex Mono',monospace",
                  color: 'var(--muted)', whiteSpace: 'pre-wrap', wordBreak: 'break-word',
                  maxHeight: 320, overflowY: 'auto' }}>
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
            <div className="card-body" style={{ paddingTop: 8 }}>
              {knowledge.length === 0
                ? <div className="note-box">Нет записей для этого проекта.</div>
                : <table>
                    <thead><tr><th>Тип</th><th>Содержание</th><th>Дата</th></tr></thead>
                    <tbody>
                      {knowledge.map((k, i) => (
                        <tr key={i}>
                          <td><span className="badge badge-indigo">{k.type}</span></td>
                          <td style={{ fontSize: 12 }}>{(k.content || '').slice(0, 90)}…</td>
                          <td className="mono">{(k.created_at || '').slice(0, 10)}</td>
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
              <div ref={logRef} className="chat-log" style={{ marginBottom: 12 }}>
                {history.length === 0 && (
                  <div style={{ textAlign: 'center', padding: '20px 0', color: 'var(--faint)', fontSize: 13 }}>
                    Напиши задачу оркестратору, например:<br/>
                    <span style={{ color: 'var(--indigo)' }}>«Создай 5 видео, вертикаль betting, гео US, формат before/after»</span>
                  </div>
                )}
                {history.map((m, i) => (
                  <div key={i} className={`chat-msg ${m.role === 'user' ? 'user' : 'assist'}`}>
                    {m.content}
                  </div>
                ))}
              </div>

              {pendingTask && (
                <div style={{ marginBottom: 12, padding: '12px 14px', borderRadius: 8,
                  background: 'var(--indigo-bg)', border: '1px solid var(--indigo-bd)',
                  display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
                  <div style={{ fontSize: 12, color: 'var(--text)' }}>
                    📋 Оркестратор предложил план. Добавить в очередь заданий?
                  </div>
                  <div style={{ display: 'flex', gap: 8, flexShrink: 0 }}>
                    <button onClick={createTask}
                      style={{ fontSize: 12, padding: '6px 14px', borderRadius: 6,
                        background: 'var(--indigo)', border: 'none', color: '#fff',
                        cursor: 'pointer', fontWeight: 600, whiteSpace: 'nowrap' }}>
                      ✓ Создать задание
                    </button>
                    <button onClick={() => setPendingTask(null)}
                      style={{ fontSize: 12, padding: '6px 10px', borderRadius: 6,
                        background: 'transparent', border: '1px solid var(--border)',
                        color: 'var(--faint)', cursor: 'pointer' }}>
                      ✕
                    </button>
                  </div>
                </div>
              )}

              <div style={{ display: 'flex', gap: 8 }}>
                <textarea value={input} onChange={e => setInput(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && !e.shiftKey && (e.preventDefault(), send())}
                  rows={2} placeholder="Спроси оркестратора об этом проекте…"
                  className="form-control" style={{ flex: 1, resize: 'vertical' }} />
                <button onClick={send} disabled={sending || !input.trim()}
                  className="btn btn-primary" style={{ alignSelf: 'flex-end', padding: '8px 18px' }}>
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
