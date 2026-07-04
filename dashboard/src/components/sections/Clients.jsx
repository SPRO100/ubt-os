import { useEffect, useState, useRef } from 'react'
import { fetchRows, insertRows, postAgents, SUPABASE_URL, SUPABASE_ANON_KEY, AGENTS_SERVER } from '../../api'
import CollapsibleCard from '../CollapsibleCard'
import { deriveVertical } from '../../lib/vertical'

const VIDEO_STATUS_META = {
  ready:      { label: '✅ Готово',    color: 'var(--green)' },
  queued:     { label: '⏳ В очереди',  color: 'var(--amber)' },
  generating: { label: '🎬 Генерация', color: 'var(--indigo)' },
  failed:     { label: '❌ Ошибка',    color: 'var(--red)' },
  expired:    { label: '⌛ Истекло',   color: 'var(--faint)' },
}

// Копии живут 24ч (COPY_TTL_HOURS в video_uniqualizer.py) — показываем
// оставшееся время или момент истечения как аудит-след.
function expiryLabel(v) {
  if (!v.expires_at) return null
  const expires = new Date(v.expires_at)
  if (v.status === 'expired') {
    return `истекло ${expires.toLocaleString('ru-RU', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })}`
  }
  const hoursLeft = Math.max(0, Math.round((expires - new Date()) / 3600000))
  return `истекает через ${hoursLeft}ч`
}

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

function parseTaskFromReply(reply, verticalName) {
  const geoMatch    = reply.match(/\b(US|BR|MX|DE|PL|UK|RU)\b/i)
  const countMatch  = reply.match(/(\d+)\s*(видео|роликов|video)/i)
  const formatMatch = reply.match(/(before.?after|ugc|vsl|quiz|story|article|shorts|carousel)/i)
  const vertMatch   = reply.match(/(betting|nutra|gambling|crypto|cod|trial)/i)
  return {
    id:          crypto.randomUUID(),
    title:       `Контент: ${verticalName}${countMatch ? ' · ' + countMatch[1] + ' видео' : ''}`,
    description: reply, plan: reply, status: 'pending',
    createdAt:   new Date().toISOString(),
    params: {
      vertical: vertMatch?.[1] || verticalName || '',
      geo:      geoMatch?.[1]?.toUpperCase() || '',
      count:    countMatch?.[1] || '',
      format:   formatMatch?.[1] || '',
    },
  }
}

