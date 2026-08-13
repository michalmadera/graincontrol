import React, { useCallback, useEffect, useRef, useState } from 'react'
import { api, thumbUrl } from './api.js'

// Narzędzie akwizycji: sesja → nazwa (BAD/NICE…) → seria zdjęć PNG+DNG.
// Jeden ekran na cały widok. Każde ujęcie przechodzi kontrakt akwizycji (§5);
// niezgodne z profilem trafia do odrzucone/ i nie zwiększa numeru.
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
  async function newSession() {
    if (!confirm('Nowa sesja? Bieżące zdjęcia zostają zapisane na dysku.')) return
    await startSession()
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
      setState((s) => ({ ...s, counts: r.counts, rejected: r.rejected }))
      // Odrzucenie przez kontrakt nie jest błędem serwera — pokazujemy je jak werdykt,
      // z konkretną rozbieżnością, a nie ogólnikiem.
      setFlash(r.accepted ? `zapisano ${r.png}` : `ODRZUCONE — ${r.png}`)
      setTimeout(() => setFlash(null), r.accepted ? 1500 : 4000)
    } catch (e) { setError(e.message) }
    finally { setBusy(false) }
  }

  if (!state) return <div className="loading">łączenie z kamerą…</div>

  const hasSession = !!state.session
  const hasLabel = !!state.label

  return (
    <div className="app">
      <Header state={state} />
      {state.blocked &&
        <div className="strip blocked">⛔ ZDJĘCIA ZABLOKOWANE — {state.blocked}</div>}
      {state.warnings?.length > 0 &&
        <div className="strip warn">⚠ {state.warnings.join(' · ')}</div>}
      {hasSession && (
        <div className="sessionbar">
          <span className="sbpath" title={state.session_path}>📁 {state.session_path}</span>
          <button className="sbnew" onClick={newSession}>+ NOWA SESJA</button>
        </div>
      )}

      <div className="main">
        <Preview busy={busy} flash={flash} last={last} />

        <aside className="side">
          {!hasSession ? (
            <StartCard onStart={startSession} dataRoot={state.data_root}
              blocked={state.blocked} />
          ) : (editingLabel || !hasLabel) ? (
            <LabelInput current={state.label} onSet={setLabel}
              onCancel={hasLabel ? () => setEditingLabel(false) : null} />
          ) : (
            <ShootPanel state={state} busy={busy} last={last}
              onShoot={shoot} onChangeLabel={() => setEditingLabel(true)} />
          )}
          <Counts counts={state.counts} active={state.label} rejected={state.rejected} />
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
        {state.profile_id && <span className="prof">{state.profile_id} · {state.shutter_us} µs</span>}
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

function StartCard({ onStart, dataRoot, blocked }) {
  return (
    <div className="card center">
      <p>Rozpocznij sesję — utworzy się folder <code>sesja_…</code> w:</p>
      <code className="path">{dataRoot}</code>
      <button className="big primary" disabled={!!blocked} onClick={onStart}>START SESJI</button>
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
      <button className="big shoot" disabled={busy || !!state.blocked} onClick={onShoot}>
        {busy ? 'ZDJĘCIE…' : '📷 ZRÓB ZDJĘCIE'}
      </button>
      {last && (last.accepted === false ? <Rejected last={last} /> : <Accepted last={last} />)}
    </div>
  )
}

function Accepted({ last }) {
  return (
    <div className="lastshot">
      <img src={thumbUrl(last.label, last.index)} alt={last.png} />
      <div>
        <div className="ok">✓ {last.png}</div>
        {last.dng && <div className="dim">+ {last.dng}</div>}
        <div className="dim">kontrakt akwizycji: ok</div>
        {last.warnings?.map((w, i) => <div key={i} className="warntext">~ {w}</div>)}
      </div>
    </div>
  )
}

// Odrzucenie musi podawać konkretną rozbieżność, nie ogólnik — inaczej operator nie
// wie, co poprawić, a numer ujęcia i tak został (§5, §12.1).
function Rejected({ last }) {
  return (
    <div className="lastshot rejected">
      <div>
        <div className="bad">✗ ODRZUCONE — {last.png}</div>
        {last.violations?.map((v, i) => <div key={i} className="viol">{v}</div>)}
        <div className="dim">
          numer bez zmian, powtórz ujęcie · pliki w odrzucone/{last.label}/
        </div>
      </div>
    </div>
  )
}

function Counts({ counts, active, rejected }) {
  const entries = Object.entries(counts || {})
  if (!entries.length && !rejected) return null
  return (
    <div className="card counts">
      <div className="card-head">ZAPISANE</div>
      {entries.map(([label, n]) => (
        <div key={label} className={`row ${label === active ? 'active' : ''}`}>
          <span className="k">{label}</span><span className="v">{n} zdj.</span>
        </div>
      ))}
      {rejected > 0 && (
        <div className="row rej">
          <span className="k">odrzucone</span><span className="v">{rejected} zdj.</span>
        </div>
      )}
    </div>
  )
}
