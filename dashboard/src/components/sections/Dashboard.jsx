import { useEffect, useState } from 'react'
import { countOf, sumColumn } from '../../api'

const PRIORITIES = [
  'Получить API ключ Publer ($12/мес) → добавить PUBLER_API_KEY и PUBLER_*_PROFILE_IDS на сервер',
  'Купить готовые aged аккаунты TikTok + Instagram → зарегистрировать в A28 (5–7 дней прогрева)',
  'Зарегистрировать партнёрки (1win, Dr.Cash) → получить affiliate links для Keitaro',
  'Подключить Higgsfield API → запустить A21+A19 пайплайн → первый UGC-ролик через Publer',
  'Запустить A29 Prelanding Generator → создать HTML прелендинг → подключить воронку',
]

const PLATFORMS = [
  { id: 'tiktok',    name: 'TikTok',    logo: '🎵' },
  { id: 'facebook',  name: 'Facebook',  logo: '📘' },
  { id: 'instagram', name: 'Instagram', logo: '📸' },
  { id: 'pinterest', name: 'Pinterest', logo: '📌' },
]

const AI_AGENTS = [
  { icon: '📝', name: 'content_creator',  id: 'A21', desc: 'Before/After, хуки, UGC',     status: 'ready',   color: 'var(--indigo)', bg: '#6366f115' },
  { icon: '🧹', name: 'text_humanizer',   id: 'A19', desc: 'Stop-Slop очистка текста',     status: 'ready',   color: 'var(--green)', bg: '#22c55e15' },
  { icon: '📤', name: 'publer_publisher', id: 'A26', desc: 'TikTok/FB/IG/Pinterest',       status: 'no_key',  color: 'var(--amber)', bg: '#f59e0b15' },
  { icon: '🎥', name: 'higgsfield_agent', id: 'A30', desc: 'UGC видео · Shorts · Карусели',status: 'no_key',  color: 'var(--amber)', bg: '#f59e0b15' },
]

function StatCard({ label, value, note, color = 'c-indigo', icon, iconBg }) {
  return (
    <div className={`stat-card ${color}`}>
      <div className="stat-left">
        <div className="stat-label">{label}</div>
        <div className="stat-value">{value}</div>
        {note && <div className="stat-note">{note}</div>}
      </div>
      {icon && (
        <div className="stat-icon" style={{ background: iconBg || 'var(--surface2)' }}>
          {icon}
        </div>
      )}
    </div>
  )
}

