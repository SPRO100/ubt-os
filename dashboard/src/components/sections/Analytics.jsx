import { useEffect, useState } from 'react'
import { fetchRows } from '../../api'

export default function Analytics() {
  const [total, setTotal] = useState(0)

  useEffect(() => {
    fetchRows('revenue_events', 'select=net_amount&limit=1000').then(rows => {
      setTotal(rows.reduce((s, r) => s + (parseFloat(r.net_amount) || 0), 0))
    })
  }, [])

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
      </div>

      <div className="card">
        <div className="card-header">
          <div className="card-title">🤝 Условия партнёрских программ</div>
          <span className="ref-tag">аккаунты не зарегистрированы</span>
        </div>
        <div className="card-body" style={{ paddingTop:8 }}>
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
        </div>
      </div>
    </>
  )
}
