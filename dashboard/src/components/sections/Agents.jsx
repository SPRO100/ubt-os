import { useState, useEffect } from 'react'

const PIPELINE_NODES = [
  { id:'A27', name:'spy_analyzer',  color:'var(--pink)', bg:'rgba(236,72,153,.08)' },
  { id:'→',   name:'',             color:'',        bg:'transparent' },
  { id:'A21', name:'content_creator', color:'var(--indigo)', bg:'rgba(99,102,241,.08)' },
  { id:'→',   name:'',             color:'',        bg:'transparent' },
  { id:'A19', name:'text_humanizer',  color:'var(--green)', bg:'rgba(34,197,94,.08)' },
  { id:'→',   name:'',             color:'',        bg:'transparent' },
  { id:'A25', name:'compliance',    color:'var(--amber)', bg:'rgba(245,158,11,.08)' },
  { id:'→',   name:'',             color:'',        bg:'transparent' },
  { id:'A29', name:'prelanding',    color:'var(--muted)', bg:'rgba(136,146,164,.08)' },
  { id:'→',   name:'',             color:'',        bg:'transparent' },
  { id:'A26', name:'Publer',        color:'var(--indigo)', bg:'rgba(99,102,241,.08)' },
  { id:'→',   name:'',             color:'',        bg:'transparent' },
  { id:'📲',  name:'TikTok/FB/IG', color:'var(--green)', bg:'rgba(34,197,94,.08)' },
]

const CORE_AGENTS = [
  { id:'A14', file:'account_checker.py',      role:'Проверка здоровья аккаунтов (ER, прокси, бан)',     status:'работает', color:'var(--green)' },
  { id:'A18', file:'knowledge_synthesizer.py',role:'Синтез знаний через Claude — ежедн. 23:45',         status:'работает', color:'var(--green)' },
  { id:'A15', file:'strategy_engine.py',      role:'Недельная стратегия — воскресенье 20:00',           status:'работает', color:'var(--green)' },
  { id:'A16', file:'revenue_analyst.py',      role:'Анализ выручки и атрибуции',                        status:'готов',    color:'var(--indigo)' },
  { id:'A17', file:'failure_recovery.py',     role:'DLQ и восстановление после сбоев',                  status:'готов',    color:'var(--indigo)' },
  { id:'A12', file:'warming_state_machine.py',role:'State machine 7-дневного прогрева',                  status:'готов',    color:'var(--indigo)' },
  { id:'A13', file:'telegram_jitter.py',      role:'Случайные задержки для human-behavior',              status:'готов',    color:'var(--indigo)' },
]

const NEW_AGENTS = [
  { id:'A22', file:'ads_auditor.py',         role:'250+ проверок. Health Score 0–100',        need:'claude-ads ⭐6.6k',     color:'var(--pink)' },
  { id:'A23', file:'youtube_creator.py',     role:'Shorts + Long-form. Retention-инжиниринг', need:'claude-youtube ⭐218',   color:'var(--pink)' },
  { id:'A24', file:'obsidian_brain.py',      role:'Self-organizing AI wiki. Hot cache.',       need:'claude-obsidian ⭐8.2k', color:'var(--pink)' },
]

const PUBLISH_AGENTS = [
  { id:'A25', file:'compliance_gate.py',     role:'Regex L1 + LLM L2/L3. Блокирует нарушения.',               status:'готов',              color:'var(--green)', statusC:'var(--green)' },
  { id:'A26', file:'publer_publisher.py',    role:'TikTok/Facebook/Instagram/Pinterest через Publer ($12/мес).', status:'нужен PUBLER_API_KEY', color:'var(--amber)', statusC:'var(--amber)' },
]

const AFFILIATE_AGENTS = [
  { id:'A27', file:'spy_analyzer.py',           role:'Анализ крипов PiPiAds/AdHeart → хуки → creative brief для A21', status:'готов', color:'var(--green)' },
  { id:'A28', file:'warmup_manager.py',          role:'14-дневный прогрев. Лимиты активности, инфра-валидация.',       status:'готов', color:'var(--green)' },
  { id:'A29', file:'prelanding_generator.py',    role:'HTML прелендинги: quiz/story/article/vsl. COD/Trial/SS.',        status:'готов', color:'var(--green)' },
  { id:'A31', file:'competitor_analyst.py',      role:'Анализ хуков конкурентов из competitor_signals → тренды (дополняет A27).', status:'готов', color:'var(--green)' },
  { id:'A32', file:'trend_radar.py',             role:'Ранжирование трендовых звуков/хэштегов под vertical/GEO → «на чём ехать».', status:'готов', color:'var(--green)' },
  { id:'A33', file:'competitor_scraper.py',      role:'Авто-сбор крипов конкурентов в competitor_signals (кормит A31).', status:'нужен TIKTOK_SCRAPER_URL', color:'var(--amber)' },
]

const MEDIA_AGENTS = [
  { id:'A30', file:'higgsfield_agent.py',     role:'UGC 9:16, Shorts 15–60с, Карусели через Higgsfield AI.', status:'нужен HIGGSFIELD_API_KEY', color:'var(--amber)' },
  { id:'A34', file:'caption_agent.py',        role:'Авто-субтитры (ASS/SRT, TikTok-style) + ffmpeg burn — буст удержания.', status:'готов', color:'var(--green)' },
  { id:'A35', file:'tts_agent.py',            role:'Озвучка faceless-видео: self-hosted TTS → ElevenLabs.', status:'готов', color:'var(--green)' },
  { id:'—',  file:'transcription_agent.py',  role:'Транскрипция видео (Deepgram → Whisper) + извлечение хука.', status:'готов', color:'var(--green)' },
  { id:'—',  file:'social_publisher.py',     role:'Прямая публикация на 8 платформ через нативные API.',        status:'готов', color:'var(--green)' },
]

