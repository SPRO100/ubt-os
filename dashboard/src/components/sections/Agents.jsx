import { useState, useEffect } from 'react'
import CollapsibleCard from '../CollapsibleCard'

const PIPELINE_NODES = [
  { id:'A21', name:'content_creator', color:'var(--indigo)', bg:'rgba(99,102,241,.08)' },
  { id:'→',   name:'',             color:'',        bg:'transparent' },
  { id:'A19', name:'text_humanizer',  color:'var(--green)', bg:'rgba(34,197,94,.08)' },
  { id:'→',   name:'',             color:'',        bg:'transparent' },
  { id:'A25', name:'compliance',    color:'var(--amber)', bg:'rgba(245,158,11,.08)' },
  { id:'→',   name:'',             color:'',        bg:'transparent' },
  { id:'A30', name:'higgsfield',    color:'var(--pink)', bg:'rgba(236,72,153,.08)' },
  { id:'→',   name:'',             color:'',        bg:'transparent' },
  { id:'A26', name:'Publer',        color:'var(--indigo)', bg:'rgba(99,102,241,.08)' },
  { id:'→',   name:'',             color:'',        bg:'transparent' },
  { id:'📲',  name:'TikTok/FB/IG', color:'var(--green)', bg:'rgba(34,197,94,.08)' },
]

const CORE_AGENTS = [
  { id:'A14', file:'account_checker.py',      role:'Проверка здоровья аккаунтов (ER, прокси, бан)',     status:'работает', color:'var(--green)' },
  { id:'A18', file:'knowledge_synthesizer.py',role:'Синтез знаний из результатов дня — ежедн. 21:00',   status:'работает', color:'var(--green)' },
  { id:'A28', file:'warmup_manager.py',       role:'14-дневный прогрев. Лимиты активности, инфра-валидация.', status:'работает', color:'var(--green)' },
  { id:'A13', file:'telegram_jitter.py',      role:'Случайные задержки для human-behavior',              status:'готов',    color:'var(--indigo)' },
  { id:'—',   file:'risk_engine.py',          role:'Риск-скоринг аккаунтов (0–100), каждые 6ч',          status:'готов',    color:'var(--indigo)' },
]

const CONTENT_AGENTS = [
  { id:'A21', file:'content_creator.py',  role:'Before/After, хуки, UGC для US/BR/MX/DE/PL', need:'ANTHROPIC_API_KEY' },
  { id:'A19', file:'text_humanizer.py',   role:'Stop-Slop фильтр. Оценка 0–50 по 5 параметрам.', need:'ANTHROPIC_API_KEY' },
  { id:'A23', file:'youtube_creator.py',  role:'Shorts + Long-form. Retention-инжиниринг, thumbnail A/B.', need:'ANTHROPIC_API_KEY' },
]

const PUBLISH_AGENTS = [
  { id:'A25', file:'compliance_gate.py',     role:'Regex L1 + LLM L2/L3. Блокирует нарушения.',               status:'готов',              color:'var(--green)', statusC:'var(--green)' },
  { id:'A26', file:'publer_publisher.py',    role:'TikTok/Facebook/Instagram/Pinterest через Publer ($12/мес).', status:'нужен PUBLER_API_KEY', color:'var(--amber)', statusC:'var(--amber)' },
]

const MEDIA_AGENTS = [
  { id:'A30', file:'higgsfield_agent.py',     role:'UGC 9:16, Shorts 15–60с, Карусели через Higgsfield AI.', status:'нужен HIGGSFIELD_API_KEY', color:'var(--amber)' },
  { id:'A34', file:'caption_agent.py',        role:'Авто-субтитры (ASS/SRT, TikTok-style) + ffmpeg burn — буст удержания.', status:'готов', color:'var(--green)' },
  { id:'A35', file:'tts_agent.py',            role:'Озвучка faceless-видео: self-hosted TTS → ElevenLabs.', status:'готов', color:'var(--green)' },
  { id:'—',  file:'social_publisher.py',     role:'Прямая публикация на 8 платформ через нативные API.',        status:'готов', color:'var(--green)' },
  { id:'A36', file:'post_analytics_agent.py', role:'Нативные метрики постов (impressions/reach/likes/comments/shares).', status:'готов', color:'var(--green)' },
]

const SKILLS = [
  ['/stop-slop', 'Очистка AI-маркеров, оценка 0–50'],
  ['/marketing <формат> <vertical> <geo>', '30+ промптов для betting/nutra контента'],
  ['/brand-voice <vertical> <geo>', 'Голос бренда для US/BR/MX/DE/PL'],
  ['/arcads <стиль> <скрипт>', 'AI видео-реклама (Sora, Veo, Kling)'],
  ['/higgsfield ugc|short|ab <скрипт>', 'Видеогенерация UGC/Shorts через Higgsfield MCP'],
  ['/keitaro link|utm|campaign', 'Трекинг-ссылки и UTM для affiliate-кампаний'],
  ['/publer schedule|batch|calendar', 'Управление расписанием публикаций (TikTok/FB/IG)'],
]

