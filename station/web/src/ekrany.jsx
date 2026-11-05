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

function Gotowa({ stan, wyslij }) {
  return (
    <Tresc tytul="Maszyna gotowa" opis={`Następna próbka: nr ${stan.nastepny_numer}`}>
      <button className="glowny" onClick={() => wyslij('nowy_pomiar')}>NOWY POMIAR</button>
    </Tresc>
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

function Analiza() {
  return <Tresc tytul="Analizuję…" opis="Wynik pojawi się na ekranie. Poczekaj." />
}

function Wynik({ stan, wyslij }) {
  const w = stan.wynik
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
}
