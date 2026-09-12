# Backend — Gran Consiglio / TooGood

API in Python (FastAPI). Non esiste ancora un database esterno, quindi i
dati vivono in memoria (`app/database.py`), seedati con alcuni account/negozi
fittizi all'avvio — vedi [Dati fittizi](#dati-fittizi-seed) più sotto.
Nessun'altra parte dell'app dovrebbe dover cambiare quando arriverà un DB
vero: ogni modulo parla solo con `app.database.db`.

## 1. Autenticazione e gestione utenti

| Requisito | Dove |
|---|---|
| Registrazione cliente/venditore con validazione (email/username univoci, password) | `POST /auth/register/customer`, `POST /auth/register/vendor` — [app/routers/auth.py](app/routers/auth.py), regole condivise in [app/validation.py](app/validation.py) (porting di `src/validation.js` del frontend) |
| Hashing password con passlib (bcrypt/argon2) | [app/security.py](app/security.py) — `CryptContext(schemes=["argon2", "bcrypt"])` |
| Verifica email via link/OTP | `POST /auth/verify-email`, `POST /auth/verify-email/resend` — accetta sia il token del link sia il codice OTP a 6 cifre; invio email in [app/email_utils.py](app/email_utils.py) |
| Login con JWT + refresh token | `POST /auth/login` (python-jose) — [app/security.py](app/security.py) |
| "Password dimenticata" con token temporaneo | `POST /auth/forgot-password`, `POST /auth/reset-password` |
| Upload/gestione documento licenza venditore (storage esterno, non su DB) | `POST /auth/register/vendor` (multipart), `PUT /users/me/license` — [app/storage.py](app/storage.py) (fake S3/Cloud Storage: salva su disco e restituisce solo un URL, mai il file nel "DB") |
| Upgrade cliente → venditore | `POST /users/me/upgrade-to-vendor` (richiede login) — [app/routers/users.py](app/routers/users.py) |

Endpoint `GET /users/me` incluso come utility per leggere il profilo
autenticato.

## 2. Gestione negozi (venditori)

| Requisito | Dove |
|---|---|
| CRUD negozio (nome, indirizzo, città, lat/lng, telefono, orari apertura, fascia ritiro) | `POST /shops`, `GET /shops/me`, `PUT /shops/me`, `DELETE /shops/me` (tutti vendor-only, un negozio per venditore) — [app/routers/shops.py](app/routers/shops.py). Schema orari/ritiro in `schemas.DaySchedule` (una voce per giorno della settimana, `HH:MM` 24h, o `closed: true`) |
| Stato verifica licenza (pending/approved/rejected), modificabile solo dall'admin | `GET /admin/shops` (coda di revisione, filtrabile per stato), `PATCH /admin/shops/{shop_id}/license-status` — [app/routers/admin.py](app/routers/admin.py). Il payload di creazione/modifica del vendor (`ShopRequest`) non ha nemmeno il campo `license_status`: strutturalmente non può auto-approvarsi |
| Ricerca negozi per città/zona/distanza | `GET /shops?city=...&lat=...&lng=...&radius_km=...&limit=...&offset=...` — Haversine puro in Python ([app/geo.py](app/geo.py)), niente PostGIS. Mostra solo negozi `approved`; se sono passati `lat`/`lng` i risultati sono ordinati per distanza e ogni negozio riporta `distance_km` |

`GET /shops/{shop_id}` è pubblico ma nasconde (404, non 403, per non far
trapelare l'esistenza) i negozi non approvati a chiunque non ne sia il
proprietario o un admin.

## Setup

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Copia `.env.example` in `.env` solo se vuoi cambiare i default (già validi
per lo sviluppo locale: `SECRET_KEY` di dev, email in console, storage su
`backend/uploads/`).

## Avvio

Da dentro `backend/` (dove hai già creato il venv):

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Docs interattive Swagger su http://127.0.0.1:8000/docs.

## Test

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Copre l'intero flusso: registrazione → verifica email (OTP) → login →
refresh (con rotazione), registrazione venditore con upload licenza,
forgot/reset password, upgrade cliente→venditore ([tests/test_auth.py](tests/test_auth.py)),
più CRUD negozio, RBAC admin/vendor, ricerca per città/distanza/raggio con
verifica numerica della formula di Haversine, paginazione, visibilità dei
negozi non approvati ([tests/test_shops.py](tests/test_shops.py)).

## Dati fittizi (seed)

Poiché non c'è ancora un DB esterno, all'avvio vengono creati alcuni
account/negozi di prova (vedi `seed_fake_data()` in [app/database.py](app/database.py)),
tutti con password `Password123`:

| Email | Ruolo | Note |
|---|---|---|
| `cliente.demo@example.com` | customer | email già verificata |
| `vivaio.rossi@example.com` | vendor | licenza `approved`; negozio "Vivaio Rossi" a Firenze, `approved` (visibile in ricerca) |
| `ortofrutta.bianchi@example.com` | vendor | licenza `pending_review`; negozio "Ortofrutta Bianchi" a Bologna, `pending_review` (visibile solo al proprietario/admin) |
| `admin@example.com` | admin | nessun endpoint pubblico crea admin: solo dato fittizio, vedi nota sotto |

## Note per la produzione

- **Email**: senza `SMTP_HOST` configurato in `.env`, le email vengono solo
  loggate in console (`app/email_utils.py`) — impostare le variabili SMTP_*
  (o sostituire con `fastapi-mail`) prima del rilascio.
- **Storage licenze**: i file finiscono su disco locale
  (`backend/uploads/licenses/`, path ancorato alla cartella `backend/`
  indipendentemente da dove lanci il processo) con un URL fittizio
  (`app/storage.py`) — sostituire `save_license_file()` con una chiamata
  reale a boto3 (S3) o google-cloud-storage (GCS); nessun'altra parte
  dell'app cambia.
- **Database**: tutto vive in memoria e si perde al riavvio del processo —
  sostituire `app/database.py` con un vero layer (es. SQLAlchemy/SQLModel su
  PostgreSQL) mantenendo la stessa interfaccia (`db.create_user`,
  `db.get_by_email`, ecc.) usata dai router.
- **SECRET_KEY**: il default in `app/config.py` è solo per sviluppo locale —
  va sempre sovrascritto in `.env` (o variabile d'ambiente) in qualunque
  ambiente condiviso/deployato.
- **Ricerca geospaziale**: `app/geo.py` fa tutto in Python (Haversine, O(n)
  su tutti i negozi) — va bene per dati di prova, ma su un vero Postgres
  conviene passare a PostGIS (`ST_DWithin`/`ST_Distance` con indice
  `GIST`) o a un equivalente lato DB; `routers/shops.py` si aspetta solo
  coppie `(shop, distance_km)`, quindi il resto non cambierebbe.
- **Ruolo admin**: non esiste (volutamente) un endpoint pubblico per
  diventare admin — in produzione andrebbe provisionato fuori banda
  (migrazione DB, CLI interna, ...), non tramite l'API pubblica.
- **License status duplicato**: lo stato di verifica vive sia su
  `Shop.license_status` (governato dall'admin, punto 2) sia su
  `User.license.status` (impostato al caricamento del documento, punto 1).
  L'endpoint admin li tiene sincronizzati manualmente
  (`routers/admin.py::set_shop_license_status`) — con un DB vero converrebbe
  unificarli in un solo campo/tabella.
