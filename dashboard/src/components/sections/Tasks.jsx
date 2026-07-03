import { useState } from 'react'
import { runAgentAPI } from '../../api'

const STATUS_META = {
  pending:    { label: 'Ожидает согласования', color: 'var(--amber)', bg: '#f59e0b18', dot: 'amber' },
  approved:   { label: 'Согласовано',          color: 'var(--indigo)', bg: '#6366f118', dot: 'indigo' },
  in_progress:{ label: 'Выполняется',          color: 'var(--green)', bg: '#22c55e18', dot: 'green' },
  done:       { label: 'Готово',               color: 'var(--green)', bg: '#22c55e18', dot: 'green' },
  rejected:   { label: 'Отклонено',            color: 'var(--red)', bg: '#ef444418', dot: 'red' },
  failed:     { label: 'Ошибка',               color: 'var(--red)', bg: '#ef444418', dot: 'red' },
}

const PIPELINE_STEPS = [
  { id:'content',   label:'A21 content_creator', icon:'📝', agent:'content_creator' },
  { id:'humanize',  label:'A19 text_humanizer',  icon:'🧹', agent:'text_humanizer' },
  { id:'comply',    label:'A25 compliance_gate', icon:'🛡️', agent:'compliance_gate' },
  { id:'publish',   label:'A26 publer_publisher',icon:'📤', agent:'publer_publisher' },
]

const FORMAT_MAP = {
  'before': 'before_after', 'before-after': 'before_after', 'before/after': 'before_after',
  'ugc': 'ugc_reaction', 'story': 'ugc_reaction',
  'article': 'seo_article', 'vsl': 'seo_article', 'quiz': 'seo_article',
  'shorts': 'hook_problem', 'carousel': 'before_after',
}

function ProgressBar({ steps, currentStep }) {
  return (
    <div style={{ display:'flex', gap:4, alignItems:'center', marginTop:10 }}>
      {steps.map((s, i) => {
        const done   = i < currentStep
        const active = i === currentStep
        return (
          <div key={s.id} style={{ display:'flex', alignItems:'center', flex:1, minWidth:0 }}>
            <div style={{
              flex:1, display:'flex', flexDirection:'column', alignItems:'center', gap:3,
              opacity: done ? 1 : active ? 1 : 0.35,
            }}>
              <div style={{
                width:28, height:28, borderRadius:'50%', display:'flex', alignItems:'center',
                justifyContent:'center', fontSize:13,
                background: done ? 'var(--green)' : active ? 'var(--indigo)' : 'var(--surface3)',
                border: `2px solid ${done ? 'var(--green)' : active ? 'var(--indigo)' : 'var(--border2)'}`,
              }}>
                {done ? '✓' : active ? <span style={{ animation:'spin 1s linear infinite', display:'inline-block' }}>⏳</span> : s.icon}
              </div>
              <div style={{ fontSize:9, color:'var(--faint)', textAlign:'center', lineHeight:1.2 }}>
                {s.label.split(' ')[0]}
              </div>
            </div>
            {i < steps.length - 1 && (
              <div style={{
                height:2, width:16, flexShrink:0,
                background: done ? 'var(--green)' : 'var(--border2)',
                marginBottom:14,
              }} />
            )}
          </div>
        )
      })}
    </div>
  )
}

