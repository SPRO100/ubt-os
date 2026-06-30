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
  launch:    ['Запуск агентов',    'Прямой запуск A19–A30 из браузера'],
  clients:   ['Клиенты',           'Чат с оркестратором → создание заданий в очередь'],
  content:   ['Производство',      'Архитектура пайплайна контента · A19–A30'],
  agents:    ['Агенты',            '22 агента A12–A31 · Publer + прямые API · TikTok / Facebook / Instagram / Pinterest'],
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

export default function App() {
  const [section, setSection] = useState('dashboard')
  const [health,  setHealth]  = useState(null)
  const [tasks,   setTasks]   = useState(loadTasks)

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
    setSection('tasks') // navigate to tasks after creation
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
      case 'tasks':     return <Tasks tasks={tasks} onUpdate={handleUpdateTask} />
      case 'agents':    return <Agents />
      case 'launch':    return <Launch goToLaunch={() => setSection('launch')} />
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
        onSelect={setSection}
        allOk={allOk}
        badges={{ tasks: pendingCount }}
      />
      <div className="main">
        <Topbar title={title} sub={sub} supaOk={supaOk} redisOk={redisOk} />
        <div className="content">
          <ErrorBoundary key={section}>
            {renderSection()}
          </ErrorBoundary>
        </div>
      </div>
    </div>
  )
}
