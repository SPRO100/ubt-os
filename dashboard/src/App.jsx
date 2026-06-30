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
import Analytics from './components/sections/Analytics'
import Infra from './components/sections/Infra'
import Knowledge from './components/sections/Knowledge'
import { checkHealth } from './api'

const NAV = [
  { id:'dashboard', icon:'⚡', label:'Dashboard', section:'Главное' },
  { id:'accounts',  icon:'👤', label:'Аккаунты',  section:'Главное' },
  { id:'content',   icon:'🎬', label:'Производство', section:'Главное' },
  { id:'pipeline',  icon:'🔄', label:'Пайплайн (n8n)', section:'Главное' },
  { id:'clients',   icon:'🤝', label:'Клиенты',   section:'Агенты' },
  { id:'agents',    icon:'🧩', label:'Агенты',    section:'Агенты' },
  { id:'launch',    icon:'🚀', label:'Запуск агентов', section:'Агенты' },
  { id:'analytics', icon:'📊', label:'Аналитика', section:'Данные' },
  { id:'infra',     icon:'🖥️', label:'Инфраструктура', section:'Данные' },
  { id:'knowledge', icon:'🧠', label:'База знаний', section:'Данные' },
]

const TITLES = {
  dashboard: ['Dashboard',          'Реальное состояние системы прямо сейчас'],
  accounts:  ['Аккаунты',           'TikTok / Facebook / Instagram / Pinterest · прогрев A28'],
  content:   ['Производство',       'Архитектура пайплайна контента · A19–A30'],
  pipeline:  ['Пайплайн (n8n)',     '6 воркфлоу реально развёрнуты и опубликованы'],
  clients:   ['Клиенты',            'White-label агентская модель · CPA-only оплата'],
  agents:    ['Агенты',             '19 агентов A12–A30 · Publer TikTok / Facebook / Instagram / Pinterest'],
  launch:    ['Запуск агентов',     'Прямой запуск A19–A30 из браузера'],
  analytics: ['Аналитика',          'Реальная выручка из Supabase · условия партнёрок'],
  infra:     ['Инфраструктура',     'FirstVDS Амстердам · 4 сервиса live'],
  knowledge: ['База знаний',        'Obsidian Vault · синхронизация через n8n каждый час'],
}

const SECTIONS = { dashboard:Dashboard, accounts:Accounts, content:Content, pipeline:Pipeline,
  clients:Clients, agents:Agents, launch:Launch, analytics:Analytics, infra:Infra, knowledge:Knowledge }

export default function App() {
  const [section, setSection] = useState('dashboard')
  const [health, setHealth]   = useState(null)

  const fetchHealth = useCallback(async () => {
    const h = await checkHealth()
    setHealth(h)
  }, [])

  useEffect(() => {
    fetchHealth()
    const id = setInterval(fetchHealth, 60000)
    return () => clearInterval(id)
  }, [fetchHealth])

  const SectionComp = SECTIONS[section] || Dashboard
  const [title, sub] = TITLES[section] || ['—','']

  const supaOk  = health?.supabase === 'ok'
  const redisOk = health?.redis    === 'ok'
  const allOk   = supaOk && redisOk

  return (
    <div className="app">
      <Sidebar nav={NAV} active={section} onSelect={setSection} allOk={allOk} />
      <div className="main">
        <Topbar
          title={title} sub={sub}
          supaOk={supaOk} redisOk={redisOk}
          onGoLaunch={() => setSection('launch')}
        />
        <div className="content">
          <SectionComp health={health} goToLaunch={(id) => { setSection('launch') }} />
        </div>
      </div>
    </div>
  )
}