function TaskCard({ task, onApprove, onReject, onDelete }) {
  const [expanded, setExpanded] = useState(false)
  const meta = STATUS_META[task.status] || STATUS_META.pending

  return (
    <div style={{
      background: 'var(--surface)', border: `1px solid var(--border)`,
      borderLeft: `3px solid ${meta.color}`, borderRadius: 10,
      padding: '14px 16px', marginBottom: 10,
    }}>
      <div style={{ display:'flex', alignItems:'flex-start', justifyContent:'space-between', gap:12 }}>
        <div style={{ flex:1, minWidth:0 }}>
          <div style={{ display:'flex', alignItems:'center', gap:8, marginBottom:4 }}>
            <span style={{
              fontSize:10, fontFamily:"'IBM Plex Mono',monospace", color:'var(--faint)',
              background:'var(--surface2)', padding:'2px 6px', borderRadius:4,
            }}>#{task.id.slice(-6).toUpperCase()}</span>
            <span style={{
              fontSize:11, padding:'2px 8px', borderRadius:20,
              color: meta.color, background: meta.bg, fontWeight:600,
            }}>
              {meta.label}
            </span>
            <span style={{ fontSize:11, color:'var(--faint)' }}>
              {new Date(task.createdAt).toLocaleString('ru-RU', { day:'2-digit', month:'short', hour:'2-digit', minute:'2-digit' })}
            </span>
          </div>

          <div style={{ fontWeight:600, color:'var(--text)', fontSize:14, marginBottom:4 }}>
            {task.title}
          </div>

          {task.params && (
            <div style={{ display:'flex', gap:6, flexWrap:'wrap' }}>
              {Object.entries(task.params).map(([k,v]) => v && (
                <span key={k} style={{
                  fontSize:11, background:'var(--surface2)', border:'1px solid var(--border)',
                  padding:'2px 7px', borderRadius:4, color:'var(--muted)',
                }}>
                  {k}: <b style={{ color:'var(--text)' }}>{v}</b>
                </span>
              ))}
            </div>
          )}

          {task.status === 'failed' && task.error && (
            <div style={{ marginTop:8, padding:'6px 10px', background:'#ef444418', borderRadius:6, fontSize:11, color:'var(--red)' }}>
              ⚠️ {task.error}
            </div>
          )}
        </div>

        <div style={{ display:'flex', gap:6, flexShrink:0 }}>
          <button onClick={() => setExpanded(e => !e)}
            style={{ fontSize:11, padding:'4px 10px', borderRadius:6, background:'var(--surface2)',
              border:'1px solid var(--border)', color:'var(--muted)', cursor:'pointer' }}>
            {expanded ? 'Скрыть' : 'Детали'}
          </button>
          {task.status === 'pending' && (
            <>
              <button onClick={() => onApprove(task.id)}
                style={{ fontSize:11, padding:'4px 12px', borderRadius:6,
                  background:'var(--indigo)', border:'none', color:'#fff',
                  cursor:'pointer', fontWeight:600 }}>
                ✓ Согласовать
              </button>
              <button onClick={() => onReject(task.id)}
                style={{ fontSize:11, padding:'4px 10px', borderRadius:6,
                  background:'var(--surface2)', border:'1px solid #ef444444',
                  color:'var(--red)', cursor:'pointer' }}>
                ✕
              </button>
            </>
          )}
          {(task.status === 'done' || task.status === 'rejected' || task.status === 'failed') && (
            <button onClick={() => onDelete(task.id)}
              style={{ fontSize:11, padding:'4px 8px', borderRadius:6, background:'transparent',
                border:'1px solid var(--border)', color:'var(--faint)', cursor:'pointer' }}>
              🗑
            </button>
          )}
        </div>
      </div>

      {task.status === 'in_progress' && (
        <ProgressBar steps={PIPELINE_STEPS} currentStep={task.step || 0} />
      )}

      {expanded && (
        <div style={{ marginTop:12, padding:'10px 12px', background:'var(--surface2)',
          borderRadius:8, fontSize:12, color:'var(--muted)', whiteSpace:'pre-wrap',
          lineHeight:1.6, fontFamily:"'IBM Plex Mono',monospace" }}>
          {task.plan || task.description || 'Нет детального описания.'}
        </div>
      )}
    </div>
  )
}