function AgentTable({ rows, cols }) {
  return (
    <table>
      <thead><tr>{cols.map(c=><th key={c}>{c}</th>)}</tr></thead>
      <tbody>
        {rows.map(r => (
          <tr key={r.id}>
            <td className="mono" style={{ color:'var(--faint)' }}>{r.id}</td>
            <td className="primary mono">{r.file}</td>
            <td>{r.role}</td>
            <td>
              <span className="badge" style={{ color:r.statusC||r.color, background:(r.statusC||r.color)+'1a' }}>
                {r.status || r.need}
              </span>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function EnvBadge({ envKey, label }) {
  const [status, setStatus] = useState(null) // null=loading, true=ok, false=missing
  useEffect(() => {
    fetch('/health/env')
      .then(r => r.json())
      .then(d => setStatus(d[envKey] === true))
      .catch(() => setStatus(null))
  }, [envKey])
  if (status === null) return <span className="badge" style={{ color:'var(--faint)', background:'rgba(136,146,164,.1)' }}>{label || envKey}</span>
  if (status) return <span className="badge badge-green">✓ настроен</span>
  return <span className="badge badge-amber">{label || envKey}</span>
}

export default function Agents() {
  return (
    <>
      {/* Pipeline diagram */}
      <CollapsibleCard title="🔗 Пайплайн: генерация → доставка" tag="схема" defaultOpen>
        <div className="pipeline-flow">
          {PIPELINE_NODES.map((n, i) =>
            n.id === '→' ? (
              <div key={i} className="pipe-arrow">→</div>
            ) : (
              <div key={i} className="pipe-node" style={{ borderColor: n.color + '44', background: n.bg }}>
                <div className="pipe-id" style={{ color: n.color }}>{n.id}</div>
                <div className="pipe-name">{n.name}</div>
              </div>
            )
          )}
        </div>
        <div style={{ marginTop:12, fontSize:12, color:'var(--faint)' }}>
          Система сфокусирована на генерации видео и безопасной доставке на аккаунты —
          без исследовательского/поискового слоя. A18 подводит итог дня в 21:00 → записывает знания в kb_entries.
        </div>
      </CollapsibleCard>

      {/* Core */}
      <CollapsibleCard title="⚙️ Ядро системы" tag="ubt_os/agents/" count={CORE_AGENTS.length}>
        <AgentTable rows={CORE_AGENTS} cols={['ID','Файл','Роль','Статус']} />
      </CollapsibleCard>

      {/* Content pipeline */}
      <CollapsibleCard title="📝 Генерация контента" tag="A19/A21/A23" count={CONTENT_AGENTS.length}>
        <table>
          <thead><tr><th>ID</th><th>Файл</th><th>Роль</th><th>Требует</th></tr></thead>
          <tbody>
            {CONTENT_AGENTS.map(r=>(
              <tr key={r.id}>
                <td className="mono" style={{ color:'var(--faint)' }}>{r.id}</td>
                <td className="primary mono">{r.file}</td>
                <td>{r.role}</td>
                <td><EnvBadge envKey={r.need} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </CollapsibleCard>

      {/* Publish */}
      <CollapsibleCard title="📤 Публикация" tag="A25–A26" count={PUBLISH_AGENTS.length}>
        <AgentTable rows={PUBLISH_AGENTS} cols={['ID','Файл','Роль','Статус']} />
      </CollapsibleCard>

      {/* Media */}
      <CollapsibleCard title="🎥 Медиа-генерация" tag="A30/A34/A35/A36" tagClass="live-tag" count={MEDIA_AGENTS.length}>
        <AgentTable rows={MEDIA_AGENTS} cols={['ID','Файл','Роль','Статус']} />
        <div style={{ marginTop:12, fontSize:12, color:'var(--faint)' }}>
          Пайплайн: A21 (скрипт) → A30 (видео) → A26/social_publisher (публикация)
        </div>
      </CollapsibleCard>

      {/* Skills */}
      <CollapsibleCard title="🛠️ Claude Code Skills (.claude/skills/)" tag={`${SKILLS.length} скиллов`} count={SKILLS.length}>
        <table>
          <thead><tr><th>Команда</th><th>Что делает</th></tr></thead>
          <tbody>
            {SKILLS.map(([cmd, desc]) => (
              <tr key={cmd}><td className="primary mono">{cmd}</td><td>{desc}</td></tr>
            ))}
          </tbody>
        </table>
      </CollapsibleCard>
    </>
  )
}
