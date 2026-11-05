import React, { useEffect, useState } from 'react'
import { pobierzStan, akcja } from './api.js'
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

  const wyslij = async (nazwa, cialo) => {
    setBlad(null)
    try {
      setStan(await akcja(nazwa, cialo))
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
      </header>
      <main className="glowna">
        <Ekran stan={stan} wyslij={wyslij} />
        {blad && <p className="blad" role="alert">{blad}</p>}
      </main>
    </div>
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
