import { useState, useEffect, useCallback } from 'react'
import Sidebar from './components/Sidebar'
import Topbar from './components/Topbar'
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
  { id:'dashboard', icon:'⚡', label:'Dashboard',       section:'Главное' },
  { id:'accounts',  icon:'👤', label:'Аккаунты',        section:'Главное' },
  { id:'content',   icon:'🎬', label:'Производство',    section:'Главное' },
  { id:'pipeline',  icon:'🔄', label:'Пайплайн (n8n)',  section:'Главное' },
  { id:'clients',   icon:'🤝', label:'Клиенты',         section:'Агенты' },
  { id:'tasks',     icon:'📋', label:'Задания',         section:'Агенты' },
  { id:'agents',    icon:'🧩', label:'Агенты',          section:'Агенты' },
  { id:'launch',    icon:'🚀', label:'Запуск агентов',  section:'Агенты' },
  { id:'analytics', icon:'📊', label:'Аналитика',       section:'Данные' },
  { id:'infra',     icon:'🖥️', label:'Инфраструктура',  section:'Данные' },
  { id:'knowledge', icon:'🧠', label:'База знаний',     section:'Данные' },
]

const TITLES = {
  dashboard: ['Dashboard',         'Реальное состояние системы прямо сейчас'],
  accounts:  ['Аккаунты',          'TikTok / Facebook / Instagram / Pinterest · прогрев A28'],
  content:   ['Производство',      'Архитектура пайплайна контента · A19–A30'],
  pipeline:  ['Пайплайн (n8n)',    '6 воркфлоу реально развёрнуты и опубликованы'],
  clients:   ['Клиенты',           'Чат с оркестратором → создание заданий в очередь'],
  tasks:     ['Задания',           'Очередь заданий · согласование → пайплайн A27→A26'],
  agents:    ['Агенты',            '19 агентов A12–A30 · Publer TikTok / Facebook / Instagram / Pinterest'],
  launch:    ['Запуск агентов',    'Прямой запуск A19–A30 из браузера'],
  analytics: ['Аналитика',         'Реальная выручка из Supabase · условия партнёрок'],
  infra:     ['Инфраструктура',    'FirstVDS Амстердам · 4 сервиса live'],
  knowledge: ['База знаний',       'Obsidian Vault · синхронизация через n8n каждый час'],
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
      case 'infra':     return <Infra />
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
          {renderSection()}
        </div>
      </div>
    </div>
  )
}
