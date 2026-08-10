import React, { useState } from 'react'

function Modal({ title, onClose, children, footer }) {
  return (
    <div className="backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">{title}<button className="link" onClick={onClose}>✕</button></div>
        <div className="modal-body">{children}</div>
        <div className="modal-foot">{footer}</div>
      </div>
    </div>
  )
}

export function StartSessionModal({ status, onClose, onSubmit }) {
  const [operator, setOperator] = useState(status?.operator || '')
  const [temperature, setTemperature] = useState('')
  const [illuminator, setIlluminator] = useState('')
  const [notes, setNotes] = useState('')
  const needsWaiver = (status?.calibration_missing?.length || 0) > 0
  const [noCalib, setNoCalib] = useState(false)

  function submit() {
    onSubmit({
      operator: operator || null,
      temperature: temperature ? Number(temperature) : null,
      illuminator_on_since: illuminator || null,
      session_notes: notes || null,
      no_calibration: noCalib,
    })
  }
  const blocked = needsWaiver && !noCalib

  return (
    <Modal title="Start sesji" onClose={onClose}
      footer={<button className="big primary" disabled={blocked} onClick={submit}>ROZPOCZNIJ</button>}>
      <Field label="Operator"><input value={operator} onChange={(e) => setOperator(e.target.value)} /></Field>
      <Field label="Temperatura otoczenia [°C]"><input type="number" value={temperature} onChange={(e) => setTemperature(e.target.value)} /></Field>
      <Field label="Oświetlacz włączony od (ISO / opis)"><input value={illuminator} onChange={(e) => setIlluminator(e.target.value)} placeholder="np. 2026-08-10T14:00" /></Field>
      <Field label="Uwagi o warunkach"><input value={notes} onChange={(e) => setNotes(e.target.value)} /></Field>
      {needsWaiver && (
        <label className="check warn">
          <input type="checkbox" checked={noCalib} onChange={(e) => setNoCalib(e.target.checked)} />
          Świadomie startuję bez kalibracji ({status.calibration_missing.join(', ')}) — flaga trafi do każdego rekordu (§7)
        </label>
      )}
    </Modal>
  )
}

export function DeclareSampleModal({ study, current, onClose, onSubmit }) {
  const verdicts = study?.verdicts || ['OK', 'NOK', 'graniczny', 'nieoceniony']
  const stages = study?.protocol_stages || ['A', 'B', 'C', 'D', 'E', 'F', 'inne']
  const vocab = study?.verdict_reasons_vocabulary || []

  const [f, setF] = useState({
    batch: current?.batch_id || '', sample: current?.sample_id || '',
    supplier: current?.supplier || '', material: current?.material_type || '',
    verdict: current?.expert_verdict || verdicts[0], verdict_author: current?.verdict_author || '',
    stage: current?.protocol_stage || 'inne', notes: current?.notes || '',
    verdict_date: '',
  })
  const [reasons, setReasons] = useState(new Set(current?.verdict_reasons || []))
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })
  const toggle = (r) => () => {
    const n = new Set(reasons); n.has(r) ? n.delete(r) : n.add(r); setReasons(n)
  }

  // Podpowiedzi §9 (silnik i tak wymusza — tu prowadzimy operatora).
  const stageE = f.stage === 'E'
  const stageD = f.stage === 'D'
  const hints = []
  if (stageD && f.verdict !== 'OK') hints.push('Etap D — wymagany werdykt OK.')
  if (stageE && !['NOK', 'graniczny'].includes(f.verdict)) hints.push('Etap E — werdykt NOK albo graniczny.')
  if (stageE && reasons.size === 0) hints.push('Etap E — wskaż co najmniej jedną przyczynę.')
  const required = ['batch', 'sample', 'supplier', 'material', 'verdict_author']
  const missing = required.filter((k) => !f[k].trim())

  function submit() {
    onSubmit({ ...f, reasons: [...reasons].join(','), verdict_date: f.verdict_date || null,
      notes: f.notes || null })
  }

  return (
    <Modal title="Deklaracja próbki" onClose={onClose}
      footer={<>
        {hints.map((h, i) => <span key={i} className="foot-hint">{h}</span>)}
        <button className="big primary" disabled={missing.length > 0} onClick={submit}>ZAPISZ PRÓBKĘ</button>
      </>}>
      <div className="grid2">
        <Field label="Dostawa (batch)"><input value={f.batch} onChange={set('batch')} /></Field>
        <Field label="Próbka (sample)"><input value={f.sample} onChange={set('sample')} /></Field>
        <Field label="Dostawca"><input value={f.supplier} onChange={set('supplier')} /></Field>
        <Field label="Materiał / frakcja"><input value={f.material} onChange={set('material')} /></Field>
        <Field label="Werdykt eksperta">
          <select value={f.verdict} onChange={set('verdict')}>
            {verdicts.map((v) => <option key={v}>{v}</option>)}
          </select>
        </Field>
        <Field label="Etap protokołu">
          <select value={f.stage} onChange={set('stage')}>
            {stages.map((s) => <option key={s}>{s}</option>)}
          </select>
        </Field>
        <Field label="Oceniający"><input value={f.verdict_author} onChange={set('verdict_author')} /></Field>
        <Field label="Data werdyktu (opc.)"><input type="date" value={f.verdict_date} onChange={set('verdict_date')} /></Field>
      </div>
      <Field label="Przyczyny (słownik kontrolowany §8)">
        <div className="chips">
          {vocab.map((r) => (
            <button key={r} type="button" className={`chip pick ${reasons.has(r) ? 'on' : ''}`} onClick={toggle(r)}>{r}</button>
          ))}
          {vocab.length === 0 && <span className="hempty">— słownik pusty —</span>}
        </div>
      </Field>
      <Field label="Notatki"><input value={f.notes} onChange={set('notes')} /></Field>
    </Modal>
  )
}

function Field({ label, children }) {
  return <label className="field"><span>{label}</span>{children}</label>
}