export default function Projects({ onCreateTask }) {
  const [projects,    setProjects]    = useState([])
  const [loading,     setLoading]     = useState(true)
  const [current,     setCurrent]     = useState(null)
  const [knowledge,   setKnowledge]   = useState([])
  const [history,     setHistory]     = useState([])
  const [projAccounts, setProjAccounts] = useState([])
  const [projVideos,   setProjVideos]   = useState([])
  const [uniqBusy,     setUniqBusy]     = useState(null)  // video_id в процессе уникализации
  const [uniqMsg,      setUniqMsg]      = useState('')
  const [expanded,     setExpanded]     = useState(new Set())  // раскрытые оригиналы (id)
  const [deletingVideoId, setDeletingVideoId] = useState(null)
  const [input,       setInput]       = useState('')
  const [sending,     setSending]     = useState(false)
  const [pendingTask, setPendingTask] = useState(null)
  const [cfgOpen,     setCfgOpen]     = useState(false)

  // Create
  const [newOpen,     setNewOpen]     = useState(false)
  const [newName,     setNewName]     = useState('')
  const [newCategory, setNewCategory] = useState('')
  const [creating,    setCreating]    = useState(false)

  // Three-dots menu
  const [menuId,      setMenuId]      = useState(null)

  // Rename
  const [editId,      setEditId]      = useState(null)
  const [editName,    setEditName]    = useState('')
  const [renaming,    setRenaming]    = useState(false)

  // Delete confirm
  const [deleteId,    setDeleteId]    = useState(null)
  const [deleting,    setDeleting]    = useState(false)

  // Запуск пайплайна из чата (предложение оркестратора)
  const [runAction,   setRunAction]   = useState(null)
  const [running,     setRunning]     = useState(false)

  const logRef = useRef(null)

  // Close menu on outside click
  useEffect(() => {
    if (!menuId) return
    const close = () => setMenuId(null)
    document.addEventListener('click', close)
    return () => document.removeEventListener('click', close)
  }, [menuId])

  function loadProjects() {
    setLoading(true)
    fetchRows('vertical_configs', 'select=id,name,category,config_yaml&order=created_at.asc')
      .then(rows => { setProjects(rows); setLoading(false) })
      .catch(() => setLoading(false))
  }
  useEffect(loadProjects, [])

  async function loadProjectMedia(projectId) {
    const accs = await fetchRows('accounts', `select=id,platform,status&project_id=eq.${projectId}&order=created_at.asc`)
    setProjAccounts(accs)
    if (!accs.length) { setProjVideos([]); return }
    const ids = accs.map(a => `"${a.id}"`).join(',')
    const vids = await fetchRows('videos', `select=id,status,storage_url,duration_sec,account_id,parent_video_id,expires_at,created_at&account_id=in.(${ids})&order=created_at.desc&limit=200`)
    setProjVideos(vids)
  }

  function toggleExpanded(id) {
    setExpanded(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id); else next.add(id)
      return next
    })
  }

  async function deleteVideo(videoId) {
    try {
      const check = await postAgents('/video/delete', { video_id: videoId, dry_run: true })
      if (check.error) { alert('Ошибка: ' + check.error); return }
      const c = check.counts || {}
      const extra = (c.copies || c.publications)
        ? ` Вместе с ним удалятся: копий — ${c.copies || 0}, публикаций — ${c.publications || 0}.`
        : ''
      if (!window.confirm(`Удалить это видео?${extra} Действие необратимо.`)) return
      setDeletingVideoId(videoId)
      await postAgents('/video/delete', { video_id: videoId, dry_run: false })
      if (current) await loadProjectMedia(current.id)
    } catch (e) {
      alert('Не удалось удалить видео: ' + e.message)
    }
    setDeletingVideoId(null)
  }

  async function openProject(p) {
    if (editId || deleteId || menuId) return
    setCurrent(p); setPendingTask(null); setCfgOpen(false); setUniqMsg('')
    const vert = deriveVertical(p)
    const kbQuery = vert
      ? `select=entry_key,title,category,vertical&is_current=eq.true&vertical=eq.${vert}&order=category.asc,entry_key.asc&limit=100`
      : `select=entry_key,title,category,vertical&is_current=eq.true&order=created_at.desc&limit=30`
    const [k, h] = await Promise.all([
      fetchRows('kb_entries', kbQuery),
      fetchRows('chat_messages', `select=role,content,created_at&vertical_id=eq.${p.id}&order=created_at.asc&limit=30`),
      loadProjectMedia(p.id),
    ])
    setKnowledge(k); setHistory(h)
  }

  async function runUniqualize(videoId) {
    setUniqBusy(videoId); setUniqMsg('')
    try {
      const data = await postAgents('/video/uniqualize', { video_id: videoId }, 600000)
      if (data.error) { setUniqMsg('❌ ' + data.error); return }
      const n = data.created?.length || 0
      const errN = data.errors?.length || 0
      setUniqMsg(`✅ Готово ${n} копий на другие аккаунты проекта` + (errN ? `, ошибок: ${errN}` : ''))
      if (current) await loadProjectMedia(current.id)
    } catch (e) {
      setUniqMsg('❌ ' + e.message)
    }
    setUniqBusy(null)
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
    } catch (e) { alert('Ошибка создания: ' + e.message) }
    setCreating(false)
  }

  // ── RENAME ───────────────────────────────────────────────────────────────
  function startRename(p) {
    setEditId(p.id); setEditName(p.name)
    setDeleteId(null); setMenuId(null)
  }

  async function confirmRename() {
    if (!editName.trim()) { setEditId(null); return }
    setRenaming(true)
    try {
      await sbPatch('vertical_configs', editId, { name: editName.trim() })
      setProjects(ps => ps.map(p => p.id === editId ? { ...p, name: editName.trim() } : p))
      if (current?.id === editId) setCurrent(c => ({ ...c, name: editName.trim() }))
    } catch (e) { alert('Ошибка переименования: ' + e.message) }
    setEditId(null); setRenaming(false)
  }

  // ── DELETE ───────────────────────────────────────────────────────────────
  function startDelete(p) {
    setDeleteId(p.id); setEditId(null); setMenuId(null)
  }

  async function confirmDelete() {
    setDeleting(true)
    try {
      await sbDelete('vertical_configs', deleteId)
      setProjects(ps => ps.filter(p => p.id !== deleteId))
      if (current?.id === deleteId) {
        setCurrent(null); setHistory([]); setKnowledge([]); setProjAccounts([]); setProjVideos([])
      }
    } catch (e) { alert('Ошибка удаления: ' + e.message) }
    setDeleteId(null); setDeleting(false)
  }

  // ── CHAT ─────────────────────────────────────────────────────────────────
  async function send() {
    if (!input.trim() || !current) return
    const msg = input.trim()
    setHistory(h => [...h, { role: 'user', content: msg }])
    setInput(''); setSending(true); setPendingTask(null); setRunAction(null)
    try {
      const res = await fetch(`${AGENTS_SERVER}/orchestrator/chat`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          vertical_id: current.id, message: msg,
          history: history.slice(-20).map(h => ({ role: h.role, content: h.content })),
        }),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data  = await res.json()
      const reply = data.reply || data.error || 'Ошибка ответа'
      setHistory(h => [...h, { role: 'assistant', content: reply }])
      if (data.run_action) setRunAction(data.run_action)
      else if (reply.length > 80) setPendingTask(reply)
    } catch (e) {
      setHistory(h => [...h, { role: 'assistant', content: '⚠️ Ошибка: ' + e.message }])
    }
    setSending(false)
  }

  // Запуск пайплайна, предложенного оркестратором (после подтверждения)
  async function runPipeline() {
    if (!runAction) return
    setRunning(true)
    try {
      const data = await postAgents(runAction.path, {
        vertical: runAction.vertical,
        geo:    runAction.geo,
        output: runAction.output,
        count:  runAction.count,
        offer:  '',
        provider: '',
      }, 300000)
      const n = data.created ?? 0
      const kind = data.video_generated ? 'видео в очереди' : 'скриптов готово'
      setHistory(h => [...h, {
        role: 'assistant',
        content: `✅ Пайплайн запущен: ${runAction.vertical}/${runAction.geo}, профиль ${runAction.output} — ${n} ${kind}` +
                 (data.blocked ? `, заблокировано ${data.blocked}` : ''),
      }])
    } catch (e) {
      setHistory(h => [...h, { role: 'assistant', content: '⚠️ Не удалось запустить пайплайн: ' + e.message }])
    }
    setRunAction(null); setRunning(false)
  }

  function createTask() {
    if (!pendingTask || !onCreateTask) return
    const task = parseTaskFromReply(pendingTask, current?.name || '')
    onCreateTask(task); setPendingTask(null)
    setHistory(h => [...h, { role: 'assistant',
      content: `✅ Задание #${task.id.slice(-6).toUpperCase()} создано → раздел «Задания»` }])
  }

  // ── RENDER ────────────────────────────────────────────────────────────────
  return (
    <>
      <div className="card">
        <div className="card-header">
          <div className="card-title">📁 Проекты</div>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <span className="live-tag">live · {projects.length}</span>
            <button
              onClick={() => { setNewOpen(o => !o); setEditId(null); setDeleteId(null) }}
              style={{ fontSize: 12, padding: '5px 14px', borderRadius: 8, cursor: 'pointer',
                background: 'var(--indigo)', color: '#fff', border: 'none', fontWeight: 600 }}>
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
              style={{ fontSize: 12, padding: '8px 16px', borderRadius: 8, cursor: 'pointer',
                background: 'var(--indigo)', color: '#fff', border: 'none', fontWeight: 600,
                opacity: (!newName.trim() || creating) ? .5 : 1 }}>
              {creating ? '…' : 'Создать'}
            </button>
          </div>
        )}

        <div style={{ padding: '14px 18px', display: 'flex', flexDirection: 'column', gap: 10 }}>
          {loading && <div className="note-box">Загрузка проектов…</div>}
          {!loading && projects.length === 0 && (
            <div className="note-box">Нет проектов. Создай первый ↑</div>
          )}

          {projects.map(p => {
            const isActive = current?.id === p.id
            const isEdit   = editId   === p.id
            const isDel    = deleteId === p.id
            const isMenu   = menuId   === p.id

            return (
              <div key={p.id}
                onClick={() => !isEdit && !isDel && openProject(p)}
                style={{
                  position: 'relative',
                  borderRadius: 10, padding: '14px 16px',
                  background: isActive ? 'var(--indigo-bg)' : 'var(--surface2)',
                  border: `1px solid ${isActive ? 'var(--indigo-bd)' : 'var(--border)'}`,
                  borderLeft: `3px solid ${isActive ? 'var(--indigo)' : '#60a5fa'}`,
                  cursor: isEdit || isDel ? 'default' : 'pointer',
                  transition: 'all .15s',
                }}>

                {/* ── Rename mode ── */}
                {isEdit ? (
                  <div onClick={e => e.stopPropagation()} style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                    <input autoFocus value={editName}
                      onChange={e => setEditName(e.target.value)}
                      onKeyDown={e => {
                        if (e.key === 'Enter') confirmRename()
                        if (e.key === 'Escape') setEditId(null)
                      }}
                      className="form-control" style={{ fontSize: 14, flex: 1, padding: '6px 10px' }} />
                    <button onClick={confirmRename} disabled={renaming}
                      style={{ fontSize: 12, padding: '6px 14px', borderRadius: 7, cursor: 'pointer',
                        background: 'var(--indigo)', color: '#fff', border: 'none', fontWeight: 700 }}>
                      {renaming ? '…' : '✓ Сохранить'}
                    </button>
                    <button onClick={e => { e.stopPropagation(); setEditId(null) }}
                      style={{ fontSize: 12, padding: '6px 10px', borderRadius: 7, cursor: 'pointer',
                        background: 'transparent', border: '1px solid var(--border)', color: 'var(--faint)' }}>
                      Отмена
                    </button>
                  </div>

                ) : isDel ? (
                  /* ── Delete confirm ── */
                  <div onClick={e => e.stopPropagation()}>
                    <div style={{ fontSize: 13, color: '#ef4444', fontWeight: 600, marginBottom: 10 }}>
                      Удалить проект «{p.name}»? Это действие необратимо.
                    </div>
                    <div style={{ display: 'flex', gap: 8 }}>
                      <button onClick={confirmDelete} disabled={deleting}
                        style={{ fontSize: 12, padding: '6px 16px', borderRadius: 7, cursor: 'pointer',
                          background: '#ef4444', color: '#fff', border: 'none', fontWeight: 700 }}>
                        {deleting ? '…' : 'Да, удалить'}
                      </button>
                      <button onClick={e => { e.stopPropagation(); setDeleteId(null) }}
                        style={{ fontSize: 12, padding: '6px 14px', borderRadius: 7, cursor: 'pointer',
                          background: 'transparent', border: '1px solid var(--border)', color: 'var(--muted)' }}>
                        Отмена
                      </button>
                    </div>
                  </div>

                ) : (
                  /* ── Normal view ── */
                  <>
                    <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 8 }}>
                      <div>
                        <div style={{ fontWeight: 600, color: 'var(--text)', fontSize: 15 }}>{p.name}</div>
                        <div style={{ fontSize: 12, color: 'var(--faint)', marginTop: 3 }}>{p.category}</div>
                      </div>

                      {/* Three-dots button */}
                      <div style={{ position: 'relative', flexShrink: 0 }}>
                        <button
                          onClick={e => { e.stopPropagation(); setMenuId(isMenu ? null : p.id) }}
                          style={{
                            width: 30, height: 30, borderRadius: 8, cursor: 'pointer', display: 'flex',
                            alignItems: 'center', justifyContent: 'center', fontSize: 18, lineHeight: 1,
                            background: isMenu ? 'var(--indigo-bg)' : 'transparent',
                            border: `1px solid ${isMenu ? 'var(--indigo-bd)' : 'transparent'}`,
                            color: 'var(--muted)',
                          }}>
                          ···
                        </button>

                        {/* Dropdown */}
                        {isMenu && (
                          <div onClick={e => e.stopPropagation()}
                            style={{
                              position: 'absolute', right: 0, top: 36, zIndex: 100,
                              background: 'var(--surface)', border: '1px solid var(--border)',
                              borderRadius: 10, boxShadow: '0 8px 24px rgba(0,0,0,.4)',
                              minWidth: 170, overflow: 'hidden',
                            }}>
                            <button
                              onClick={() => startRename(p)}
                              style={{ display: 'flex', alignItems: 'center', gap: 10, width: '100%',
                                padding: '11px 16px', background: 'transparent', border: 'none',
                                cursor: 'pointer', fontSize: 13, color: 'var(--text)', textAlign: 'left' }}
                              onMouseEnter={e => e.currentTarget.style.background = 'var(--surface2)'}
                              onMouseLeave={e => e.currentTarget.style.background = 'transparent'}>
                              <span>✏️</span> Переименовать
                            </button>
                            <div style={{ height: 1, background: 'var(--border)', margin: '0 10px' }} />
                            <button
                              onClick={() => startDelete(p)}
                              style={{ display: 'flex', alignItems: 'center', gap: 10, width: '100%',
                                padding: '11px 16px', background: 'transparent', border: 'none',
                                cursor: 'pointer', fontSize: 13, color: '#ef4444', textAlign: 'left' }}
                              onMouseEnter={e => e.currentTarget.style.background = 'rgba(239,68,68,.08)'}
                              onMouseLeave={e => e.currentTarget.style.background = 'transparent'}>
                              <span>🗑</span> Удалить
                            </button>
                          </div>
                        )}
                      </div>
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

          <CollapsibleCard
            title="🧠 База знаний проекта"
            tag={deriveVertical(current) ? `${deriveVertical(current)} · ${knowledge.length}` : `общая · ${knowledge.length}`}
            tagClass="live-tag">
            {knowledge.length === 0
              ? <div className="note-box">
                  Нет записей по вертикали этого проекта. Знания лежат в <code>kb_entries</code> —
                  проверь раздел «База знаний».
                </div>
              : <table>
                  <thead><tr><th>Категория</th><th>Заголовок</th><th>Ключ</th></tr></thead>
                  <tbody>
                    {knowledge.map((k, i) => (
                      <tr key={i}>
                        <td><span className="badge badge-indigo" style={{ fontSize: 10 }}>{k.category}</span></td>
                        <td style={{ fontSize: 12 }}>{k.title}</td>
                        <td className="mono" style={{ fontSize: 11, color: 'var(--faint)' }}>{k.entry_key}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
            }
          </CollapsibleCard>

          <CollapsibleCard
            title="🎬 Аккаунты и видео проекта"
            tag={`${projAccounts.length} акк · ${projVideos.length} видео`}
            tagClass="live-tag" defaultOpen>
            {projAccounts.length === 0 ? (
              <div className="note-box">
                К проекту не привязано ни одного аккаунта. Открой раздел «Аккаунты» и укажи
                этот проект при добавлении (1 аккаунт = 1 проект).
              </div>
            ) : (
              <>
                <div style={{ display:'flex', flexWrap:'wrap', gap:6, marginBottom:12 }}>
                  {projAccounts.map(a => (
                    <span key={a.id} className="badge badge-indigo" style={{ fontSize:11 }}>
                      {a.id} · {a.platform}
                    </span>
                  ))}
                </div>

                {uniqMsg && (
                  <div className="note-box" style={{ marginBottom:10,
                    color: uniqMsg.startsWith('✅') ? 'var(--green)' : 'var(--red)' }}>
                    {uniqMsg}
                  </div>
                )}

                {projVideos.length === 0 ? (
                  <div className="note-box">
                    У аккаунтов проекта пока нет видео. Запусти пайплайн (профиль <b>video</b>) —
                    ролики появятся здесь.
                  </div>
                ) : (() => {
                  const originals = projVideos.filter(v => !v.parent_video_id)
                  const copiesByParent = {}
                  for (const v of projVideos) {
                    if (v.parent_video_id) (copiesByParent[v.parent_video_id] ||= []).push(v)
                  }
                  return (
                    <div style={{ display:'flex', flexDirection:'column', gap:8 }}>
                      {originals.map(orig => {
                        const st = VIDEO_STATUS_META[orig.status] || { label: orig.status, color: 'var(--faint)' }
                        const ready = orig.status === 'ready' && orig.storage_url
                        const copies = copiesByParent[orig.id] || []
                        const isOpen = expanded.has(orig.id)
                        const canUniqualize = ready && projAccounts.length > 1
                        return (
                          <div key={orig.id} style={{ border:'1px solid var(--border)', borderRadius:8, overflow:'hidden' }}>
                            <div style={{ display:'flex', alignItems:'center', gap:10, padding:'8px 12px',
                              background:'var(--surface2)', flexWrap:'wrap' }}>
                              <button onClick={() => copies.length > 0 && toggleExpanded(orig.id)}
                                disabled={copies.length === 0}
                                style={{ background:'none', border:'none', cursor: copies.length ? 'pointer' : 'default',
                                  color:'var(--faint)', fontSize:11, width:16 }}>
                                {copies.length > 0 ? (isOpen ? '▾' : '▸') : ' '}
                              </button>
                              {ready
                                ? <a href={orig.storage_url} target="_blank" rel="noreferrer" style={{ color:'var(--indigo)', fontSize:12 }}>открыть ↗</a>
                                : <span style={{ color:st.color, fontSize:12 }}>{st.label}</span>}
                              <span className="mono" style={{ fontSize:11, color:'var(--faint)' }}>{orig.account_id}</span>
                              <span className="badge" style={{ color:st.color, background:st.color+'1a', fontSize:10 }}>{st.label}</span>
                              {copies.length > 0 && (
                                <span className="badge badge-muted" style={{ fontSize:10 }}>{copies.length} копий</span>
                              )}
                              <div style={{ flex:1 }} />
                              {canUniqualize && (
                                <button onClick={() => runUniqualize(orig.id)} disabled={uniqBusy === orig.id}
                                  style={{ fontSize:11, padding:'4px 10px', borderRadius:6, cursor:'pointer',
                                    background:'var(--indigo)', color:'#fff', border:'none', fontWeight:600,
                                    opacity: uniqBusy === orig.id ? .5 : 1, whiteSpace:'nowrap' }}>
                                  {uniqBusy === orig.id ? '⏳ Уникализирую…' : '🧬 На все аккаунты'}
                                </button>
                              )}
                              <button onClick={() => deleteVideo(orig.id)} disabled={deletingVideoId === orig.id}
                                title="Удалить видео вместе со всеми копиями"
                                style={{ fontSize:11, padding:'4px 8px', borderRadius:6, cursor:'pointer',
                                  background:'transparent', border:'1px solid var(--border)', color:'var(--red)',
                                  opacity: deletingVideoId === orig.id ? .5 : 1 }}>
                                {deletingVideoId === orig.id ? '…' : '🗑'}
                              </button>
                            </div>
                            {isOpen && copies.length > 0 && (
                              <table style={{ margin:0 }}>
                                <thead><tr><th>Копия</th><th>Аккаунт</th><th>Статус</th><th>Срок</th></tr></thead>
                                <tbody>
                                  {copies.map(c => {
                                    const cst = VIDEO_STATUS_META[c.status] || { label: c.status, color: 'var(--faint)' }
                                    const cReady = c.status === 'ready' && c.storage_url
                                    return (
                                      <tr key={c.id}>
                                        <td>
                                          {cReady
                                            ? <a href={c.storage_url} target="_blank" rel="noreferrer" style={{ color:'var(--indigo)' }}>↳ открыть ↗</a>
                                            : <span style={{ color:cst.color }}>↳ {cst.label}</span>}
                                        </td>
                                        <td className="mono">{c.account_id}</td>
                                        <td><span className="badge" style={{ color:cst.color, background:cst.color+'1a', fontSize:10 }}>{cst.label}</span></td>
                                        <td style={{ fontSize:11, color:'var(--faint)' }}>{expiryLabel(c) || '—'}</td>
                                      </tr>
                                    )
                                  })}
                                </tbody>
                              </table>
                            )}
                          </div>
                        )
                      })}
                    </div>
                  )
                })()}
              </>
            )}
          </CollapsibleCard>

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

              {runAction && (
                <div style={{ marginBottom: 12, padding: '12px 14px', borderRadius: 8,
                  background: 'var(--green-bg, rgba(34,197,94,.1))', border: '1px solid rgba(34,197,94,.35)',
                  display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
                  <div style={{ fontSize: 12, color: 'var(--text)' }}>
                    🚀 Запустить пайплайн: <b>{runAction.vertical}</b> · {runAction.geo} ·
                    профиль <b>{runAction.output}</b> · {runAction.count} шт
                    {runAction.output === 'text' && <span style={{ color: 'var(--faint)' }}> (без видео)</span>}
                  </div>
                  <div style={{ display: 'flex', gap: 8, flexShrink: 0 }}>
                    <button onClick={runPipeline} disabled={running}
                      style={{ fontSize: 12, padding: '6px 14px', borderRadius: 6,
                        background: 'var(--green, #22c55e)', border: 'none', color: '#fff',
                        cursor: 'pointer', fontWeight: 700, whiteSpace: 'nowrap' }}>
                      {running ? '⏳ Запуск…' : '▶ Запустить'}
                    </button>
                    <button onClick={() => setRunAction(null)}
                      style={{ fontSize: 12, padding: '6px 10px', borderRadius: 6,
                        background: 'transparent', border: '1px solid var(--border)',
                        color: 'var(--faint)', cursor: 'pointer' }}>
                      ✕
                    </button>
                  </div>
                </div>
              )}

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
