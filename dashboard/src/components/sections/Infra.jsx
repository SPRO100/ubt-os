import { AGENTS_SERVER } from '../../api'
import CollapsibleCard from '../CollapsibleCard'

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
    if (name === 'nginx (dashboard + API proxy)') return 'online'
    if (name === 'UBT Agents')  return checking ? 'проверка…' : agentsOk ? 'online' : 'offline'
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
      <CollapsibleCard title="🖥️ Сервер" tag="реально развёрнут">
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
      </CollapsibleCard>

      <CollapsibleCard title="🔧 Развёрнутые сервисы" defaultOpen
        headerRight={agentsOk
          ? <span className="badge badge-green">● сервер доступен</span>
          : <span className="badge badge-red">● сервер недоступен</span>}>
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
                ['nginx (dashboard + API proxy)','80','Docker, restart unless-stopped'],
                ['UBT Agents','8080','Docker (agents), внутренняя сеть'],
                ['n8n','5678','Docker, отдельный контейнер (не в этом compose)'],
                ['LiteLLM','4000','Docker, внутренний (без публичного доступа)'],
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
      </CollapsibleCard>

      <CollapsibleCard title="🌐 nginx reverse proxy" tag="deploy/nginx.conf">
        <table>
          <thead><tr><th>Путь</th><th>Сервис</th><th>Особенности</th></tr></thead>
          <tbody>
            {[
              ['/','статика dashboard-static/','gzip, SPA fallback (index.html), кэш статики 1ч'],
              ['/run/, /agents/run, /publish/, /orchestrator/…','agents:8080 (docker, внутренняя сеть)','rate 30r/m, 180s timeout (LLM)'],
            ].map(([path,svc,note]) => (
              <tr key={path}>
                <td className="primary mono" style={{ fontSize:11 }}>{path}</td>
                <td>{svc}</td>
                <td style={{ color:'var(--faint)', fontSize:12 }}>{note}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <div style={{ fontSize:11, color:'var(--faint)', marginTop:8 }}>
          n8n и LiteLLM через nginx не проксируются — n8n доступен напрямую на :5678,
          LiteLLM используется только внутри docker-сети агентами.
        </div>
      </CollapsibleCard>
    </>
  )
}