export default function Tasks({ tasks = [], onUpdate }) {
  const counts = {
    pending:     tasks.filter(t => t.status === 'pending').length,
    in_progress: tasks.filter(t => t.status === 'in_progress').length,
    done:        tasks.filter(t => t.status === 'done').length,
  }

  async function approve(id) {
    const task = tasks.find(t => t.id === id)
    if (!task) return

    const vert = task.params?.vertical || 'nutra'
    const geo  = task.params?.geo      || 'US'
    const rawFmt = (task.params?.format || '').toLowerCase()
    const fmt  = FORMAT_MAP[rawFmt] || 'before_after'

    onUpdate(id, { status: 'in_progress', step: 0, approvedAt: new Date().toISOString() })

    try {
      // Step 0: Content creator
      const contentRes = await runAgentAPI('content_creator', {
        format: fmt, vertical: vert, geo,
      })
      const rawText = contentRes.result || contentRes.content || task.title
      onUpdate(id, { step: 1 })

      // Step 1: Text humanizer
      const humanRes = await runAgentAPI('text_humanizer', {
        text: rawText, geo, vertical: vert,
      })
      const cleanText = humanRes.result || rawText
      onUpdate(id, { step: 2 })

      // Step 2: Compliance gate
      await runAgentAPI('compliance_gate', {
        text: cleanText, vertical: vert, geo,
      })
      onUpdate(id, { step: 3 })

      // Step 3: Publisher (dry run — real publish requires PUBLER_API_KEY)
      await runAgentAPI('publer_publisher', {
        text: cleanText, platform: 'tiktok',
        affiliate_url: '', vertical: vert, geo, dry_run: true,
      })

      onUpdate(id, { status: 'done', step: PIPELINE_STEPS.length, doneAt: new Date().toISOString() })
    } catch (e) {
      onUpdate(id, { status: 'failed', error: e.message })
    }
  }

  function reject(id) {
    onUpdate(id, { status: 'rejected' })
  }

  function remove(id) {
    onUpdate(id, null)
  }

  const pending  = tasks.filter(t => t.status === 'pending')
  const active   = tasks.filter(t => t.status === 'in_progress')
  const finished = tasks.filter(t => t.status === 'done' || t.status === 'rejected' || t.status === 'failed')

  return (
    <>
      {/* Stats */}
      <div style={{ display:'grid', gridTemplateColumns:'repeat(3,1fr)', gap:12, marginBottom:4 }}>
        {[
          { label:'Ожидают',  val: counts.pending,     color:'var(--amber)' },
          { label:'В работе', val: counts.in_progress, color:'var(--indigo)' },
          { label:'Готово',   val: counts.done,        color:'var(--green)' },
        ].map(s => (
          <div key={s.label} style={{
            background:'var(--surface)', border:'1px solid var(--border)', borderRadius:10,
            padding:'16px 20px', borderTop:`3px solid ${s.color}`,
          }}>
            <div style={{ fontSize:11, color:'var(--faint)', marginBottom:4 }}>{s.label}</div>
            <div style={{ fontSize:32, fontWeight:700, fontFamily:"'IBM Plex Mono',monospace", color:'var(--text)' }}>
              {s.val}
            </div>
          </div>
        ))}
      </div>

      {tasks.length === 0 && (
        <div className="card">
          <div className="card-body">
            <div className="note-box" style={{ textAlign:'center', padding:'32px 20px' }}>
              <div style={{ fontSize:32, marginBottom:12 }}>📋</div>
              <div style={{ fontWeight:600, color:'var(--text)', marginBottom:6 }}>Заданий пока нет</div>
              <div style={{ color:'var(--faint)', fontSize:13 }}>
                Перейди в раздел <b style={{ color:'var(--indigo)' }}>Клиенты</b> → выбери проект →
                напиши оркестратору задачу (например: «Создай 5 видео, вертикаль betting, гео US, формат before/after») →
                нажми «Создать задание»
              </div>
            </div>
          </div>
        </div>
      )}

      {pending.length > 0 && (
        <div className="card">
          <div className="card-header">
            <div className="card-title">⏳ Ожидают согласования</div>
            <span style={{ fontSize:12, padding:'3px 10px', borderRadius:20,
              background:'#f59e0b18', color:'var(--amber)', fontWeight:600 }}>
              {pending.length}
            </span>
          </div>
          <div className="card-body">
            {pending.map(t => (
              <TaskCard key={t.id} task={t} onApprove={approve} onReject={reject} onDelete={remove} />
            ))}
          </div>
        </div>
      )}

      {active.length > 0 && (
        <div className="card">
          <div className="card-header">
            <div className="card-title">⚙️ Выполняются</div>
            <span className="live-tag">live · {active.length}</span>
          </div>
          <div className="card-body">
            {active.map(t => (
              <TaskCard key={t.id} task={t} onApprove={approve} onReject={reject} onDelete={remove} />
            ))}
          </div>
        </div>
      )}

      {finished.length > 0 && (
        <div className="card">
          <div className="card-header">
            <div className="card-title">✅ Завершённые</div>
            <span className="ref-tag">{finished.length}</span>
          </div>
          <div className="card-body">
            {finished.map(t => (
              <TaskCard key={t.id} task={t} onApprove={approve} onReject={reject} onDelete={remove} />
            ))}
          </div>
        </div>
      )}
    </>
  )
}
