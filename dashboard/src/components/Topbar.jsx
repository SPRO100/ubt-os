import { useState, useEffect } from 'react'

export default function Topbar({ title, sub, supaOk, redisOk }) {
  const [now, setNow] = useState(new Date())

  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000)
    return () => clearInterval(id)
  }, [])

  const time = now.toLocaleTimeString('ru', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  const date = now.toLocaleDateString('ru', { day: 'numeric', month: 'short', year: 'numeric' })

  return (
    <div className="topbar">
      <div className="topbar-left">
        <div className="topbar-title">{title}</div>
        <div className="topbar-sub">{sub}</div>
      </div>
      <div className="topbar-right">
        <div className="topbar-btn">
          <span>📅</span> {date}
        </div>
        <div className="topbar-status">
          <div className={`dot${supaOk ? '' : ' err'}`} />
          <span style={{ fontSize: 11, color: supaOk ? 'var(--muted)' : 'var(--red)' }}>
            Supabase {supaOk ? 'OK' : 'ERR'}
          </span>
        </div>
        <div className="topbar-status">
          <div className={`dot${redisOk ? '' : ' err'}`} />
          <span style={{ fontSize: 11, color: redisOk ? 'var(--muted)' : 'var(--red)' }}>
            Redis {redisOk ? 'OK' : 'ERR'}
          </span>
        </div>
        <div className="topbar-btn mono" style={{ fontSize: 12, color: 'var(--indigo)', letterSpacing: '.05em' }}>
          {time}
        </div>
      </div>
    </div>
  )
}
