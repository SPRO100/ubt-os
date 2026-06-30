import { AGENTS_SERVER } from '../../api'

const SERVER_IP = (() => {
  try { return AGENTS_SERVER ? new URL(AGENTS_SERVER).hostname : window.location.hostname }
  catch { return '—' }
})()

export default function Infra({ health }) {
  const supaOk   = health?.supabase === 'ok'
  const redisOk  = health?.redis    === 'ok'
  const agentsOk = health !== null && health !== undefined
  const checking = health === null || health === undefined

  function svcStatus(name) {
    if (name === 'UBT Agents') return checking ? 'проверка…' : agentsOk ? 'online' : 'offline'
    if (name === 'Dashboard')  return 'online'
    // n8n and LiteLLM: not directly checkable from frontend (no CORS-open endpoint)
    return agentsOk ? 'online' : 'неизвестно'
  }

  function StatusBadge({ name }) {
    const s = svcStatus(name)
    if (s === 'проверка…')   return <span className="badge" style={{ color:'var(--faint)', background:'var(--surface3)' }}>⏳ {s}</span>
    if (s === 'online')      return <span className="badge badge-green">● {s}</span>
    if (s === 'неизвестно')  return <span className="badge" style={{ color:'var(--faint)', background:'var(--surface3)' }}>? {s}</span>
    return <span className="badge badge-red">● {s}</span>
  }

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
                ['IP',SERVER_IP],
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
          <div style={{ display:'flex', gap:8, alignItems:'center' }}>
            {agentsOk
              ? <span className="badge badge-green">● сервер доступен</span>
              : <span className="badge badge-red">● сервер недоступен</span>
            }
          </div>
        </div>
        <div className="card-body" style={{ paddingTop:8 }}>
          <div style={{ marginBottom:12, display:'grid', gridTemplateColumns:'1fr 1fr', gap:8 }}>
            <div style={{ padding:'10px 14px', background:'var(--surface2)', borderRadius:8, borderLeft:`3px solid ${supaOk ? 'var(--green)' : 'var(--red)'}` }}>
              <div style={{ fontSize:11, color:'var(--faint)' }}>Supabase</div>
              <div style={{ fontWeight:600, color: supaOk ? 'var(--green)' : 'var(--red)', fontSize:13, marginTop:2 }}>
                {checking ? '⏳ проверка…' : supaOk ? '● OK' : '● ERR'}
              </div>
            </div>
            <div style={{ padding:'10px 14px', background:'var(--surface2)', borderRadius:8, borderLeft:`3px solid ${redisOk ? 'var(--green)' : 'var(--red)'}` }}>
              <div style={{ fontSize:11, color:'var(--faint)' }}>Redis (Upstash)</div>
              <div style={{ fontWeight:600, color: redisOk ? 'var(--green)' : 'var(--red)', fontSize:13, marginTop:2 }}>
                {checking ? '⏳ проверка…' : redisOk ? '● OK' : '● ERR'}
              </div>
            </div>
          </div>
          <table>
            <thead><tr><th>Сервис</th><th>Порт</th><th>Тип</th><th>Статус</th></tr></thead>
            <tbody>
              {[
                ['n8n','5678','Docker, restart always'],
                ['LiteLLM','4000','systemd'],
                ['UBT Agents','8080','systemd'],
                ['Dashboard','3000','systemd'],
              ].map(([s,p,t]) => (
                <tr key={s}>
                  <td className="primary">{s}</td>
                  <td className="mono">{p}</td>
                  <td style={{ color:'var(--faint)', fontSize:12 }}>{t}</td>
                  <td><StatusBadge name={s} /></td>
                </tr>
              ))}
            </tbody>
          </table>
          <div style={{ fontSize:11, color:'var(--faint)', marginTop:8 }}>
            Статус UBT Agents определяется по health-check эндпоинту каждые 60 сек.
          </div>
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
