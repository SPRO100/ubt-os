import { useEffect, useState } from 'react'
import { fetchRows, countOf } from '../../api'

const CATEGORY_LABELS = {
  content:        '🎬 Контент',
  zaliv:          '🚀 Залив',
  warmup:         '🔥 Прогрев',
  antiban:        '🛡 Антибан',
  prelanding:     '🏠 Прелендинг',
  publishing:     '📤 Публикация',
  master_prompt:  '🧠 Мастер-промпт',
  analytics:      '📊 Аналитика',
  infra:          '⚙️ Инфра',
  scaling:        '📈 Масштаб',
  affiliate:      '🤝 Партнёрки',
  vertical_guide: '📗 Гайд по вертикали',
  compliance:     '⚖️ Compliance',
  funnel:         '🔻 Воронки',
  benchmarks:     '📐 Бенчмарки',
  white_funnel:   '🏢 Белые воронки',
  tg_growth:      '📣 Рост Telegram',
  tg_monetize:    '💰 Монетизация TG',
  yt_growth:      '▶️ Рост YouTube',
  yt_monetize:    '💵 Монетизация YouTube',
}

const SCHEME_COLOR = {
  white: { background: '#d1fae5', color: '#065f46' },
  grey:  { background: '#fef3c7', color: '#92400e' },
  black: { background: '#fee2e2', color: '#991b1b' },
  any:   { background: 'var(--surface2)', color: 'var(--muted)' },
}

function extractScheme(entryKey) {
  const parts = (entryKey || '').split('.')
  return parts[3] || 'any'
}

function extractPlatform(entryKey) {
  const parts = (entryKey || '').split('.')
  return parts[1] || '—'
}

