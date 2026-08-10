import React from 'react'

const STAGE_LABEL = {
  preview_stop: 'zatrzymanie podglądu…',
  exposure: 'ekspozycja…',
  save: 'zapis…',
  verdict: 'gotowe',
}

export default function Session(props) {
  const { status, session, history, busy, stage, verdict } = props
  // 'none' = brak sesji; 'pending' = parametry sesji zapamiętane, ale session.json
  // powstanie dopiero przy pierwszej deklaracji próbki (sprzężenie silnika);
  // 'open' = sesja zapisana. W 'pending' i 'open' bez próbki prowadzimy do deklaracji.
  const started = session?.status === 'open' || session?.status === 'pending'
  const sample = session?.sample

  return (
    <div className="session">
      <Header status={status} session={session} onEndSession={props.onEndSession} />
      <StatusStrip status={status} />

      <div className="main">
        <Preview busy={busy} stage={stage} />

        <aside className="side">
          {!started ? (
            <StartCard onStart={props.onStartSession} />
          ) : !sample ? (
            <NoSampleCard onChange={props.onChangeSample} pending={session?.status === 'pending'} />
          ) : (
            <>
              <SamplePanel sample={sample} onChange={props.onChangeSample} />
              <CaptureButtons
                sample={sample}
                busy={busy}
                stage={stage}
                onCapture={props.onCapture}
                onLayout={props.onLayout}
              />
            </>
          )}
        </aside>
      </div>

      {verdict && <VerdictBar verdict={verdict} onDismiss={props.onDismissVerdict} />}
      <HistoryBar history={history} />
    </div>
  )
}

function Header({ status, session, onEndSession }) {
  const cam = status?.camera?.state || '—'
  const camOk = cam === 'idle' || cam === 'preview'
  return (
    <header className="header">
      <div className="hleft">
        {session?.status === 'open'
          ? <><b>SESJA {session.session_id}</b> · profil {session.profile_id} · operator {session.operator}</>
          : session?.status === 'pending'
          ? <b>Sesja przygotowana — zadeklaruj próbkę</b>
          : <b>Brak otwartej sesji</b>}
      </div>
      <div className="hright">
        <span className={`cam ${camOk ? 'ok' : 'warn'}`}>● kamera {cam}</span>
        {session?.status === 'open' &&
          <button className="link" onClick={onEndSession}>zamknij sesję</button>}
      </div>
    </header>
  )
}

// Pasek stanu — blokady widoczne cały czas, nie jednorazowy komunikat (§12.12).
function StatusStrip({ status }) {
  if (!status) return null
  const alerts = []
  if (!status.tuning_present) alerts.push('brak pliku strojenia')
  if (status.disk_free_gb !== null && status.disk_free_gb < 5) alerts.push(`mało miejsca: ${status.disk_free_gb} GB`)
  if (status.calibration_missing?.length) alerts.push(`brak kalibracji: ${status.calibration_missing.join(', ')}`)
  if (!alerts.length) return null
  return <div className="strip warn">⚠ {alerts.join(' · ')}</div>
}

function Preview({ busy, stage }) {
  return (
    <div className="preview">
      <img src="/api/preview.mjpg" alt="podgląd na żywo" />
      <div className="pv-caption">PODGLĄD NA ŻYWO · na parametrach profilu</div>
      {busy && (
        <div className="pv-overlay">
          <div className="spinner" />
          <div>{STAGE_LABEL[stage] || 'ujęcie…'}</div>
        </div>
      )}
    </div>
  )
}

function StartCard({ onStart }) {
  return (
    <div className="card center">
      <p>Rozpocznij sesję, aby zbierać materiał.</p>
      <button className="big primary" onClick={onStart}>START SESJI</button>
    </div>
  )
}

