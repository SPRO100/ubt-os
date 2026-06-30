import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent } from '@testing-library/react'
import Sidebar from './Sidebar'

const NAV = [
  { id: 'dashboard', icon: '⚡', label: 'Dashboard', section: 'Работа' },
  { id: 'tasks',     icon: '📋', label: 'Задания',   section: 'Работа' },
  { id: 'agents',    icon: '🧩', label: 'Агенты',    section: 'Контент' },
]

afterEach(cleanup)

describe('Sidebar', () => {
  it('renders all nav items', () => {
    render(<Sidebar nav={NAV} active="dashboard" onSelect={() => {}} allOk />)
    expect(screen.getByText('Dashboard')).toBeTruthy()
    expect(screen.getByText('Задания')).toBeTruthy()
    expect(screen.getByText('Агенты')).toBeTruthy()
  })

  it('marks the active item with aria-current=page', () => {
    render(<Sidebar nav={NAV} active="tasks" onSelect={() => {}} allOk />)
    const active = screen.getByRole('button', { name: /Задания/ })
    expect(active.getAttribute('aria-current')).toBe('page')
  })

  it('calls onSelect with the item id on click', () => {
    const onSelect = vi.fn()
    render(<Sidebar nav={NAV} active="dashboard" onSelect={onSelect} allOk />)
    fireEvent.click(screen.getByRole('button', { name: /Агенты/ }))
    expect(onSelect).toHaveBeenCalledWith('agents')
  })

  it('shows the task badge count when > 0', () => {
    render(<Sidebar nav={NAV} active="dashboard" onSelect={() => {}} allOk badges={{ tasks: 3 }} />)
    expect(screen.getByText('3')).toBeTruthy()
  })
})
