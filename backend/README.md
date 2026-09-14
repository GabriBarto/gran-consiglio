# Backend

API del marketplace di box a sorpresa per piante. Node.js + Express + TypeScript + Prisma + MySQL.

## Setup

1. Installa MySQL 8 (locale o via Docker) e crea un database vuoto.
2. Copia `.env.example` in `.env` e compila i valori (almeno `DATABASE_URL`, `JWT_ACCESS_SECRET`, `JWT_REFRESH_SECRET`).
3. Installa le dipendenze:

   ```bash
   npm install
   ```

4. Applica lo schema al database e genera il client Prisma:

   ```bash
   npm run prisma:migrate
   ```

5. (Opzionale ma consigliato) popola le categorie box e crea un utente admin di sviluppo:

   ```bash
   npm run prisma:seed
   ```

6. Avvia il server in sviluppo:

   ```bash
   npm run dev
   ```

L'API parte su `http://localhost:3000` (configurabile via `PORT`). Healthcheck: `GET /health`.

## Struttura

```
src/
  config/env.ts        variabili d'ambiente tipizzate
  lib/prisma.ts         client Prisma condiviso
  middleware/           auth JWT, controllo ruolo, validazione zod, error handler
  modules/
    auth/                registrazione, verifica email, login, refresh, reset password
    negozio/              CRUD negozio (venditore)
    admin/                approvazione/rifiuto negozi
  utils/                 password (bcrypt), JWT, token monouso, invio email
prisma/schema.prisma    schema del database
prisma/seed.ts          categorie box + admin di sviluppo
```

## API implementate finora

**Auth** (`/api/auth`)
- `POST /register` — registrazione cliente/venditore, invia email di verifica
- `POST /verify-email` — conferma email tramite token
- `POST /login` — richiede email verificata, ritorna access + refresh token
- `POST /refresh` — rotazione refresh token
- `POST /logout` — revoca il refresh token
- `POST /forgot-password` / `POST /reset-password`

**Negozio** (`/api/negozi`, solo ruolo VENDITORE)
- `POST /` — crea il proprio negozio (stato iniziale: `PENDING`)
- `GET /me`, `PATCH /me`

**Admin** (`/api/admin`, solo ruolo ADMIN)
- `GET /negozi?stato=PENDING|APPROVED|REJECTED`
- `POST /negozi/:id/approve`
- `POST /negozi/:id/reject` (richiede `motivo`)

Nota: l'email in sviluppo (senza SMTP configurato) viene stampata in console invece di essere inviata — utile per copiare i link di verifica/reset durante i test manuali.

## Prossimi passi (vedi `../docs/implementation-plan.md` e `../PROGRESS.md`)

- Upload diretto del documento di licenza (oggi si passa un URL già caricato altrove).
- Box, carrello con riserva temporanea dello stock, checkout.
- Integrazione Stripe Connect.
- Notifiche push (FCM), recensioni, funzione AI.