export default function Dashboard({ health }) {
  const [counts, setCounts]         = useState({ accounts: 0, videos: 0, revenue: 0, knowledge: 0, strategy: 0 })
  const [platAccs, setPlatAccs]     = useState({ tiktok: 0, facebook: 0, instagram: 0, pinterest: 0 })
  const [revenueTotal, setRevenue]  = useState(0)

  useEffect(() => {
    async function load() {
      const [accounts, videos, revenue, knowledge, strategy] = await Promise.all([
        countOf('accounts'), countOf('videos'), countOf('revenue_events'),
        countOf('knowledge_entries'), countOf('strategy_briefs'),
      ])
      setCounts({ accounts, videos, revenue, knowledge, strategy })

      const [tiktok, facebook, instagram, pinterest] = await Promise.all([
        countOf('accounts', '&platform=eq.tiktok'),
        countOf('accounts', '&platform=eq.facebook'),
        countOf('accounts', '&platform=eq.instagram'),
        countOf('accounts', '&platform=eq.pinterest'),
      ])
      setPlatAccs({ tiktok, facebook, instagram, pinterest })
    }

    async function loadRevenue() {
      setRevenue(await sumColumn('revenue_events', 'net_amount'))
    }

    load()
    loadRevenue()
    const id = setInterval(() => { load(); loadRevenue() }, 60000)
    return () => clearInterval(id)
  }, [])

  const supaOk  = health?.supabase === 'ok'
  const redisOk = health?.redis    === 'ok'

  return (
    <>
      {/* ── STAT ROW ── */}
      <div className="stat-grid">
        <StatCard label="Supabase" value={supaOk ? 'OK' : 'ERR'} note="База данных" color={supaOk ? 'c-green' : 'c-red'}
          icon="🗄️" iconBg={supaOk ? 'rgba(34,197,94,.12)' : 'rgba(239,68,68,.12)'}
        />
        <StatCard label="Redis" value={redisOk ? 'OK' : 'ERR'} note="Upstash" color={redisOk ? 'c-cyan' : 'c-red'}
          icon="⚡" iconBg="rgba(6,182,212,.12)"
        />
        <StatCard label="Агенты" value="22" note="A12–A31 в системе" color="c-indigo" icon="🤖" iconBg="var(--indigo-bg)" />
        <StatCard label="Revenue Events" value={counts.revenue} note="net_amount events" color="c-green" icon="💰" iconBg="var(--green-bg)" />
        <StatCard label="Записи знаний" value={counts.knowledge} note="knowledge_entries" color="c-amber" icon="🧠" iconBg="var(--amber-bg)" />
        <StatCard label="Стратегий" value={counts.strategy} note="strategy_briefs" color="c-pink" icon="📊" iconBg="rgba(236,72,153,.12)" />
      </div>

      {/* ── TOTALS ── */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
        <div className="card" style={{ marginBottom: 0 }}>
          <div className="card-body" style={{ padding: '22px 24px' }}>
            <div style={{ fontSize: 12, color: 'var(--faint)', marginBottom: 6, textTransform: 'uppercase', letterSpacing: '.08em' }}>Всего видео</div>
            <div style={{ fontSize: 48, fontWeight: 700, fontFamily: "'IBM Plex Mono',monospace", color: 'var(--text)', lineHeight: 1 }}>{counts.videos}</div>
            <div style={{ marginTop: 14, fontSize: 12, color: 'var(--faint)' }}>из таблицы videos в Supabase</div>
          </div>
        </div>

        <div className="card" style={{ marginBottom: 0 }}>
          <div className="card-body" style={{ padding: '22px 24px' }}>
            <div style={{ fontSize: 12, color: 'var(--faint)', marginBottom: 6, textTransform: 'uppercase', letterSpacing: '.08em' }}>Всего аккаунтов</div>
            <div style={{ fontSize: 48, fontWeight: 700, fontFamily: "'IBM Plex Mono',monospace", color: 'var(--indigo)', lineHeight: 1 }}>{counts.accounts}</div>
            <div style={{ marginTop: 16, display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 8 }}>
              {PLATFORMS.map(p => (
                <div key={p.id} style={{ textAlign: 'center', background: 'var(--surface2)', borderRadius: 8, padding: '8px 6px' }}>
                  <div style={{ fontSize: 18 }}>{p.logo}</div>
                  <div style={{ fontSize: 11, color: 'var(--faint)', marginTop: 2 }}>{p.name}</div>
                  <div style={{ fontSize: 16, fontWeight: 700, fontFamily: "'IBM Plex Mono',monospace", color: 'var(--indigo)', marginTop: 4 }}>
                    {platAccs[p.id]}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* ── BOTTOM GRID ── */}
      <div className="bottom-grid">
        {/* Что дальше */}
        <div className="card" style={{ marginBottom: 0 }}>
          <div className="card-header">
            <div className="card-title">📋 Что дальше</div>
            <span className="ref-tag">приоритет</span>
          </div>
          <div className="card-body">
            {PRIORITIES.map((t, i) => (
              <div key={i} className="priority-item">
                <span className="priority-num">{String(i + 1).padStart(2, '0')}</span>
                <span className="priority-text">{t}</span>
              </div>
            ))}
          </div>
        </div>

        {/* AI Агенты */}
        <div className="card" style={{ marginBottom: 0 }}>
          <div className="card-header">
            <div className="card-title">🤖 AI-агенты</div>
            <span className="badge badge-indigo">{AI_AGENTS.length} активных</span>
          </div>
          <div className="card-body" style={{ padding: '8px 18px' }}>
            {AI_AGENTS.map(a => (
              <div key={a.id} className="agent-status-item">
                <div className="agent-status-left">
                  <div className="agent-status-icon" style={{ background: a.bg }}>
                    {a.icon}
                  </div>
                  <div>
                    <div className="agent-status-name">{a.name}</div>
                    <div className="agent-status-desc">{a.desc}</div>
                  </div>
                </div>
                <div className="status-dot-row">
                  <div className={`status-dot ${a.status === 'ready' ? 'green' : 'amber'}`} />
                  <span style={{ fontSize: 11, color: a.status === 'ready' ? 'var(--green)' : 'var(--amber)' }}>
                    {a.status === 'ready' ? 'Готов' : 'Нужен ключ'}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Финансы */}
        <div className="card" style={{ marginBottom: 0 }}>
          <div className="card-header">
            <div className="card-title">💰 Финансы</div>
          </div>
          <div className="card-body">
            <div style={{ fontSize: 36, fontWeight: 700, fontFamily: "'IBM Plex Mono',monospace", color: 'var(--text)', lineHeight: 1 }}>
              ${revenueTotal.toFixed(2)}
            </div>
            <div style={{ fontSize: 12, color: 'var(--faint)', marginTop: 6 }}>суммарная выручка · revenue_events</div>
            <div style={{ marginTop: 20 }}>
              <div style={{ fontSize: 11, color: 'var(--faint)', marginBottom: 8 }}>Условия партнёрок</div>
              {[['1win','RevShare до 60%, CPA $250'],['Dr.Cash','$25–100 CPA (COD)']].map(([n,v]) => (
                <div key={n} style={{ display:'flex', justifyContent:'space-between', padding:'6px 0', borderBottom:'1px solid var(--border)', fontSize:12 }}>
                  <b style={{ color:'var(--text)' }}>{n}</b>
                  <span style={{ color:'var(--faint)' }}>{v}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* ── FUNNEL ── */}
      <div className="card" style={{ marginTop: 14 }}>
        <div className="card-header">
          <div className="card-title">🔽 Воронка конверсии</div>
          <span className="ref-tag">прогноз</span>
        </div>
        <div className="card-body">
          <div className="funnel-row">
            {[
              { icon:'👁️', label:'Просмотры',  val:'0',  pct:'100%' },
              { icon:'🖱️', label:'Переходы',   val:'0',  pct:'0%' },
              { icon:'📋', label:'Подписки',   val:'0',  pct:'0%' },
              { icon:'🎯', label:'Лиды',       val:'0',  pct:'0%' },
              { icon:'💳', label:'Продажи',    val:'0',  pct:'0%' },
            ].map((s, i, arr) => (
              <div key={s.label} style={{ display:'flex', alignItems:'center', flex:1, minWidth:0 }}>
                <div className="funnel-step">
                  <div className="funnel-icon">{s.icon}</div>
                  <div className="funnel-label">{s.label}</div>
                  <div className="funnel-val">{s.val}</div>
                  <div className="funnel-pct">{s.pct}</div>
                </div>
                {i < arr.length - 1 && <div className="funnel-arrow">→</div>}
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* ── COMPARISON ── */}
      <div className="card">
        <div className="card-header">
          <div className="card-title">🏆 Позиционирование vs конкурентов</div>
          <span className="ref-tag">справка</span>
        </div>
        <div className="card-body" style={{ paddingTop: 8 }}>
          <table>
            <thead>
              <tr>
                <th>Фактор</th>
                <th>GeeLark</th>
                <th>Conbersa</th>
                <th>NoimosAI</th>
                <th style={{ color:'var(--indigo)' }}>UBT OS</th>
              </tr>
            </thead>
            <tbody>
              {[
                ['Claude как оркестратор', false, false, false, true],
                ['Higgsfield видео', false, false, false, true],
                ['Direction-based workflow', false, false, false, true],
                ['Obsidian как память', false, false, false, true],
                ['Человек одобряет действия', false, false, false, true],
              ].map(([f, ...vals]) => (
                <tr key={f}>
                  <td className="primary">{f}</td>
                  {vals.map((v, i) => (
                    <td key={i} style={i === 3 ? { color: 'var(--green)', fontWeight: 600 } : {}}>
                      {v ? '✓' : '—'}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </>
  )
}