export default function Knowledge() {
  const [entries,  setEntries]  = useState([])
  const [total,    setTotal]    = useState(null)
  const [loading,  setLoading]  = useState(true)
  const [filter,   setFilter]   = useState({ vertical: '', scheme: '', category: '' })
  const [expanded, setExpanded] = useState(null)

  useEffect(() => {
    async function load() {
      setLoading(true)
      const [cnt, rows] = await Promise.all([
        countOf('kb_entries', '&is_current=eq.true'),
        fetchRows('kb_entries',
          'select=entry_key,title,category,vertical,tags,version,changed_by,created_at' +
          '&is_current=eq.true&order=category.asc,entry_key.asc&limit=200'),
      ])
      setTotal(cnt)
      setEntries(rows || [])
      setLoading(false)
    }
    load()
  }, [])

  const verticals = [...new Set(entries.map(e => e.vertical).filter(Boolean))].sort()
  const schemes   = [...new Set(entries.map(e => extractScheme(e.entry_key)).filter(s => s !== 'any'))].sort()
  const cats      = [...new Set(entries.map(e => e.category).filter(Boolean))].sort()

  const visible = entries.filter(e => {
    if (filter.vertical && e.vertical !== filter.vertical) return false
    if (filter.scheme   && extractScheme(e.entry_key) !== filter.scheme) return false
    if (filter.category && e.category !== filter.category) return false
    return true
  })

  const byCategory = visible.reduce((acc, e) => {
    const cat = e.category || 'other'
    ;(acc[cat] = acc[cat] || []).push(e)
    return acc
  }, {})

  function chip(label, field, val) {
    const active = filter[field] === val
    return (
      <button key={val} onClick={() => setFilter(f => ({ ...f, [field]: active ? '' : val }))}
        style={{
          fontSize: 11, padding: '3px 10px', borderRadius: 20, cursor: 'pointer',
          fontWeight: active ? 700 : 400,
          background: active ? 'var(--indigo)' : 'var(--surface2)',
          color: active ? '#fff' : 'var(--muted)',
          border: `1px solid ${active ? 'var(--indigo)' : 'var(--border)'}`,
          whiteSpace: 'nowrap',
        }}>{label}</button>
    )
  }

  return (
    <>
      <div className="card">
        <div className="card-header">
          <div className="card-title">🧠 База знаний (kb_entries)</div>
          {total !== null
            ? <span className="live-tag">live · {total} записей</span>
            : <span className="live-tag">…</span>}
        </div>
        <div className="card-body" style={{ paddingTop: 8, paddingBottom: 6 }}>
          {/* Filters */}
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 12 }}>
            <span style={{ fontSize: 11, color: 'var(--faint)', alignSelf: 'center' }}>Вертикаль:</span>
            {verticals.map(v => chip(v, 'vertical', v))}
            <span style={{ fontSize: 11, color: 'var(--faint)', alignSelf: 'center', marginLeft: 6 }}>Схема:</span>
            {schemes.map(s => chip(s, 'scheme', s))}
            <span style={{ fontSize: 11, color: 'var(--faint)', alignSelf: 'center', marginLeft: 6 }}>Категория:</span>
            {cats.map(c => chip(CATEGORY_LABELS[c] || c, 'category', c))}
            {(filter.vertical || filter.scheme || filter.category) && (
              <button onClick={() => setFilter({ vertical: '', scheme: '', category: '' })}
                style={{ fontSize: 11, padding: '3px 10px', borderRadius: 20, cursor: 'pointer',
                  background: 'transparent', border: '1px solid var(--border)', color: 'var(--faint)' }}>
                × сброс
              </button>
            )}
          </div>

          {loading && <div className="note-box">Загрузка записей…</div>}
          {!loading && visible.length === 0 && (
            <div className="note-box">Нет записей по выбранным фильтрам.</div>
          )}

          {!loading && Object.entries(byCategory).map(([cat, rows]) => (
            <div key={cat} style={{ marginBottom: 16 }}>
              <div style={{ fontWeight: 600, fontSize: 12, color: 'var(--indigo)',
                marginBottom: 6, paddingBottom: 4, borderBottom: '1px solid var(--border)' }}>
                {CATEGORY_LABELS[cat] || cat}
                <span style={{ fontWeight: 400, color: 'var(--faint)', marginLeft: 6 }}>
                  {rows.length} {rows.length === 1 ? 'запись' : 'записей'}
                </span>
              </div>
              <table>
                <thead>
                  <tr>
                    <th>Ключ</th>
                    <th>Заголовок</th>
                    <th>Вертикаль</th>
                    <th>Платформа</th>
                    <th>Схема</th>
                    <th>v</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map(e => {
                    const scheme   = extractScheme(e.entry_key)
                    const platform = extractPlatform(e.entry_key)
                    const isOpen   = expanded === e.entry_key
                    return (
                      <tr key={e.entry_key} onClick={() => setExpanded(isOpen ? null : e.entry_key)}
                        style={{ cursor: 'pointer', background: isOpen ? 'var(--indigo-bg)' : undefined }}>
                        <td className="mono" style={{ fontSize: 11, color: 'var(--muted)' }}>{e.entry_key}</td>
                        <td style={{ fontSize: 12, fontWeight: 500 }}>{e.title}</td>
                        <td><span className="badge badge-indigo" style={{ fontSize: 10 }}>{e.vertical || '—'}</span></td>
                        <td style={{ fontSize: 11, color: 'var(--muted)' }}>{platform}</td>
                        <td>
                          <span style={{
                            fontSize: 10, padding: '2px 7px', borderRadius: 10, fontWeight: 600,
                            ...(SCHEME_COLOR[scheme] || SCHEME_COLOR.any),
                          }}>{scheme}</span>
                        </td>
                        <td className="mono" style={{ fontSize: 11, color: 'var(--faint)' }}>v{e.version}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          ))}
        </div>
      </div>

      <div className="card">
        <div className="card-header">
          <div className="card-title">📂 Obsidian Vault</div>
          <span className="ref-tag">obsidian-vault/</span>
        </div>
        <div className="card-body">
          <div className="note-box">
            Структура PARA: <b>00 Inbox / 20 Projects / 40 Areas / 50 Resources+SOPs / 60 Daily / 90 Archive</b><br/>
            Синхронизация: <b>каждый час</b> → GitHub через воркфлоу <code>obsidian-sync</code><br/>
            Репозиторий: <code>github.com/SPRO100/ubt-os</code>
          </div>
        </div>
      </div>
    </>
  )
}
