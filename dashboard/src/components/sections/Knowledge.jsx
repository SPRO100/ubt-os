export default function Knowledge() {
  return (
    <>
      <div className="card">
        <div className="card-header">
          <div className="card-title">🧠 Obsidian Vault</div>
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

      <div className="card">
        <div className="card-header">
          <div className="card-title">📚 Wiki страницы</div>
          <span className="ref-tag">11 страниц</span>
        </div>
        <div className="card-body" style={{ paddingTop:8 }}>
          <table>
            <thead><tr><th>Страница</th><th>Описание</th></tr></thead>
            <tbody>
              {[
                ['tiktok-arbitrage-techniques','Техники TikTok арбитража'],
                ['cpa-rip-knowledge-base','База знаний CPA/RIP'],
                ['account-warmup-protocols','Протоколы прогрева аккаунтов'],
                ['content-frameworks','Фреймворки контента'],
                ['geo-targeting','GEO-таргетинг US/BR/MX/DE/PL'],
                ['compliance-rules','Compliance правила'],
                ['affiliate-programs','Партнёрские программы'],
              ].map(([p,d]) => (
                <tr key={p}>
                  <td className="primary mono">{p}.md</td>
                  <td style={{ color:'var(--muted)' }}>{d}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </>
  )
}
