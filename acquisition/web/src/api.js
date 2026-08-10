// Klient API akwizycji (§12.11). UI nie trzyma własnego stanu poza bieżącym widokiem —
// prawda o sesji jest w backendzie (session.json), tu tylko ją odczytujemy.

async function req(method, path, body) {
  const opts = { method, headers: {} }
  if (body !== undefined) {
    opts.headers['Content-Type'] = 'application/json'
    opts.body = JSON.stringify(body)
  }
  const res = await fetch(path, opts)
  const text = await res.text()
  const data = text ? JSON.parse(text) : null
  if (!res.ok) throw new Error(data?.detail || `${res.status} ${res.statusText}`)
  return data
}

export const api = {
  status: () => req('GET', '/api/status'),
  profile: () => req('GET', '/api/profile'),
  getSession: () => req('GET', '/api/session'),
  startSession: (body) => req('POST', '/api/session', body),
  endSession: () => req('DELETE', '/api/session'),
  declareSample: (body) => req('PUT', '/api/session/sample', body),
  advanceLayout: () => req('POST', '/api/session/layout'),
  capture: () => req('POST', '/api/capture'),
  captures: (session, limit = 20) =>
    req('GET', `/api/captures?limit=${limit}` + (session ? `&session=${session}` : '')),
}

// Strumień zdarzeń (SSE): postęp ujęcia, wynik QC, zmiany stanu kamery.
export function subscribeEvents(onEvent) {
  const es = new EventSource('/api/events')
  es.onmessage = (e) => {
    try { onEvent(JSON.parse(e.data)) } catch { /* ramka powitalna */ }
  }
  return () => es.close()
}
