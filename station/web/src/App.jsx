import React, { useEffect, useRef, useState } from 'react'
import { pobierzStan, akcja, stop } from './api.js'
import { EKRANY } from './ekrany.jsx'

const ODSWIEZANIE_MS = 300
const BLOKADA_PO_ZMIANIE_MS = 800

export default function App() {
  const [stan, setStan] = useState(null)
  const [brakStacji, setBrakStacji] = useState(false)
  const [blad, setBlad] = useState(null)
  const [stopNieDotarl, setStopNieDotarl] = useState(false)
  const [zablokowany, setZablokowany] = useState(false)

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
  useEffect(() => {
    setBlad(null)
    // Główny przycisk bywa w tym samym miejscu na kolejnym ekranie, a tam może uruchamiać ruch:
    // podwójne dotknięcie albo drganie styku nie może nacisnąć go przypadkiem.
    setZablokowany(true)
    const id = setTimeout(() => setZablokowany(false), BLOKADA_PO_ZMIANIE_MS)
    return () => clearTimeout(id)
  }, [ekran])

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
      setStopNieDotarl(false)
    } catch {
      setStopNieDotarl(true)
    }
  }

  const Ekran = stan && (EKRANY[stan.ekran] ?? (() => <Tresc tytul="Nieznany stan" opis={stan.ekran} />))
  return (
    <div className="aplikacja">
      {/* Pasek ze STOP jest zawsze, także gdy odpytanie stacji się nie udało. */}
      <header className="pasek">
        <Logo wyslij={wyslij} />
        {stan?.numer_probki && <span className="numer">Próbka nr {stan.numer_probki}</span>}
        {stan && (!stan.serwer_dostepny || stan.w_kolejce > 1) && (
          <span className={stan.serwer_dostepny ? 'lacznosc' : 'lacznosc offline'}>
            {stan.serwer_dostepny ? 'Serwer działa' : 'Brak łączności z serwerem'} · w kolejce: {stan.w_kolejce}
          </span>
        )}
        <button className="stop" onClick={zatrzymaj}>STOP</button>
      </header>
      {(stopNieDotarl || stan?.stop_nieudany) && (
        <p className="alarm" role="alert">STOP NIE DOTARŁ DO MASZYNY — odłącz zasilanie maszyny</p>
      )}
      {stan && !brakStacji && <Kroki ekran={stan.ekran} />}
      <main className="glowna">
        {brakStacji || !stan
          ? <Tresc tytul={brakStacji ? 'Brak połączenia ze stacją' : 'Uruchamianie…'}
                   opis={brakStacji ? 'Nie wkładaj rąk do maszyny. Trwa ponowne łączenie…' : undefined} />
          : (
            <fieldset className="ekran" disabled={zablokowany}>
              <Ekran stan={stan} wyslij={wyslij} />
              {blad && <p className="blad" role="alert">{blad}</p>}
            </fieldset>
          )}
      </main>
    </div>
  )
}

const CZAS_WEJSCIA_SERWIS_MS = 5000

// Wejście ukryte przed robotnikiem: przytrzymanie napisu przez 5 s (jak E-07 w spec-operacyjny).
function Logo({ wyslij }) {
  const licznik = useRef(null)
  const pusc = () => clearTimeout(licznik.current)
  useEffect(() => pusc, [])
  return (
    <span className="tytul" data-testid="logo"
          onPointerDown={() => { licznik.current = setTimeout(() => wyslij('serwis_wejdz'), CZAS_WEJSCIA_SERWIS_MS) }}
          onPointerUp={pusc} onPointerLeave={pusc} onPointerCancel={pusc}
          onContextMenu={(e) => e.preventDefault()}>GrainControl</span>
  )
}

const KROKI = [
  ['Przygotowanie', ['przygotowanie']],
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
