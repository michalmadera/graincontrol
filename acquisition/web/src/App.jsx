import React, { useCallback, useEffect, useRef, useState } from 'react'
import { api, thumbUrl } from './api.js'

// Proste narzędzie akwizycji: sesja → nazwa (BAD/NICE…) → seria zdjęć PNG+DNG.
// Jeden ekran na cały widok. Bez kiosku, bez kontraktu, bez QC.
export default function App() {
  const [state, setState] = useState(null)
  const [busy, setBusy] = useState(false)
  const [last, setLast] = useState(null)      // ostatnie zapisane {label,index,png}
  const [flash, setFlash] = useState(null)
  const [error, setError] = useState(null)
  const [editingLabel, setEditingLabel] = useState(false)

  const refresh = useCallback(async () => {
    try { setState(await api.state()) } catch (e) { setError(e.message) }
  }, [])
  useEffect(() => { refresh() }, [refresh])

  async function startSession() {
    setError(null)
    try { setState(await api.startSession()); setLast(null); setEditingLabel(true) }
    catch (e) { setError(e.message) }
  }
  async function setLabel(name) {
    setError(null)
    try { setState(await api.setLabel(name)); setEditingLabel(false); setLast(null) }
    catch (e) { setError(e.message) }
  }
  async function shoot() {
    if (busy) return
    setBusy(true); setError(null)
    try {
      const r = await api.shoot()
      setLast(r)
      setState((s) => ({ ...s, counts: r.counts }))
      setFlash(`zapisano ${r.png}`)
      setTimeout(() => setFlash(null), 1500)
    } catch (e) { setError(e.message) }
    finally { setBusy(false) }
  }

  if (!state) return <div className="loading">łączenie z kamerą…</div>

  const hasSession = !!state.session
  const hasLabel = !!state.label

  return (
    <div className="app">
      <Header state={state} />

      <div className="main">
        <Preview busy={busy} flash={flash} last={last} />

        <aside className="side">
          {!hasSession ? (
            <StartCard onStart={startSession} dataRoot={state.data_root} />
          ) : (editingLabel || !hasLabel) ? (
            <LabelInput current={state.label} onSet={setLabel}
              onCancel={hasLabel ? () => setEditingLabel(false) : null} />
          ) : (
            <ShootPanel state={state} busy={busy} last={last}
              onShoot={shoot} onChangeLabel={() => setEditingLabel(true)} />
          )}
          <Counts counts={state.counts} active={state.label} />
        </aside>
      </div>

      {error && <div className="toast error" onClick={() => setError(null)}>{error} ✕</div>}
    </div>
  )
}

function Header({ state }) {
  const cam = state.camera?.state || '—'
  const camOk = cam === 'idle' || cam === 'preview'
  return (
    <header className="header">
      <div className="hleft">
        {state.session
          ? <><b>{state.session}</b>{state.label && <> · nazwa <b className="lab">{state.label}</b></>}</>
          : <b>Brak sesji</b>}
      </div>
      <div className="hright">
        {state.dummy && <span className="badge">ATRAPA (bez kamery)</span>}
        <span className={`cam ${camOk ? 'ok' : 'warn'}`}>● kamera {cam}</span>
      </div>
    </header>
  )
}

function Preview({ busy, flash, last }) {
  return (
    <div className="preview">
      <img src="/api/preview.mjpg" alt="podgląd na żywo" />
      <div className="pv-caption">PODGLĄD NA ŻYWO</div>
      {flash && <div className="flash">{flash}</div>}
      {busy && <div className="pv-overlay"><div className="spinner" /><div>zdjęcie…</div></div>}
    </div>
  )
}

function StartCard({ onStart, dataRoot }) {
  return (
    <div className="card center">
      <p>Rozpocznij sesję — utworzy się folder <code>sesja_…</code> w:</p>
      <code className="path">{dataRoot}</code>
      <button className="big primary" onClick={onStart}>START SESJI</button>
    </div>
  )
}

function LabelInput({ current, onSet, onCancel }) {
  const [name, setName] = useState(current || '')
  const ref = useRef(null)
  useEffect(() => { ref.current?.focus() }, [])
  const submit = () => { if (name.trim()) onSet(name.trim()) }
  return (
    <div className="card center">
      <p>Wpisz nazwę (np. <b>BAD</b>, <b>NICE</b>) — zdjęcia trafią do folderu o tej nazwie.</p>
      <input ref={ref} className="labelfield" value={name} placeholder="BAD"
        onChange={(e) => setName(e.target.value)}
        onKeyDown={(e) => e.key === 'Enter' && submit()} />
      <div className="btnrow">
        {onCancel && <button className="big ghost" onClick={onCancel}>anuluj</button>}
        <button className="big primary" disabled={!name.trim()} onClick={submit}>USTAW NAZWĘ</button>
      </div>
    </div>
  )
}

function ShootPanel({ state, busy, last, onShoot, onChangeLabel }) {
  return (
    <div className="card shootcard">
      <div className="labrow">
        <span>nazwa: <b className="lab">{state.label}</b></span>
        <button className="link" onClick={onChangeLabel}>zmień nazwę</button>
      </div>
      <button className="big shoot" disabled={busy} onClick={onShoot}>
        {busy ? 'ZDJĘCIE…' : '📷 ZRÓB ZDJĘCIE'}
      </button>
      {last && (
        <div className="lastshot">
          <img src={thumbUrl(last.label, last.index)} alt={last.png} />
          <div>
            <div className="ok">✓ {last.png}</div>
            {last.dng && <div className="dim">+ {last.dng}</div>}
          </div>
        </div>
      )}
    </div>
  )
}

function Counts({ counts, active }) {
  const entries = Object.entries(counts || {})
  if (!entries.length) return null
  return (
    <div className="card counts">
      <div className="card-head">ZAPISANE</div>
      {entries.map(([label, n]) => (
        <div key={label} className={`row ${label === active ? 'active' : ''}`}>
          <span className="k">{label}</span><span className="v">{n} zdj.</span>
        </div>
      ))}
    </div>
  )
}
