const SECTIONS = ['Главное', 'Агенты', 'Данные']

export default function Sidebar({ nav, active, onSelect, allOk }) {
  const grouped = SECTIONS.map(s => ({
    label: s,
    items: nav.filter(n => n.section === s),
  }))

  return (
    <aside className="sidebar">
      <div className="sidebar-logo">
        <div className="logo-icon">U</div>
        <div>
          <div className="logo-name">UBT OS</div>
          <div className="logo-sub">Traffic System</div>
        </div>
      </div>

      <nav className="sidebar-nav">
        {grouped.map(g => (
          <div key={g.label}>
            <div className="nav-section">{g.label}</div>
            {g.items.map(item => (
              <button
                key={item.id}
                className={`nav-item${active === item.id ? ' active' : ''}`}
                onClick={() => onSelect(item.id)}
              >
                <span className="nav-icon">{item.icon}</span>
                {item.label}
              </button>
            ))}
          </div>
        ))}
      </nav>

      <div className="sidebar-footer">
        <div className="status-chip">
          <div className={`pulse-dot${allOk ? '' : ' err'}`} />
          <span style={{ color: allOk ? 'var(--muted)' : 'var(--red)' }}>
            {allOk ? 'Все системы OK' : 'Проверка…'}
          </span>
        </div>
        <div style={{ marginTop: 8, fontSize: 10, color: 'var(--faint)', fontFamily: "'IBM Plex Mono',monospace", paddingLeft: 2 }}>
          88.218.121.108 · v2.0
        </div>
      </div>
    </aside>
  )
}
