import { useEffect, useState } from 'react'
import { fetchRows, runAgentAPI } from '../../api'
import CollapsibleCard from '../CollapsibleCard'

function fmt(n) {
  const v = Number(n) || 0
  return v >= 1000 ? v.toLocaleString('ru-RU') : String(v)
}

export default function Analytics() {
  const [total, setTotal]           = useState(0)
  const [platforms, setPlatforms]   = useState([])
  const [recentPosts, setRecent]    = useState([])
  const [loadingMetrics, setLoadingMetrics] = useState(true)
  const [syncing, setSyncing]       = useState(false)
  const [syncResult, setSyncResult] = useState(null)
  const [syncError, setSyncError]   = useState(null)

  function loadMetrics() {
    setLoadingMetrics(true)
    Promise.all([
      fetchRows('v_platform_engagement', 'select=*&order=total_impressions.desc'),
      fetchRows('v_post_metrics_latest', 'select=*&order=fetched_at.desc&limit=20'),
    ]).then(([plat, posts]) => {
      setPlatforms(plat || [])
      setRecent(posts || [])
      setLoadingMetrics(false)
    }).catch(() => setLoadingMetrics(false))
  }

  useEffect(() => {
    fetchRows('revenue_events', 'select=net_amount&limit=10000').then(rows => {
      setTotal((rows || []).reduce((s, r) => s + (parseFloat(r.net_amount) || 0), 0))
    }).catch(() => {})
    loadMetrics()
  }, [])

  async function sync() {
    setSyncing(true)
    setSyncError(null)
    setSyncResult(null)
    try {
      const res = await runAgentAPI('post_analytics', {})
      setSyncResult(res)
      loadMetrics()
    } catch (e) {
      setSyncError(e.message)
    }
    setSyncing(false)
  }

  return (
    <>
      <div className="stat-grid">
        <div className="stat-card c-green">
          <div className="stat-left">
            <div className="stat-label">Реальная выручка</div>
            <div className="stat-value">${total.toFixed(2)}</div>
            <div className="stat-note">из revenue_events</div>
          </div>
          <div className="stat-icon" style={{ background:'var(--green-bg)' }}>💰</div>
        </div>
        <div className="stat-card c-indigo">
          <div className="stat-left">
            <div className="stat-label">Постов отслеживается</div>
            <div className="stat-value">{platforms.reduce((s, p) => s + (p.posts_tracked || 0), 0)}</div>
            <div className="stat-note">post_metrics · A36</div>
          </div>
          <div className="stat-icon" style={{ background:'var(--indigo-bg)' }}>📊</div>
        </div>
      </div>

      <div className="card">
        <div className="card-header">
          <div className="card-title">📈 Нативная аналитика по постам</div>
          <div style={{ display:'flex', gap:8, alignItems:'center' }}>
            {loadingMetrics && <span style={{ fontSize:11, color:'var(--faint)' }}>загрузка…</span>}
            <button onClick={sync} disabled={syncing}
              style={{ fontSize:11, padding:'4px 12px', borderRadius:6,
                background:'var(--indigo)', border:'none', color:'#fff',
                cursor:'pointer', fontWeight:600 }}>
              {syncing ? '⏳ Синхронизация…' : '↻ Синхронизировать (A36)'}
            </button>
          </div>
        </div>
        <div className="card-body" style={{ paddingTop:8 }}>
          {syncError && (
            <div className="note-box" style={{ borderColor:'var(--red)', color:'var(--red)', marginBottom:12 }}>
              ⚠️ {syncError}
            </div>
          )}
          {syncResult && (
            <div className="note-box" style={{ marginBottom:12 }}>
              Синхронизировано: <b style={{ color:'var(--green)' }}>{syncResult.synced ?? 0}</b> ·
              {' '}ошибок: <b style={{ color:'var(--red)' }}>{syncResult.failed ?? 0}</b> ·
              {' '}пропущено: {syncResult.skipped ?? 0} · всего джобов: {syncResult.total ?? 0}
            </div>
          )}

          {platforms.length === 0 ? (
            <div className="note-box">
              Метрик пока нет. Нативная аналитика (impressions/reach/likes/comments/shares) синхронизируется
              из <b>direct_publish_jobs</b> через A36 <code>post_analytics_agent</code> — жми «Синхронизировать»
              после публикации постов через A26/social_publisher.
            </div>
          ) : (
            <>
              <table style={{ marginBottom:16 }}>
                <thead>
                  <tr>
                    <th>Платформа</th><th>Постов</th><th>Impressions</th><th>Reach</th>
                    <th>Views</th><th>Likes</th><th>Comments</th><th>Shares</th><th>Avg ER</th>
                  </tr>
                </thead>
                <tbody>
                  {platforms.map(p => (
                    <tr key={p.platform}>
                      <td className="primary">{p.platform}</td>
                      <td className="mono">{p.posts_tracked}</td>
                      <td className="mono">{fmt(p.total_impressions)}</td>
                      <td className="mono">{fmt(p.total_reach)}</td>
                      <td className="mono">{fmt(p.total_views)}</td>
                      <td className="mono">{fmt(p.total_likes)}</td>
                      <td className="mono">{fmt(p.total_comments)}</td>
                      <td className="mono">{fmt(p.total_shares)}</td>
                      <td className="mono" style={{ color:'var(--green)' }}>{p.avg_engagement_rate}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>

              <div style={{ fontSize:11, color:'var(--faint)', marginBottom:6 }}>Последние посты (снапшот метрик)</div>
              <table>
                <thead>
                  <tr>
                    <th>Платформа</th><th>Post ID</th><th>Impr/Views</th>
                    <th>Likes</th><th>Comments</th><th>Shares</th><th>ER</th><th>Обновлено</th>
                  </tr>
                </thead>
                <tbody>
                  {recentPosts.map(p => (
                    <tr key={p.id}>
                      <td className="primary">{p.platform}</td>
                      <td className="mono" style={{ fontSize:11 }}>{(p.platform_post_id||'').slice(0,16)}</td>
                      <td className="mono">{fmt(p.impressions || p.reach || p.views)}</td>
                      <td className="mono">{fmt(p.likes)}</td>
                      <td className="mono">{fmt(p.comments)}</td>
                      <td className="mono">{fmt(p.shares)}</td>
                      <td className="mono" style={{ color:'var(--green)' }}>{p.engagement_rate}%</td>
                      <td className="mono" style={{ fontSize:11, color:'var(--faint)' }}>
                        {(p.fetched_at||'').slice(0,16).replace('T',' ')}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}
        </div>
      </div>

      <CollapsibleCard title="🤝 Условия партнёрских программ" tag="аккаунты не зарегистрированы" count={3}>
        <table>
          <thead><tr><th>Программа</th><th>Условия</th><th>Cookie</th><th>Выплаты</th></tr></thead>
          <tbody>
            {[
              ['1win','RevShare до 60%, CPA до $250','365 дней','по вторникам'],
              ['Mostbet','RevShare до 60%','—','—'],
              ['Dr.Cash','$25–100 CPA (COD)','—','2×/неделю'],
            ].map(([n,c,k,p]) => (
              <tr key={n}>
                <td className="primary">{n}</td>
                <td>{c}</td>
                <td className="mono">{k}</td>
                <td>{p}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </CollapsibleCard>
    </>
  )
}
