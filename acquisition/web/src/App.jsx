import React, { useCallback, useEffect, useRef, useState } from 'react'
import { api, subscribeEvents } from './api.js'
import Session from './Session.jsx'
import { StartSessionModal, DeclareSampleModal } from './Modals.jsx'

export default function App() {
  const [status, setStatus] = useState(null)
  const [session, setSession] = useState(null)
  const [history, setHistory] = useState([])
  const [modal, setModal] = useState(null)          // 'start' | 'sample' | null
  const [busy, setBusy] = useState(false)           // trwa ujęcie
  const [stage, setStage] = useState(null)          // etap ujęcia z SSE
  const [verdict, setVerdict] = useState(null)      // werdykt ostatniego ujęcia
  const [error, setError] = useState(null)
  const sessionId = session?.session_id

  const refreshStatus = useCallback(async () => {
    try { setStatus(await api.status()) } catch (e) { setError(e.message) }
  }, [])

  const refreshSession = useCallback(async () => {
    try {
      const s = await api.getSession()
      setSession(s)
      if (s.status === 'open' && s.session_id) {
        const h = await api.captures(s.session_id, 16)
        setHistory(h.captures)
      } else {
        setHistory([])
      }
    } catch (e) { setError(e.message) }
  }, [])

  useEffect(() => { refreshStatus(); refreshSession() }, [refreshStatus, refreshSession])

  // Pasek stanu odświeżany cyklicznie (kamera, dysk, plik strojenia) — §12.12.
  useEffect(() => {
    const t = setInterval(refreshStatus, 3000)
    return () => clearInterval(t)
  }, [refreshStatus])

  // Strumień zdarzeń: postęp ujęcia i stan kamery bez odpytywania (§12.11).
  const stateRef = useRef({ refreshSession, refreshStatus })
  stateRef.current = { refreshSession, refreshStatus }
  useEffect(() => subscribeEvents((ev) => {
    if (ev.kind === 'capture') {
      setStage(ev.stage)
      if (ev.stage === 'verdict') {
        setVerdict(ev)
        stateRef.current.refreshSession()
        stateRef.current.refreshStatus()
      }
    } else if (ev.kind === 'camera') {
      setStatus((s) => s ? { ...s, camera: { ...s.camera, state: ev.state } } : s)
    } else if (['sample', 'layout', 'session'].includes(ev.kind)) {
      stateRef.current.refreshSession()
    }
  }), [])

  async function onCapture() {
    setBusy(true); setVerdict(null); setStage('preview_stop'); setError(null)
    try {
      const v = await api.capture()
      setVerdict(v)
    } catch (e) { setError(e.message) }
    finally { setBusy(false); setStage(null); refreshSession(); refreshStatus() }
  }

  async function onLayout() {
    setError(null)
    try { await api.advanceLayout(); await refreshSession() }
    catch (e) { setError(e.message) }
  }

  return (
    <div className="app">
      <Session
        status={status}
        session={session}
        history={history}
        busy={busy}
        stage={stage}
        verdict={verdict}
        onCapture={onCapture}
        onLayout={onLayout}
        onChangeSample={() => setModal('sample')}
        onStartSession={() => setModal('start')}
        onEndSession={async () => {
          if (!confirm('Zamknąć sesję i wygenerować raport?')) return
          try { await api.endSession(); setVerdict(null); await refreshSession() }
          catch (e) { setError(e.message) }
        }}
        onDismissVerdict={() => setVerdict(null)}
      />

      {error && (
        <div className="toast error" onClick={() => setError(null)}>{error} ✕</div>
      )}

      {modal === 'start' && (
        <StartSessionModal
          status={status}
          onClose={() => setModal(null)}
          onSubmit={async (body) => {
            try { await api.startSession(body); setModal(null); await refreshSession() }
            catch (e) { setError(e.message) }
          }}
        />
      )}
      {modal === 'sample' && (
        <DeclareSampleModal
          study={status?.study}
          current={session?.sample}
          onClose={() => setModal(null)}
          onSubmit={async (body) => {
            try { await api.declareSample(body); setModal(null); await refreshSession() }
            catch (e) { setError(e.message) }  // walidacja §8/§9 zwrócona przez silnik
          }}
        />
      )}
    </div>
  )
}
