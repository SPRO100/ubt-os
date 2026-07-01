import { useState, useEffect, useCallback } from 'react'
import Sidebar from './components/Sidebar'
import Topbar from './components/Topbar'
import ErrorBoundary from './components/ErrorBoundary'
import Dashboard from './components/sections/Dashboard'
import Accounts from './components/sections/Accounts'
import Content from './components/sections/Content'
import Pipeline from './components/sections/Pipeline'
import Clients from './components/sections/Clients'
import Agents from './components/sections/Agents'
import Launch from './components/sections/Launch'
import Trends from './components/sections/Trends'
import Media from './components/sections/Media'
import Tasks from './components/sections/Tasks'
import Analytics from './components/sections/Analytics'
import Infra from './components/sections/Infra'
import Knowledge from './components/sections/Knowledge'
import { checkHealth } from './api'

const NAV = [
  // ── Ежедневная работа ──────────────────────────────
  { id:'dashboard', icon:'⚡', label:'Dashboard',       section:'Работа' },
  { id:'tasks',     icon:'📋', label:'Задания',         section:'Работа' },
  { id:'accounts',  icon:'👤', label:'Аккаунты',        section:'Работа' },
  { id:'launch',    icon:'🚀', label:'Запуск агентов',  section:'Работа' },
  // ── Контент и агенты ───────────────────────────────
  { id:'clients',   icon:'🤝', label:'Клиенты',         section:'Контент' },
  { id:'trends',    icon:'📡', label:'Тренды',          section:'Контент' },
  { id:'media',     icon:'🎙️', label:'Медиа',           section:'Контент' },
  { id:'content',   icon:'🎬', label:'Производство',    section:'Контент' },
  { id:'agents',    icon:'🧩', label:'Агенты',          section:'Контент' },
  // ── Система и данные ───────────────────────────────
  { id:'analytics', icon:'📊', label:'Аналитика',       section:'Система' },
  { id:'knowledge', icon:'🧠', label:'База знаний',     section:'Система' },
  { id:'infra',     icon:'🖥️', label:'Инфраструктура',  section:'Система' },
  { id:'pipeline',  icon:'🔄', label:'Пайплайн (n8n)', section:'Система' },
]

const TITLES = {
  dashboard: ['Dashboard',         'Реальное состояние системы прямо сейчас'],
  tasks:     ['Задания',           'Очередь заданий · согласование → пайплайн A27→A26'],
  accounts:  ['Аккаунты',          'TikTok / Facebook / Instagram / Pinterest · прогрев A28'],
  launch:    ['Запуск агентов',    'Прямой запуск A19–A35 из браузера'],
  clients:   ['Клиенты',           'Чат с оркестратором → создание заданий в очередь'],
  trends:    ['Тренды',            'Trend Radar (A32) + авто-сбор крипов конкурентов (A33 → A31)'],
  media:     ['Медиа',             'Озвучка скриптов (A35 TTS) + авто-субтитры для видео (A34)'],
  content:   ['Производство',      'Архитектура пайплайна контента · A19–A30'],
  agents:    ['Агенты',            '26 агентов A12–A35 · Publer + прямые API · TikTok / Facebook / Instagram / Pinterest'],
  analytics: ['Аналитика',         'Реальная выручка из Supabase · условия партнёрок'],
  knowledge: ['База знаний',       'Obsidian Vault · синхронизация через n8n каждый час'],
  infra:     ['Инфраструктура',    'FirstVDS Амстердам · 4 сервиса live'],
  pipeline:  ['Пайплайн (n8n)',    'Живые статусы воркфлоу · запуск и остановка из браузера'],
}

function loadTasks() {
  try { return JSON.parse(localStorage.getItem('ubt_tasks') || '[]') } catch { return [] }
}
function saveTasks(tasks) {
  localStorage.setItem('ubt_tasks', JSON.stringify(tasks))
}

const VALID_SECTIONS = new Set(NAV.map(n => n.id))
function sectionFromHash() {
  const h = window.location.hash.replace(/^#\/?/, '')
  return VALID_SECTIONS.has(h) ? h : 'dashboard'
}

export default function App() {
  const [section, setSection] = useState(sectionFromHash)
  const [health,  setHealth]  = useState(null)
  const [tasks,   setTasks]   = useState(loadTasks)
  const [apiError, setApiError] = useState(null)

  // Hash-роутинг: секция отражается в URL (#/tasks) — работает deep-link и кнопка «назад».
  function navigate(id) { window.location.hash = `/${id}` }
  useEffect(() => {
    const onHash = () => setSection(sectionFromHash())
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])

  // Баннер ошибок API (Supabase/agents недоступны) — авто-скрытие через 6с.
  useEffect(() => {
    let timer
    const onErr = (e) => {
      setApiError(e.detail?.message || 'ошибка запроса')
      clearTimeout(timer)
      timer = setTimeout(() => setApiError(null), 6000)
    }
    window.addEventListener('ubt:api-error', onErr)
    return () => { window.removeEventListener('ubt:api-error', onErr); clearTimeout(timer) }
  }, [])

  const fetchHealth = useCallback(async () => {
    try {
      const h = await checkHealth()
      setHealth(h)
    } catch {
      setHealth({ supabase: 'err', redis: 'err' })
    }
  }, [])

  useEffect(() => {
    fetchHealth()
    const id = setInterval(fetchHealth, 60000)
    return () => clearInterval(id)
  }, [fetchHealth])

  function handleCreateTask(task) {
    setTasks(prev => {
      const next = [task, ...prev]
      saveTasks(next)
      return next
    })
    navigate('tasks') // navigate to tasks after creation
  }

  function handleUpdateTask(id, patch) {
    setTasks(prev => {
      const next = patch === null
        ? prev.filter(t => t.id !== id)
        : prev.map(t => t.id === id ? { ...t, ...patch } : t)
      saveTasks(next)
      return next
    })
  }

  const supaOk = health?.supabase === 'ok'
  const redisOk = health?.redis   === 'ok'
  const allOk  = supaOk && redisOk

  const pendingCount = tasks.filter(t => t.status === 'pending').length

  function renderSection() {
    switch (section) {
      case 'dashboard': return <Dashboard health={health} />
      case 'accounts':  return <Accounts />
      case 'content':   return <Content />
      case 'pipeline':  return <Pipeline />
      case 'clients':   return <Clients onCreateTask={handleCreateTask} />
      case 'trends':    return <Trends />
      case 'media':     return <Media />
      case 'tasks':     return <Tasks tasks={tasks} onUpdate={handleUpdateTask} />
      case 'agents':    return <Agents />
      case 'launch':    return <Launch goToLaunch={() => navigate('launch')} />
      case 'analytics': return <Analytics />
      case 'infra':     return <Infra health={health} />
      case 'knowledge': return <Knowledge />
      default:          return <Dashboard health={health} />
    }
  }

  const [title, sub] = TITLES[section] || ['—', '']

  return (
    <div className="app">
      <Sidebar
        nav={NAV}
        active={section}
        onSelect={navigate}
        allOk={allOk}
        badges={{ tasks: pendingCount }}
      />
      <div className="main">
        <Topbar title={title} sub={sub} supaOk={supaOk} redisOk={redisOk} />
        {apiError && (
          <div className="api-error-banner" role="alert">
            <span>⚠️ Проблема со связью: {apiError}</span>
            <button onClick={() => setApiError(null)} aria-label="Закрыть уведомление">✕</button>
          </div>
        )}
        <div className="content">
          <ErrorBoundary key={section}>
            {renderSection()}
          </ErrorBoundary>
        </div>
      </div>
    </div>
  )
}