const SKILLS = [
  ['/stop-slop', 'Очистка AI-маркеров, оценка 0–50'],
  ['/marketing <формат> <vertical> <geo>', '30+ промптов для betting/nutra контента'],
  ['/brand-voice <vertical> <geo>', 'Голос бренда для US/BR/MX/DE/PL'],
  ['/seo-article <тема> <ключ>', 'SEO-статья с E-E-A-T, FAQ, мета-тегами'],
  ['/firecrawl-audit <url>', 'Аудит контент-стратегии конкурента'],
  ['/arcads <стиль> <скрипт>', 'AI видео-реклама (Sora, Veo, Kling)'],
  ['/market-report <vertical> <geo>', 'Конкурентный отчёт по рынку'],
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
      <div className="card">
        <div className="card-header">
          <div className="card-title">🔗 Пайплайн A27 → A26</div>
          <span className="ref-tag">схема</span>
        </div>
        <div className="card-body">
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
            A20 trend_scraper параллельно: ежедн. 06:00 → A24 Obsidian Brain → обновление trend_windows
          </div>
        </div>
      </div>

      {/* Core */}
      <div className="card">
        <div className="card-header"><div className="card-title">⚙️ Ядро системы (A12–A18)</div><span className="ref-tag">ubt_os/agents/</span></div>
        <div className="card-body" style={{ paddingTop:8 }}>
          <AgentTable rows={CORE_AGENTS} cols={['ID','Файл','Роль','Статус']} />
        </div>
      </div>

      {/* Content pipeline */}
      <div className="card">
        <div className="card-header"><div className="card-title">📝 Контент-пайплайн (A19–A21)</div><span className="ref-tag">добавлены 29 июня</span></div>
        <div className="card-body" style={{ paddingTop:8 }}>
          <table>
            <thead><tr><th>ID</th><th>Файл</th><th>Роль</th><th>Требует</th></tr></thead>
            <tbody>
              {[
                { id:'A21', file:'content_creator.py',  role:'Before/After, хуки, UGC для US/BR/MX/DE/PL', need:'ANTHROPIC_API_KEY' },
                { id:'A19', file:'text_humanizer.py',   role:'Stop-Slop фильтр. Оценка 0–50 по 5 параметрам.', need:'ANTHROPIC_API_KEY' },
                { id:'A20', file:'trend_scraper.py',    role:'Мониторинг конкурентов через Firecrawl.',       need:'FIRECRAWL_API_KEY' },
              ].map(r=>(
                <tr key={r.id}>
                  <td className="mono" style={{ color:'var(--faint)' }}>{r.id}</td>
                  <td className="primary mono">{r.file}</td>
                  <td>{r.role}</td>
                  <td><EnvBadge envKey={r.need} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* New A22-A24 */}
      <div className="card">
        <div className="card-header"><div className="card-title">🆕 Новые агенты (A22–A24)</div><span className="ref-tag">29 июня</span></div>
        <div className="card-body" style={{ paddingTop:8 }}>
          <AgentTable rows={NEW_AGENTS} cols={['ID','Файл','Роль','Основан на']} />
        </div>
      </div>

      {/* Publish */}
      <div className="card">
        <div className="card-header"><div className="card-title">📤 Публикация (A25–A26)</div><span className="ref-tag">29 июня</span></div>
        <div className="card-body" style={{ paddingTop:8 }}>
          <AgentTable rows={PUBLISH_AGENTS} cols={['ID','Файл','Роль','Статус']} />
        </div>
      </div>

      {/* Affiliate */}
      <div className="card">
        <div className="card-header"><div className="card-title">🕵️ Affiliate Intelligence (A27–A29)</div><span className="live-tag">29 июня</span></div>
        <div className="card-body" style={{ paddingTop:8 }}>
          <AgentTable rows={AFFILIATE_AGENTS} cols={['ID','Файл','Роль','Статус']} />
        </div>
      </div>

      {/* Media */}
      <div className="card">
        <div className="card-header"><div className="card-title">🎥 Медиа-генерация (A30)</div><span className="live-tag">30 июня</span></div>
        <div className="card-body" style={{ paddingTop:8 }}>
          <AgentTable rows={MEDIA_AGENTS} cols={['ID','Файл','Роль','Статус']} />
          <div style={{ marginTop:12, fontSize:12, color:'var(--faint)' }}>
            Пайплайн: A21 (скрипт) → A30 (медиа) → A26 Publer (публикация) · Форматы: seedance_2_0 / Higgsfield Image API
          </div>
        </div>
      </div>

      {/* Skills */}
      <div className="card">
        <div className="card-header"><div className="card-title">🛠️ Claude Code Skills (.claude/skills/)</div><span className="ref-tag">11 скиллов</span></div>
        <div className="card-body" style={{ paddingTop:8 }}>
          <table>
            <thead><tr><th>Команда</th><th>Что делает</th></tr></thead>
            <tbody>
              {SKILLS.map(([cmd, desc]) => (
                <tr key={cmd}><td className="primary mono">{cmd}</td><td>{desc}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </>
  )
}