function NoSampleCard({ onChange, pending }) {
  return (
    <div className="card center">
      <p>{pending
        ? 'Sesja przygotowana. Zadeklaruj pierwszą próbkę (§8) — wtedy zapisze się sesja i odblokują ujęcia.'
        : 'Zadeklaruj próbkę (§8), aby odblokować ujęcia.'}</p>
      <button className="big primary" onClick={onChange}>DEKLARUJ PRÓBKĘ</button>
    </div>
  )
}

function SamplePanel({ sample, onChange }) {
  return (
    <div className="card sample">
      <div className="card-head">PRÓBKA <button className="link" onClick={onChange}>zmień</button></div>
      <Row k="dostawa" v={sample.batch_id} />
      <Row k="próbka" v={sample.sample_id} />
      <Row k="werdykt" v={sample.expert_verdict + (sample.verdict_reasons?.length ? ' · ' + sample.verdict_reasons.join(', ') : '')} />
      <Row k="etap" v={sample.protocol_stage} />
      <div className="counters">
        <span>ułożenie <b>{sample.layout_seq}</b></span>
        <span>ujęcie <b>{sample.frame_seq}</b></span>
      </div>
    </div>
  )
}

function Row({ k, v }) {
  return <div className="row"><span className="k">{k}</span><span className="v">{v}</span></div>
}

function CaptureButtons({ sample, busy, stage, onCapture, onLayout }) {
  const stageA = sample.protocol_stage === 'A'   // A: „przesypałem" zablokowane (§9)
  return (
    <div className="buttons">
      <button className="big shoot" disabled={busy} onClick={onCapture}>
        {busy ? (STAGE_LABEL[stage] || 'UJĘCIE…') : 'ZRÓB ZDJĘCIE'}
      </button>
      <button className="big refill" disabled={busy || stageA} onClick={onLayout}
        title={stageA ? 'Etap A — przesypywanie zablokowane' : ''}>
        PRZESYPAŁEM MATERIAŁ
      </button>
      {sample.protocol_stage === 'B' &&
        <div className="hint">Etap B — po ujęciu przesyp materiał (§9).</div>}
    </div>
  )
}

function VerdictBar({ verdict, onDismiss }) {
  const ok = verdict.verdict === 'ok'
  const qcReject = verdict.verdict === 'qc_rejected'
  const cls = ok ? 'good' : (qcReject ? 'warn' : 'bad')
  const label = ok ? '✓ ZAPISANE'
    : qcReject ? '⚠ ZAPISANE, ale QC odrzuca'
    : verdict.verdict === 'error' ? '✕ BŁĄD UJĘCIA' : '✕ ODRZUCONE'
  const reasons = verdict.qc?.reject_reasons?.length
    ? 'QC: ' + verdict.qc.reject_reasons.join(', ')
    : (verdict.contract_status && verdict.contract_status !== 'ok'
        ? 'kontrakt: ' + verdict.contract_status : (verdict.engine_stderr || ''))
  return (
    <div className={`verdict ${cls}`} onClick={onDismiss}>
      <b>{label}</b>
      {verdict.capture_id && <span className="cid">{verdict.capture_id}</span>}
      {reasons && <span className="rsn">{reasons}</span>}
      {verdict.qc?.warnings?.length ? <span className="rsn">ostrzeżenia: {verdict.qc.warnings.join(', ')}</span> : null}
    </div>
  )
}

function HistoryBar({ history }) {
  return (
    <div className="history">
      <span className="htitle">OSTATNIE</span>
      {history.length === 0 && <span className="hempty">— brak ujęć w tej sesji —</span>}
      {history.map((c) => {
        const ok = (c.contract_status === 'ok')
        return (
          <span key={c.capture_id} className={`chip ${ok ? 'ok' : 'bad'}`}
            title={c.capture_id}>
            L{String(c.layout_seq).padStart(2, '0')}F{String(c.frame_seq).padStart(2, '0')} {ok ? '✓' : '✗'}
          </span>
        )
      })}
    </div>
  )
}
