const WORKFLOWS = [
  { name:'obsidian-sync',          schedule:'каждый час',              desc:'Vault → GitHub коммит и пуш' },
  { name:'account-checker',        schedule:'каждые 6ч',               desc:'Проверка ER, прокси, теневой бан' },
  { name:'health-monitor',         schedule:'каждые 60 сек',           desc:'Health-check Supabase/Redis + Telegram-алерты' },
  { name:'knowledge-synthesizer',  schedule:'ежедневно/еженедельно',   desc:'Claude анализирует данные → запись в Obsidian' },
  { name:'risk-engine-monitor',    schedule:'каждые 6ч',               desc:'Risk-скоринг аккаунтов 0–100' },
  { name:'strategy-engine-weekly', schedule:'воскресенье 20:00',       desc:'Недельный стратегический бриф' },
]

export default function Pipeline() {
  return (
    <>
      <div className="card">
        <div className="card-header">
          <div className="card-title">🔄 n8n воркфлоу — реально развёрнуты</div>
          <span className="ref-tag">6 из 6 активны</span>
        </div>
        <div className="card-body" style={{ paddingTop:8 }}>
          <table>
            <thead><tr><th>Воркфлоу</th><th>Расписание</th><th>Что делает</th><th>Статус</th></tr></thead>
            <tbody>
              {WORKFLOWS.map(w => (
                <tr key={w.name}>
                  <td className="primary mono">{w.name}</td>
                  <td className="mono">{w.schedule}</td>
                  <td>{w.desc}</td>
                  <td><span className="badge badge-green">● работает</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      <div className="card">
        <div className="card-header">
          <div className="card-title">🔗 n8n панель управления</div>
        </div>
        <div className="card-body">
          <div className="note-box">
            Открыть живые воркфлоу:{' '}
            <a href="http://88.218.121.108:5678" target="_blank" rel="noopener">
              88.218.121.108:5678
            </a>
          </div>
        </div>
      </div>
    </>
  )
}
