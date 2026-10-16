# Implementazione Progetto — "Too Good To Go" per le Piante

Ho riletto il tuo `project-work.md`. L'impianto generale (2 ruoli, box a sorpresa, ritiro in presenza) è solido e ricalca bene il modello di riferimento. Mancano però diversi passaggi che, se non affrontati ora, ti bloccheranno in fase di sviluppo o ti esporranno a problemi legali/di business. Li ho organizzati per area.

---

## 1. Autenticazione e sicurezza (assente nel documento originale)

- **Hashing password**: mai salvare `password` in chiaro nel DB — bcrypt/argon2.
- **Verifica email** alla registrazione (link/OTP) prima di poter operare.
- **Recupero password** (flusso "password dimenticata").
- **Token di sessione**: JWT con refresh token, non solo login persistente.
- **Verifica licenza venditore**: chi la controlla? Serve un **pannello admin** (anche minimale) dove un operatore approva/rifiuta il documento caricato, con stato `pending / approved / rejected` sul negozio.

## 2. Modello dati incompleto

Il tuo schema attuale ha `utente`, `box`, `ordine`. Mancano tabelle essenziali:

- **`negozio`** separato da `utente`: nome negozio, orari di apertura, fascia oraria ritiro, posizione (lat/lng), stato verifica licenza. Un venditore ha un negozio, ma tenerli separati evita di sporcare la tabella utenti e serve per la geolocalizzazione/ricerca.
- **`carrello`** e **`carrello_item`**: hai detto "ogni negozio ha il suo carrello" ma non c'è una tabella per questo — serve per gestire più carrelli attivi in parallelo prima del checkout.
- **`recensione`** (id, ordineId, userId, negozioId, voto, testo, data): non presente nello schema DB nonostante sia un'azione cliente.
- **`notifica`**: per lo storico notifiche in-app (nuovo ordine, ordine pronto, ecc.).
- **`categoria_box`**: per gestire i tipi (interno/esterno/sempreverde/fiorita/altezza) in modo relazionale invece che come enum fisso, così puoi aggiungerne altri in futuro.

## 3. Concorrenza sullo stock (rischio critico)

Se due clienti comprano l'ultima box disponibile nello stesso istante, senza gestione della concorrenza **entrambi** potrebbero pagare per una box che esiste una sola volta. Serve:

- Transazione atomica sul decremento di `maxBox - soldBoxes` al momento del pagamento confermato (non al click su "aggiungi al carrello").
- Meccanismo di **riserva temporanea** (es. 10 minuti) quando la box è nel carrello, con rilascio automatico se il pagamento non viene completato.

## 4. Pagamenti (solo accennato, mai definito)

- Scelta del **payment gateway** (Stripe è lo standard per marketplace: supporta split payment/Stripe Connect per pagare direttamente i venditori trattenendo una commissione).
- Definizione della **commissione piattaforma** (% per ordine).
- Gestione **rimborsi**: cosa succede se il cliente non ritira la box nella fascia oraria? Rimborso parziale, nessun rimborso, penalità al venditore?
- **Scontrino/fattura elettronica**: obbligo fiscale italiano da chiarire con un commercialista (hai già segnato "tassazione di servizio" come cosa da controllare — corretto, va fatto prima del lancio).

## 5. Ciclo di vita dell'ordine (mancante)

Non è definito uno **stato dell'ordine**. Serve una macchina a stati tipo:

`in_attesa_pagamento → pagato → pronto_per_ritiro → ritirato → annullato / scaduto`

Questo stato determina cosa vede il venditore, quando parte la notifica, e quando si può lasciare una recensione (solo dopo `ritirato`).

## 6. Notifiche push (menzionata ma non progettata)

- Serve un servizio come **Firebase Cloud Messaging** (gratuito, standard per React Native).
- Notifica al venditore: nuovo ordine ricevuto.
- Notifica al cliente: ordine confermato, box pronta, promemoria fascia oraria ritiro, box in scadenza vicino a te (opzionale, tipo il modello originale).

## 7. Geolocalizzazione (accennata, non specificata tecnicamente)

