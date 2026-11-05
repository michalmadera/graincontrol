import React, { useRef, useState } from 'react'
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

function Gotowa({ stan, wyslij }) {
  return (
    <Tresc tytul="Maszyna gotowa" opis={`Następna próbka: nr ${stan.nastepny_numer}`}>
      {stan.kolejka_pelna
        ? <p className="ostrzezenie" role="alert">Kolejka pełna — powiadom serwis</p>
        : <button className="glowny" onClick={() => wyslij('nowy_pomiar')}>NOWY POMIAR</button>}
      <OstatnieWyniki wyniki={stan.ostatnie_wyniki} />
    </Tresc>
  )
}

function OstatnieWyniki({ wyniki }) {
  if (!wyniki?.length) return null
  return (
    <ul className="ostatnie" aria-label="Ostatnie wyniki">
      {wyniki.map((w) => (
        <li key={w.id_pomiaru}>
          Próbka {w.numer_probki}: {w.blad ? 'błąd analizy' : w.werdykt === 'akceptowalna' ? 'DOBRA' : 'ZŁA'}
          {!w.blad && w.zrodlo_wyniku !== 'model' && ' (TEST)'}
        </li>
      ))}
    </ul>
  )
}

function Przygotowanie() {
  return <Tresc tytul="Maszyna się przygotowuje" opis="Poczekaj, aż ekran poprosi o wsypanie próbki." />
}

function Wsyp({ wyslij }) {
  return (
    <Tresc tytul="Wsyp próbkę do lejka" opis="Gdy skończysz, naciśnij przycisk poniżej.">
      <button className="glowny" onClick={() => wyslij('probka_wsypana')}>PRÓBKA WSYPANA</button>
      <button className="drugorzedny" onClick={() => wyslij('anuluj')}>Anuluj</button>
    </Tresc>
  )
}

function Splyw({ stan }) {
  return <Tresc tytul="Kamyki spływają" opis={`Pozostało ${stan.pozostalo_s ?? 0} s`} />
}

function Rozgarnianie() {
  return <Tresc tytul="Maszyna rozgarnia próbkę" opis="Nie wkładaj rąk do maszyny." />
}

function Zdjecie() {
  return <Tresc tytul="Robię zdjęcie" />
}

function BrakPolaczenia() {
  return <Tresc tytul="Brak połączenia z maszyną" opis="Trwa ponowne łączenie…" />
}

function BladZdjecia({ stan, wyslij }) {
  return (
    <Tresc tytul="Nie udało się zrobić zdjęcia" opis={stan.komunikat}>
      <button className="glowny" onClick={() => wyslij('ponow_zdjecie')}>PONÓW ZDJĘCIE</button>
    </Tresc>
  )
}

function Analiza({ stan, wyslij }) {
  if (stan.serwer_dostepny) {
    return <Tresc tytul="Analizuję…" opis="Wynik pojawi się na ekranie. Poczekaj." />
  }
  return (
    <Tresc tytul="Wynik po przywróceniu łączności" opis="Zdjęcie jest bezpieczne i wyśle się samo. Możesz pracować dalej.">
      <button className="glowny" onClick={() => wyslij('dalej_bez_wyniku')}>DALEJ</button>
    </Tresc>
  )
}

function Wynik({ stan, wyslij }) {
  const w = stan.wynik
  if (w.blad) {
    return (
      <Tresc tytul="Błąd analizy — powiadom serwis" opis={w.blad}>
        <button className="glowny" onClick={() => wyslij('dalej')}>DALEJ</button>
      </Tresc>
    )
  }
  const dobra = w.werdykt === 'akceptowalna'
  return (
    <section className="tresc">
      {/* Decyduje odpowiedź serwera: wszystko poza wynikiem z modelu to tylko test. */}
      {w.zrodlo_wyniku !== 'model' && <p className="test">TEST – wynik niemiarodajny</p>}
      <h1 className={dobra ? 'werdykt dobra' : 'werdykt zla'}>{dobra ? 'DOBRA' : 'ZŁA'}</h1>
      <p className="opis">Kamieni: {w.liczba_kamieni} · wtrąceń: {w.liczba_wtracen} ({w.udzial_wtracen_proc}%)</p>
      <button className="glowny" onClick={() => wyslij('dalej')}>DALEJ</button>
    </section>
  )
}

function Czyszczenie() {
  return <Tresc tytul="Maszyna czyści stół" opis="Nie wkładaj rąk do maszyny." />
}

function Oproznij({ wyslij }) {
  return (
    <Tresc tytul="Opróżnij pudełko na kamyki" opis="Wyjmij pudełko spod stołu, opróżnij je i włóż z powrotem.">
      <button className="glowny" onClick={() => wyslij('oproznione')}>OPRÓŻNIONE</button>
    </Tresc>
  )
}

const CZAS_PRZYTRZYMANIA_MS = 3000

// Przytrzymanie, a nie dotknięcie: wznowienie ma być świadomą decyzją człowieka przy maszynie.
function PrzyciskPrzytrzymaj({ onGotowe, children }) {
  const licznik = useRef(null)
  const [trzyma, setTrzyma] = useState(false)
  const pusc = () => { clearTimeout(licznik.current); setTrzyma(false) }
  const nacisnij = () => {
    setTrzyma(true)
    licznik.current = setTimeout(() => { setTrzyma(false); onGotowe() }, CZAS_PRZYTRZYMANIA_MS)
  }
  return (
    <button className={trzyma ? 'glowny przytrzymaj trzyma' : 'glowny przytrzymaj'}
            onPointerDown={nacisnij} onPointerUp={pusc} onPointerLeave={pusc} onPointerCancel={pusc}
            onContextMenu={(e) => e.preventDefault()}>
      <span className="postep" />
      <span className="napis">{children}</span>
    </button>
  )
}

function Zatrzymana({ wyslij }) {
  return (
    <Tresc tytul="Maszyna zatrzymana" opis="Sprawdź, czy nic jej nie blokuje i czy nikt nie ma rąk w środku.">
      <PrzyciskPrzytrzymaj onGotowe={() => wyslij('wznow')}>PRZYTRZYMAJ, ABY WZNOWIĆ</PrzyciskPrzytrzymaj>
    </Tresc>
  )
}

function Uruchamianie() {
  return <Tresc tytul="Maszyna się uruchamia" opis="Poczekaj chwilę." />
}

function Blad({ stan, wyslij }) {
  return (
    <Tresc tytul="Wystąpił błąd" opis={stan.komunikat}>
      <button className="glowny" onClick={() => wyslij('odblokuj')}>ODBLOKUJ MASZYNĘ</button>
    </Tresc>
  )
}

export const EKRANY = {
  brak_polaczenia: BrakPolaczenia,
  kalibracja: Kalibracja,
  gotowa: Gotowa,
  przygotowanie: Przygotowanie,
  wsyp: Wsyp,
  splyw: Splyw,
  rozgarnianie: Rozgarnianie,
  zdjecie: Zdjecie,
  blad_zdjecia: BladZdjecia,
  analiza: Analiza,
  wynik: Wynik,
  czyszczenie: Czyszczenie,
  oproznij: Oproznij,
  zatrzymana: Zatrzymana,
  uruchamianie: Uruchamianie,
  blad: Blad,
}
