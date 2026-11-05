import React, { useEffect, useRef, useState } from 'react'
import { pobierzStan, akcja, stop } from './api.js'
import { EKRANY } from './ekrany.jsx'

const ODSWIEZANIE_MS = 300

export default function App() {
  const [stan, setStan] = useState(null)
  const [brakStacji, setBrakStacji] = useState(false)
  const [blad, setBlad] = useState(null)

  useEffect(() => {
    let aktywny = true
    const odswiez = async () => {
      try {
        const nowy = await pobierzStan()
        if (aktywny) { setStan(nowy); setBrakStacji(false) }
      } catch {
        if (aktywny) setBrakStacji(true)
      }
    }
    odswiez()
    const id = setInterval(odswiez, ODSWIEZANIE_MS)
    return () => { aktywny = false; clearInterval(id) }
  }, [])

  // Komunikat dotyczy ekranu, na którym się pojawił.
  const ekran = stan?.ekran
  useEffect(() => { setBlad(null) }, [ekran])

  const wTrakcie = useRef(false)
  const wyslij = async (nazwa, cialo) => {
    if (wTrakcie.current) return      // podwójne dotknięcie nie może wysłać akcji dwa razy
    wTrakcie.current = true
    setBlad(null)
    try {
      setStan(await akcja(nazwa, cialo))
    } catch (e) {
      setBlad(e.message)
    } finally {
      wTrakcie.current = false
    }
  }

  const zatrzymaj = async () => {
    try {
      setStan(await stop())
    } catch (e) {
      setBlad(e.message)
    }
  }

  if (brakStacji || !stan) {
    return <div className="aplikacja"><Tresc tytul={brakStacji ? 'Brak połączenia ze stacją' : 'Uruchamianie…'} /></div>
  }
  const Ekran = EKRANY[stan.ekran] ?? (() => <Tresc tytul="Nieznany stan" opis={stan.ekran} />)
  return (
    <div className="aplikacja">
      <header className="pasek">
        <span className="tytul">GrainControl</span>
        {stan.numer_probki && <span className="numer">Próbka nr {stan.numer_probki}</span>}
        {(!stan.serwer_dostepny || stan.w_kolejce > 1) && (
          <span className={stan.serwer_dostepny ? 'lacznosc' : 'lacznosc offline'}>
            {stan.serwer_dostepny ? 'Serwer działa' : 'Brak łączności z serwerem'} · w kolejce: {stan.w_kolejce}
          </span>
        )}
        <button className="stop" onClick={zatrzymaj}>STOP</button>
      </header>
      <Kroki ekran={stan.ekran} />
      <main className="glowna">
        <Ekran stan={stan} wyslij={wyslij} />
        {blad && <p className="blad" role="alert">{blad}</p>}
      </main>
    </div>
  )
}

const KROKI = [
  ['Ustawienie', ['przygotowanie']],
  ['Wsyp próbkę', ['wsyp']],
  ['Rozgarnianie', ['splyw', 'rozgarnianie']],
  ['Zdjęcie', ['zdjecie', 'blad_zdjecia']],
  ['Analiza', ['analiza']],
  ['Wynik', ['wynik']],
  ['Czyszczenie', ['czyszczenie']],
]

function Kroki({ ekran }) {
  const biezacy = KROKI.findIndex(([, ekrany]) => ekrany.includes(ekran))
  if (biezacy < 0) return null
  return (
    <ol className="kroki">
      {KROKI.map(([nazwa], i) => (
        <li key={nazwa} className={i === biezacy ? 'teraz' : i < biezacy ? 'zrobione' : ''}
            aria-current={i === biezacy ? 'step' : undefined}>{i + 1}. {nazwa}</li>
      ))}
    </ol>
  )
}

export function Tresc({ tytul, opis, children }) {
  return (
    <section className="tresc">
      <h1>{tytul}</h1>
      {opis && <p className="opis">{opis}</p>}
      {children}
    </section>
  )
}
