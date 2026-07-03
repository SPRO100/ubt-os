// Конфигурация через Vite env (VITE_*) с дефолтами на текущий сервер.
// Переопредели в dashboard/.env (см. .env.example). Для работы за nginx без
// порта задай VITE_AGENTS_SERVER="" — тогда запросы пойдут на тот же origin.
const env = import.meta.env;
const stripSlash = (u) => (u || "").replace(/\/+$/, "");

export const SUPABASE_URL = stripSlash(env.VITE_SUPABASE_URL || "https://ricuoztdelapexfpqsux.supabase.co");
export const SUPABASE_ANON_KEY = env.VITE_SUPABASE_ANON_KEY || "sb_publishable_f_z6goLZoPN68j2N71wX6g_r6jNjrJt";
export const AGENTS_SERVER = env.VITE_AGENTS_SERVER !== undefined ? stripSlash(env.VITE_AGENTS_SERVER) : "http://88.218.121.108";
export const N8N_URL = env.VITE_N8N_URL !== undefined ? stripSlash(env.VITE_N8N_URL) : "http://88.218.121.108:5678";
// Set N8N_API_KEY in localStorage: localStorage.setItem('n8n_api_key', 'your-key')
export const getN8nApiKey = () => localStorage.getItem('n8n_api_key') || '';

// Bearer-токен для защищённого UBT Agents API (совпадает с AGENTS_API_TOKEN на сервере).
// Задать: localStorage.setItem('agents_api_token', 'your-token')
export const getAgentsToken = () => localStorage.getItem('agents_api_token') || '';

// Заголовки авторизации для вызовов UBT Agents API.
export function agentsHeaders(extra = {}) {
  const token = getAgentsToken();
  return token ? { ...extra, Authorization: `Bearer ${token}` } : { ...extra };
}

const headers = {
  apikey: SUPABASE_ANON_KEY,
  Authorization: "Bearer " + SUPABASE_ANON_KEY,
};

function fetchWithTimeout(url, options = {}, ms = 8000) {
  const ctrl = new AbortController();
  const id = setTimeout(() => ctrl.abort(), ms);
  return fetch(url, { ...options, signal: ctrl.signal }).finally(() => clearTimeout(id));
}

// Сигнализирует UI об ошибке запроса (App показывает баннер). Не ломает поток —
// функции по-прежнему возвращают безопасные дефолты.
export function notifyApiError(source, err) {
  const message = err?.name === 'AbortError' ? 'таймаут запроса' : (err?.message || String(err));
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent('ubt:api-error', { detail: { source, message } }));
  }
}

export async function countOf(table, filter = "") {
  try {
    const res = await fetchWithTimeout(
      `${SUPABASE_URL}/rest/v1/${table}?select=id${filter}`,
      { headers: { ...headers, Prefer: "count=exact" } }
    );
    const range = res.headers.get("content-range");
    return range ? parseInt(range.split("/")[1] || "0", 10) : 0;
  } catch (e) { notifyApiError(`count:${table}`, e); return 0; }
}

export async function fetchRows(table, query) {
  try {
    const res = await fetchWithTimeout(`${SUPABASE_URL}/rest/v1/${table}?${query}`, { headers });
    return res.ok ? await res.json() : [];
  } catch (e) { notifyApiError(`fetch:${table}`, e); return []; }
}

// Сумма по столбцу через серверный aggregate PostgREST с fallback на клиентский
// подсчёт (если агрегаты не включены в проекте Supabase).
export async function sumColumn(table, column, filter = "") {
  try {
    const res = await fetchWithTimeout(
      `${SUPABASE_URL}/rest/v1/${table}?select=total:${column}.sum()${filter}`,
      { headers }
    );
    if (res.ok) {
      const data = await res.json();
      const total = data?.[0]?.total;
      if (total !== undefined && total !== null) return parseFloat(total) || 0;
    }
  } catch (e) { notifyApiError(`sum:${table}`, e); }
  // Fallback: тянем столбец и суммируем на клиенте (ограничено 10k)
  const rows = await fetchRows(table, `select=${column}&limit=10000${filter}`);
  return (rows || []).reduce((s, r) => s + (parseFloat(r[column]) || 0), 0);
}

export async function checkHealth() {
  try {
    const res = await fetchWithTimeout(`${AGENTS_SERVER}/health/check-all`, {}, 10000);
    return res.ok ? await res.json() : null;
  } catch { return null; }
}

export async function runAgentAPI(agent, params) {
  const res = await fetchWithTimeout(
    `${AGENTS_SERVER}/agents/run`,
    {
      method: "POST",
      headers: agentsHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({ agent, params }),
    },
    120000
  );
  if (!res.ok) {
    const text = await res.text().catch(() => `HTTP ${res.status}`);
    throw new Error(text || `HTTP ${res.status}`);
  }
  return res.json();
}

// Обобщённый POST на защищённый Agents API (для роутов вне /agents/run).
export async function postAgents(path, body, ms = 120000) {
  const res = await fetchWithTimeout(
    `${AGENTS_SERVER}${path}`,
    {
      method: "POST",
      headers: agentsHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify(body),
    },
    ms
  );
  if (!res.ok) {
    const text = await res.text().catch(() => `HTTP ${res.status}`);
    throw new Error(text || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function fetchN8nWorkflows() {
  const key = getN8nApiKey();
  if (!key) return { error: 'no_key', workflows: [] };
  try {
    const res = await fetchWithTimeout(
      `${N8N_URL}/api/v1/workflows`,
      { headers: { 'X-N8N-API-KEY': key } },
      8000
    );
    if (!res.ok) return { error: `HTTP ${res.status}`, workflows: [] };
    const data = await res.json();
    return { error: null, workflows: data.data || [] };
  } catch (e) {
    return { error: e.message, workflows: [] };
  }
}

export async function toggleN8nWorkflow(id, active) {
  const key = getN8nApiKey();
  if (!key) throw new Error('no_key');
  const res = await fetchWithTimeout(
    `${N8N_URL}/api/v1/workflows/${id}/${active ? 'activate' : 'deactivate'}`,
    { method: 'POST', headers: { 'X-N8N-API-KEY': key } },
    8000
  );
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function insertRows(table, body, prefer = "return=minimal") {
  const res = await fetchWithTimeout(
    `${SUPABASE_URL}/rest/v1/${table}`,
    {
      method: "POST",
      headers: { ...headers, "Content-Type": "application/json", Prefer: prefer },
      body: JSON.stringify(body),
    },
    20000
  );
  if (!res.ok) throw new Error(await res.text());
  return res;
}

// Удаляет строку по id (PK-колонка по умолчанию "id" — переопредели для
// таблиц с текстовым PK другого имени через idColumn).
export async function deleteRow(table, id, idColumn = "id") {
  const res = await fetchWithTimeout(
    `${SUPABASE_URL}/rest/v1/${table}?${idColumn}=eq.${encodeURIComponent(id)}`,
    { method: "DELETE", headers },
    20000
  );
  if (!res.ok) throw new Error(await res.text());
  return res;
}
