// Общий словарь вертикалей/GEO для дашборда — единая точка правды вместо
// разбросанных по секциям хардкод-списков (Launch.jsx, Clients.jsx, Accounts.jsx).
// slug'и соответствуют тем, что использует kb_entries.vertical и content_creator/
// video_pipeline на бэкенде (см. deploy/seed_kb_white.py, CLAUDE.md).

// Сопоставление проекта (название + категория) с вертикалью kb_entries.
export const VERTICAL_ALIASES = [
  ['betting',      ['беттинг', 'betting', 'ставк', 'букмекер']],
  ['gambling',     ['гемблинг', 'gambling', 'казино', 'casino', 'слот']],
  ['nutra',        ['нутра', 'nutra', 'бад', 'похуден']],
  ['finance',      ['финанс', 'finance', 'займ', 'кредит', 'мфо', 'карт']],
  ['crypto',       ['крипт', 'crypto', 'форекс', 'forex', 'бирж']],
  ['dating',       ['дейтинг', 'dating', 'знакомств']],
  ['edtech',       ['edtech', 'образован', 'обучен', 'курс', 'инфобиз', 'школ']],
  ['auto',         ['авто', 'auto', 'машин', 'car', 'корея', 'кита', 'япони', 'пригон']],
  ['tourism',      ['тур', 'туризм', 'travel', 'путешеств']],
  ['realty',       ['недвиж', 'realty', 'квартир', 'застройщик']],
  ['construction', ['строит', 'ремонт', 'construction']],
  ['beauty',       ['красот', 'beauty', 'салон', 'бьюти']],
  ['fitness',      ['фитнес', 'fitness', 'спортзал']],
  ['ecommerce',    ['магазин', 'ecommerce', 'commerce', 'товар', 'shop']],
  ['b2b',          ['b2b', 'услуг']],
  ['food',         ['доставк', 'еда', 'food', 'ресторан']],
]

// Человекочитаемые подписи для UI-селектов (порядок = порядок в списках).
export const VERTICAL_LABELS = {
  nutra: 'Nutra', betting: 'Betting', gambling: 'Gambling', finance: 'Finance',
  crypto: 'Crypto', dating: 'Dating', edtech: 'Edtech', auto: 'Авто',
  tourism: 'Туризм', realty: 'Недвижимость', construction: 'Строительство/ремонт',
  beauty: 'Красота', fitness: 'Фитнес', ecommerce: 'E-commerce', b2b: 'B2B',
  food: 'Еда/доставка', white: 'White / текстовые',
}

// 'white' — не в VERTICAL_ALIASES (не детектируется по названию проекта), но
// нужен как ручной выбор для белых/текстовых кампаний (см. A30Card carousel).
export const VERTICAL_OPTIONS = [...VERTICAL_ALIASES.map(([slug]) => slug), 'white']

// Определяет вертикаль проекта по его названию/категории — null, если не распозналась.
export function deriveVertical(project) {
  const hay = `${project?.name || ''} ${project?.category || ''}`.toLowerCase()
  for (const [slug, aliases] of VERTICAL_ALIASES) {
    if (aliases.some(a => hay.includes(a))) return slug
  }
  return null
}

// GEO-коды, с которыми реально работает BRAND_VOICE/compliance/warmup на бэкенде
// (см. content_creator.py BRAND_VOICE — незнакомые GEO уже грациозно падают на US-фолбэк).
export const GEO_OPTIONS = ['US', 'BR', 'MX', 'DE', 'PL', 'RU', 'TR', 'IN', 'NG', 'UK']
