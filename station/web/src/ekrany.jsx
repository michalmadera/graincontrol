import React from 'react'
import { Tresc } from './App.jsx'

function Kalibracja({ stan, wyslij }) {
  if (stan.trwa) {
    return <Tresc tytul="Maszyna się ustawia" opis="To potrwa około 2 minut. Nie wkładaj rąk do maszyny." />
  }
  return (
    <Tresc tytul="Maszyna musi się ustawić" opis="Upewnij się, że nic nie blokuje maszyny, i naciśnij przycisk.">
      <button className="glowny" onClick={() => wyslij('kalibruj')}>USTAW MASZYNĘ</button>
    </Tresc>
  )
}

function Gotowa() {
  return <Tresc tytul="Maszyna gotowa" />
}

function BrakPolaczenia() {
  return <Tresc tytul="Brak połączenia z maszyną" opis="Trwa ponowne łączenie…" />
}

export const EKRANY = {
  brak_polaczenia: BrakPolaczenia,
  kalibracja: Kalibracja,
  gotowa: Gotowa,
}