- Serve un provider mappe: **Google Maps Platform** o **Mapbox** (Mapbox spesso più economico per uso intensivo).
- Calcolo distanza: query geospaziale sul DB (es. PostGIS se Postgres, o calcolo Haversine lato backend).
- Filtri: città, zona, distanza massima — vanno tradotti in una query con raggio in km dal punto utente.

## 8. Funzione AI "scheda di recupero pianta" (nel documento è solo un titolo)

Va specificato meglio, perché cambia molto la complessità:

- **Input**: l'utente carica una foto della pianta, o seleziona la specie da un elenco?
- Se richiede **riconoscimento immagine** della specie → serve un modello di visione (es. API tipo PlantNet, o Claude/GPT-4V) — costo e complessità maggiori.
- Se è solo **testo generato da un prompt** con nome specie + stato → molto più semplice e economico.
- **Disclaimer legale**: hai già notato giustamente che va segnalata come "orientativa" — va scritto anche nei Termini e Condizioni, non solo nell'interfaccia.

## 9. Gestione allergie (menzionata, non implementata)

- Serve un campo su ogni box (o categoria) con eventuali allergeni/rischi (es. pollini), visibile prima dell'acquisto — non è indicato dove nello schema DB.

## 10. Cosa NON è ancora nello schema `box`

- Manca un campo **foto** della box.
- Manca la **categoria** (interno/esterno/sempreverde/fiorita/altezza) — attualmente non c'è modo di collegare una box a questi tag.
- Manca la **fascia oraria di ritiro** — l'hai scritta come nota testuale ma non come campo strutturato, mentre serve per le notifiche automatiche.

## 11. Ruolo Admin (assente)

Serve un terzo ruolo, anche minimale, per:
- Approvare/rifiutare licenze venditori.
- Gestire dispute cliente-venditore.
- Moderare recensioni segnalate.

## 12. Aspetti legali da aggiungere alla tua lista

Oltre a quanto hai già segnato (copyright, T&C, scheda AI, allergie, pagamenti, tassazione):
- **GDPR**: gestisci dati sensibili come documenti di licenza e dati di pagamento — serve una privacy policy conforme e probabilmente non salvare mai i dati carta (li gestisce Stripe/gateway).
- **Policy di cancellazione ordine** e mancato ritiro, da scrivere nei T&C.
- **Responsabilità sulla qualità della pianta**: chi risponde se una pianta arriva danneggiata nonostante il divieto di vendere piante malate?

---

## Schema database aggiornato (proposta)

```
utente (id, role, username, email, password_hash, email_verified, createdAt)

negozio (id, userId, nome, indirizzo, lat, lng, telefono, licenzaUrl,
         statoVerifica['pending'|'approved'|'rejected'], orarioApertura, fasciaRitiro)

box (id, negozioId, nome, descrizione, prezzo, foto, categoria,
     maxBox, soldBoxes, allergeni, dataCreazione, dataScadenza)

carrello (id, userId, negozioId, stato['attivo'|'completato'])
carrello_item (id, carrelloId, boxId, quantita)

ordine (id, userId, negozioId, totalPrice, stato, dataOrdine, fasciaRitiro)
ordine_item (id, ordineId, boxId, quantita, prezzoUnitario)

recensione (id, ordineId, userId, negozioId, voto, testo, data)

notifica (id, userId, tipo, testo, letta, data)
```

---

## Priorità consigliata (roadmap)

1. Autenticazione sicura + verifica email + verifica licenza venditore (base indispensabile)
2. Schema DB completo + gestione stock con concorrenza
3. Flusso base cliente: ricerca negozio → box → carrello → checkout (senza pagamento reale, mock)
4. Integrazione pagamento reale (Stripe Connect)
5. Notifiche push
6. Recensioni
7. Funzione AI (va bene lasciarla per ultima, è la meno bloccante)
8. Pannello admin

---

Fammi sapere se vuoi che approfondisca una di queste aree (es. schema Stripe Connect nel dettaglio, o la macchina a stati dell'ordine) o se preferisci che trasformi questo file in un documento Word.
