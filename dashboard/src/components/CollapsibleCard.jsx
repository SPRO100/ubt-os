import { useState } from 'react'

/**
 * Сворачиваемая карточка. Клик по заголовку скрывает/показывает тело.
 *
 * props:
 *  - title       — заголовок (строка или node)
 *  - tag         — правый бейдж (строка или node), опц.
 *  - tagClass    — класс бейджа (по умолч. 'ref-tag')
 *  - count       — число в заголовке (напр. кол-во строк), опц.
 *  - headerRight — интерактивные контролы справа (кнопки), опц. — клик по ним не сворачивает
 *  - defaultOpen — открыта ли по умолчанию (по умолч. false)
 *  - bodyStyle   — доп. стиль тела
 */
export default function CollapsibleCard({
  title, tag, tagClass = 'ref-tag', count, headerRight,
  defaultOpen = false, bodyStyle, children,
}) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div className="card">
      <div className="card-header" onClick={() => setOpen(o => !o)}
        style={{ cursor: 'pointer', userSelect: 'none' }}
        role="button" aria-expanded={open}>
        <div className="card-title">
          <span style={{ display: 'inline-block', width: 14, color: 'var(--faint)', fontSize: 11 }}>
            {open ? '▾' : '▸'}
          </span>
          {title}
          {count != null && (
            <span style={{ marginLeft: 8, fontSize: 11, color: 'var(--faint)', fontWeight: 400 }}>
              · {count}
            </span>
          )}
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          {headerRight && (
            <span onClick={e => e.stopPropagation()} style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              {headerRight}
            </span>
          )}
          {tag && <span className={tagClass}>{tag}</span>}
        </div>
      </div>
      {open && (
        <div className="card-body" style={{ paddingTop: 8, ...bodyStyle }}>
          {children}
        </div>
      )}
    </div>
  )
}
