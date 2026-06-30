export const SUPABASE_URL = "https://ricuoztdelapexfpqsux.supabase.co";
export const SUPABASE_ANON_KEY = "sb_publishable_f_z6goLZoPN68j2N71wX6g_r6jNjrJt";
export const AGENTS_SERVER = "http://88.218.121.108:8080";

const headers = {
  apikey: SUPABASE_ANON_KEY,
  Authorization: "Bearer " + SUPABASE_ANON_KEY,
};

function fetchWithTimeout(url, options = {}, ms = 8000) {
  const ctrl = new AbortController();
  const id = setTimeout(() => ctrl.abort(), ms);
  return fetch(url, { ...options, signal: ctrl.signal }).finally(() => clearTimeout(id));
}

export async function countOf(table, filter = "") {
  try {
    const res = await fetchWithTimeout(
      `${SUPABASE_URL}/rest/v1/${table}?select=id${filter}`,
      { headers: { ...headers, Prefer: "count=exact" } }
    );
    const range = res.headers.get("content-range");
    return range ? parseInt(range.split("/")[1] || "0", 10) : 0;
  } catch { return 0; }
}

export async function fetchRows(table, query) {
  try {
    const res = await fetchWithTimeout(`${SUPABASE_URL}/rest/v1/${table}?${query}`, { headers });
    return res.ok ? await res.json() : [];
  } catch { return []; }
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
      headers: { "Content-Type": "application/json" },
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
