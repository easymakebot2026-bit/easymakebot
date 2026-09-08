// Glue between the Telegram Mini App JS SDK and our own /api/flow backend
// (see bot/webapp_server.py). The bot's WebAppInfo button opens this page as
// `${WEBAPP_URL}?bot_id=<uuid>`.

export function getTelegram() {
  return window.Telegram?.WebApp ?? null;
}

export function getBotId() {
  return new URLSearchParams(window.location.search).get('bot_id')
}

export function getInitData() {
  return getTelegram()?.initData ?? ''
}

export function initTelegramApp() {
  const tg = getTelegram()
  if (!tg) return
  tg.ready()
  tg.expand()
}

async function apiRequest(path, method, body) {
  const botId = getBotId()
  const res = await fetch(`${path}?bot_id=${encodeURIComponent(botId ?? '')}`, {
    method,
    headers: {
      'Content-Type': 'application/json',
      'X-Telegram-Init-Data': getInitData(),
    },
    body: body ? JSON.stringify(body) : undefined,
  })

  if (!res.ok) {
    const detail = await res.json().catch(() => ({}))
    throw new Error(detail.error || `Request failed (${res.status})`)
  }

  return res.json()
}

export function loadFlow() {
  return apiRequest('/api/flow', 'GET')
}

export function saveFlow(flow) {
  return apiRequest('/api/flow', 'POST', flow)
}

// Content List CRUD (bot/webapp_server.py: /api/content) — a real DB table,
// not part of the flow_definition blob above, so the chat wizard and this
// Mini App panel both read/write it directly and immediately: whichever was
// used most recently is simply the current state, no reconciliation needed.
export function listContent() {
  return apiRequest('/api/content', 'GET')
}

export function createContent(fields) {
  return apiRequest('/api/content', 'POST', fields)
}

export function updateContent(id, fields) {
  return apiRequest(`/api/content/${id}`, 'PUT', fields)
}

export function deleteContent(id) {
  return apiRequest(`/api/content/${id}`, 'DELETE')
}

export function reparentContent(id, parentId) {
  return apiRequest(`/api/content/${id}`, 'PUT', { parent_id: parentId })
}
