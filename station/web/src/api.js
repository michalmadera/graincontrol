// Stan pochodzi zawsze z backendu: przeładowanie ekranu nie może zgubić kroku cyklu.
export async function pobierzStan() {
  const odp = await fetch('/api/stan', { cache: 'no-store' })
  if (!odp.ok) throw new Error(`stan: ${odp.status}`)
  return odp.json()
}

export async function akcja(nazwa, cialo) {
  const odp = await fetch(`/api/akcja/${nazwa}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(cialo ?? {}),
  })
  if (!odp.ok) {
    const dane = await odp.json().catch(() => ({}))
    throw new Error(dane.detail ?? `Akcja nie powiodła się (${odp.status})`)
  }
  return odp.json()
}
