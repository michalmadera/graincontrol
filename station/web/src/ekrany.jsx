import React, { useEffect, useRef, useState } from 'react'
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
        : stan.skanowanie_wlaczone
          ? <PoleSkanu onKod={(kod) => wyslij('nowy_pomiar', { kod_partii: kod })} />
          : <button className="glowny" onClick={() => wyslij('nowy_pomiar')}>NOWY POMIAR</button>}
      <OstatnieWyniki wyniki={stan.ostatnie_wyniki} />
    </Tresc>
  )
}

// Czytnik USB działa jak klawiatura i kończy kod Enterem, więc pole musi trzymać fokus.
function PoleSkanu({ onKod }) {
  const [kod, setKod] = useState('')
  const pole = useRef(null)
  useEffect(() => { pole.current?.focus() })
  return (
    <form className="skan" onSubmit={(e) => { e.preventDefault(); onKod(kod); setKod('') }}>
      <label htmlFor="kod">Zeskanuj kod partii</label>
      <input id="kod" ref={pole} value={kod} autoComplete="off" onChange={(e) => setKod(e.target.value)} />
    </form>
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

function Oczekiwanie() {
  return <Tresc tytul="Maszyna kończy poprzedni ruch" opis="Poczekaj. Nie wkładaj rąk do maszyny." />
}

function Blad({ stan, wyslij }) {
  return (
    <Tresc tytul="Wystąpił błąd" opis={stan.komunikat}>
      <button className="glowny" onClick={() => wyslij('odblokuj')}>ODBLOKUJ MASZYNĘ</button>
    </Tresc>
  )
}

function Licznik({ etykieta, wartosc, krok, min, jednostka, onZmiana }) {
  return (
    <div className="pole">
      <span className="etykieta">{etykieta}</span>
      <button aria-label={`${etykieta}: mniej`} onClick={() => onZmiana(Math.max(min, wartosc - krok))}>−</button>
      <output aria-label={etykieta}>{wartosc}{jednostka}</output>
      <button aria-label={`${etykieta}: więcej`} onClick={() => onZmiana(wartosc + krok)}>+</button>
    </div>
  )
}

function Serwis({ stan, wyslij }) {
  const [potwierdzenie, setPotwierdzenie] = useState(false)
  const u = stan.ustawienia
  const zmien = (zmiany) => wyslij('serwis_ustawienia', zmiany)
  return (
    <section className="serwis">
      <div className="kolumna">
        <h1>Tryb serwisowy</h1>
        <div className="siatka">
          {['GORA_5MM', 'DOL_5MM', 'GORA_1MM', 'DOL_1MM'].map((ruch) => (
            <button key={ruch} disabled={stan.trwa} onClick={() => wyslij('serwis_ruch', { ruch })}>
              {{ GORA_5MM: 'Stół w górę 5 mm', DOL_5MM: 'Stół w dół 5 mm', GORA_1MM: 'Stół w górę 1 mm', DOL_1MM: 'Stół w dół 1 mm' }[ruch]}
            </button>
          ))}
        </div>
        {stan.komunikat && <p className="ostrzezenie maly" role="alert">{stan.komunikat}</p>}
        <img className="podglad" src="/api/podglad.mjpg" alt="Podgląd kamery" />
      </div>
      <div className="kolumna">
        <Licznik etykieta="Czas spływu" wartosc={u.czas_splywu_s} krok={5} min={0} jednostka=" s" onZmiana={(w) => zmien({ czas_splywu_s: w })} />
        <Licznik etykieta="Szczelina" wartosc={u.szczelina_mm ?? 0.5} krok={0.5} min={0.5} jednostka=" mm" onZmiana={(w) => zmien({ szczelina_mm: w })} />
        <Licznik etykieta="Opróżnianie co" wartosc={u.oproznianie_co_n} krok={1} min={1} jednostka="" onZmiana={(w) => zmien({ oproznianie_co_n: w })} />
        <Licznik etykieta="Limit kolejki" wartosc={u.limit_kolejki} krok={10} min={1} jednostka="" onZmiana={(w) => zmien({ limit_kolejki: w })} />
        <button className={u.skanowanie_wlaczone ? 'przelacznik wlaczony' : 'przelacznik'} aria-pressed={u.skanowanie_wlaczone}
                onClick={() => zmien({ skanowanie_wlaczone: !u.skanowanie_wlaczone })}>
          Skanowanie kodów: {u.skanowanie_wlaczone ? 'włączone' : 'wyłączone'}
        </button>
        {potwierdzenie
          ? <button className="przelacznik niebezpieczny" onClick={() => { setPotwierdzenie(false); wyslij('serwis_reset_numeracji', { potwierdzam: true }) }}>Potwierdź reset numeracji</button>
          : <button className="przelacznik" onClick={() => setPotwierdzenie(true)}>Następny numer: {stan.nastepny_numer} (reset)</button>}
        <button className="glowny maly" disabled={stan.trwa} onClick={() => wyslij('serwis_wyjdz')}>WYJDŹ</button>
      </div>
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
  czyszczenie: Czyszczenie,
  oproznij: Oproznij,
  zatrzymana: Zatrzymana,
  uruchamianie: Uruchamianie,
  blad: Blad,
  oczekiwanie: Oczekiwanie,
  serwis: Serwis,
}
