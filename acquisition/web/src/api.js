// Klient prostego API akwizycji.

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
  state: () => req('GET', '/api/state'),
  startSession: () => req('POST', '/api/session'),
  setLabel: (name) => req('POST', '/api/label', { name }),
  shoot: () => req('POST', '/api/shoot'),
}

export const thumbUrl = (label, index) =>
  `/api/thumb/${encodeURIComponent(label)}/${index}`
