# Stato di avanzamento

Tracker rispetto alla roadmap in [`docs/implementation-plan.md`](docs/implementation-plan.md).

Stack scelto: **Node.js + Express + Prisma** (backend), **MySQL** (DB), **React Native / Expo** (app, non ancora scaffoldata).

## 1. Autenticazione sicura + verifica email + verifica licenza venditore
- [x] Hashing password (bcrypt, 12 salt rounds)
- [x] Registrazione con verifica email (token opaco, scadenza configurabile)
- [x] Login con JWT access token + refresh token (rotazione + revoca in DB)
- [x] Recupero password ("password dimenticata")
- [x] Negozio con stato `PENDING/APPROVED/REJECTED` + endpoint admin per approvare/rifiutare
- [ ] Upload diretto del file di licenza (oggi si passa solo un URL già caricato altrove)
- [ ] Rate limiting su login/register/forgot-password (da aggiungere prima della produzione)

## 2. Schema DB completo + gestione stock con concorrenza
- [x] Schema Prisma completo: utente, negozio, box, categoria_box, carrello, carrello_item,
      ordine, ordine_item, recensione, notifica (+ tabelle token per l'auth)
- [ ] Transazione atomica sul decremento stock al pagamento confermato
- [ ] Riserva temporanea della box nel carrello (campo `riservatoFino` già nello schema, manca la logica)

## 3. Flusso base cliente (ricerca → box → carrello → checkout mock)
- [ ] Non iniziato

## 4. Pagamenti (Stripe Connect)
- [ ] Non iniziato

## 5. Notifiche push (FCM)
- [ ] Non iniziato (tabella `notifica` già presente nello schema)

## 6. Recensioni
- [ ] Non iniziato (tabella `recensione` già presente nello schema)

## 7. Funzione AI "scheda di recupero pianta"
- [ ] Non iniziato — da chiarire: riconoscimento immagine vs testo da prompt (vedi punto 8 del piano)

## 8. Pannello admin
- [x] Endpoint API per approvazione/rifiuto negozi
- [ ] Interfaccia (oggi solo API, nessuna UI)

---

## Come continuare da qui

1. `cd backend`, segui il [`README.md`](backend/README.md) per lo setup locale (MySQL + `.env` + migrazioni).
2. Prossimo blocco consigliato: box + carrello con riserva temporanea (punto 3 del piano),
   perché sblocca il primo flusso cliente end-to-end anche senza pagamento reale.
3. Scaffolding dell'app React Native/Expo, ancora da avviare.
