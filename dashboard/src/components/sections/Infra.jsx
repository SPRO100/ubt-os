export default function Infra() {
  return (
    <>
      <div className="card">
        <div className="card-header">
          <div className="card-title">🖥️ Сервер</div>
          <span className="ref-tag">реально развёрнут</span>
        </div>
        <div className="card-body" style={{ paddingTop:8 }}>
          <table>
            <thead><tr><th>Параметр</th><th>Значение</th></tr></thead>
            <tbody>
              {[
                ['Провайдер','FirstVDS «Улёт»'],
                ['Локация','Амстердам (EU для Claude API)'],
                ['Конфигурация','8 CPU / 12 GB RAM / 120 GB NVMe'],
                ['OS','Ubuntu 22.04 LTS'],
                ['IP','88.218.121.108'],
              ].map(([k,v]) => (
                <tr key={k}>
                  <td className="primary">{k}</td>
                  <td className="mono">{v}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="card">
        <div className="card-header">
          <div className="card-title">🔧 Развёрнутые сервисы</div>
          <span className="live-tag">4 активных</span>
        </div>
        <div className="card-body" style={{ paddingTop:8 }}>
          <table>
            <thead><tr><th>Сервис</th><th>Порт</th><th>Тип</th><th>Статус</th></tr></thead>
            <tbody>
              {[
                ['n8n','5678','Docker, restart always','online'],
                ['LiteLLM','4000','systemd','online'],
                ['UBT Agents','8080','systemd','online'],
                ['Dashboard','3000','systemd','online'],
              ].map(([s,p,t,status]) => (
                <tr key={s}>
                  <td className="primary">{s}</td>
                  <td className="mono">{p}</td>
                  <td style={{ color:'var(--faint)', fontSize:12 }}>{t}</td>
                  <td><span className={`badge ${status==='online'?'badge-green':'badge-red'}`}>● {status}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="card">
        <div className="card-header">
          <div className="card-title">🌐 nginx reverse proxy</div>
          <span className="ref-tag">deploy/nginx.conf</span>
        </div>
        <div className="card-body" style={{ paddingTop:8 }}>
          <table>
            <thead><tr><th>Путь</th><th>Сервис</th><th>Особенности</th></tr></thead>
            <tbody>
              {[
                ['/','Dashboard :3000','gzip, static cache'],
                ['/agents/','UBT Agents :8080','rate 30r/m, 180s timeout (LLM)'],
                ['/n8n/','n8n :5678','WebSocket upgrade, 3600s'],
                ['/litellm/','LiteLLM :4000','SSE streaming, buffering off'],
              ].map(([path,svc,note]) => (
                <tr key={path}>
                  <td className="primary mono">{path}</td>
                  <td>{svc}</td>
                  <td style={{ color:'var(--faint)', fontSize:12 }}>{note}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </>
  )
}
