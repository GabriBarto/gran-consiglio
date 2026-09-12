# Backend — Gran Consiglio / TooGood

API in Python (FastAPI), con persistenza reale su **MySQL/MariaDB**. Lo
schema del database vive esclusivamente in
[db/projectwork_en_v2.sql](db/projectwork_en_v2.sql) — il codice Python
(`app/db/`) mappa quello schema via SQLAlchemy, non lo genera né lo
sostituisce: nessuna riga di Python fa DDL (`CREATE TABLE`, ecc.), è tutto
nel file `.sql`.

## 1. Autenticazione e gestione utenti

| Requisito | Dove |
|---|---|
| Registrazione cliente/venditore con validazione (email/username univoci, password) | `POST /auth/register/customer`, `POST /auth/register/vendor` — [app/routers/auth.py](app/routers/auth.py), regole condivise in [app/validation.py](app/validation.py) (porting di `src/validation.js` del frontend) |
| Hashing password con passlib (bcrypt/argon2) | [app/security.py](app/security.py) — `CryptContext(schemes=["argon2", "bcrypt"])`, salvato nella colonna `user.password` |
| Verifica email via link/OTP | `POST /auth/verify-email`, `POST /auth/verify-email/resend` — accetta sia il token del link sia il codice OTP a 6 cifre; invio email in [app/email_utils.py](app/email_utils.py) |
| Login con JWT + refresh token | `POST /auth/login` (python-jose) — [app/security.py](app/security.py) |
| "Password dimenticata" con token temporaneo | `POST /auth/forgot-password`, `POST /auth/reset-password` |
| Upload/gestione documento licenza venditore (storage esterno, non su DB) | `POST /auth/register/vendor` (multipart) — [app/storage.py](app/storage.py) (fake S3/Cloud Storage: salva su disco e restituisce solo un URL, mai il file nel DB — l'URL finisce in `store.licenseUrl`, vedi punto 2) |
| Upgrade cliente → venditore | `POST /users/me/upgrade-to-vendor` (richiede login) — [app/routers/users.py](app/routers/users.py) |

`GET /users/me` incluso come utility per leggere il profilo autenticato.

## 2. Gestione negozi (venditori)

| Requisito | Dove |
|---|---|
| CRUD negozio (nome, indirizzo, lat/lng, telefono, orario apertura, fascia ritiro) | `POST /shops` (multipart, con licenza), `GET /shops/me`, `PUT /shops/me`, `DELETE /shops/me`, `PUT /shops/me/license` — tutti vendor-only, un negozio "principale" per venditore — [app/routers/shops.py](app/routers/shops.py) |
| Stato verifica licenza (pending/approved/rejected), modificabile solo dall'admin | `GET /admin/shops` (coda di revisione, filtrabile per stato), `PATCH /admin/shops/{shop_id}/license-status` — [app/routers/admin.py](app/routers/admin.py). Il payload del vendor (`ShopRequest`) non ha nemmeno il campo `license_status`/`license_url`: strutturalmente non può auto-approvarsi né auto-assegnarsi una licenza |
| Ricerca negozi per città/zona/distanza | `GET /shops?city=...&lat=...&lng=...&radius_km=...&limit=...&offset=...` — Haversine puro in Python ([app/geo.py](app/geo.py)), niente PostGIS. Mostra solo negozi `approved`; se sono passati `lat`/`lng` i risultati sono ordinati per distanza e ogni negozio riporta `distance_km`. `city` cerca **come sottostringa dentro `address`**: lo schema dato non ha una colonna città separata |

`GET /shops/{shop_id}` è pubblico ma nasconde (404, non 403, per non far
trapelare l'esistenza) i negozi non approvati a chiunque non ne sia il
proprietario o un admin.

Registrarsi come venditore (o fare l'upgrade da cliente) crea **subito** un
negozio placeholder (lat/lng `0,0`, orari generici) con la licenza appena
caricata — visto che nello schema la licenza è legata a `store`, non a
`user`. Il vendor lo completa con `PUT /shops/me` (indirizzo vero,
coordinate, orari).

## Setup

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### Database (MySQL/MariaDB — qui via XAMPP)

```powershell
# 1. avvia MySQL (XAMPP Control Panel, oppure da riga di comando):
C:\xampp\mysql\bin\mysqld.exe --defaults-file=C:\xampp\mysql\bin\my.ini --standalone

# 2. crea lo schema + i dati di prova (root, nessuna password: default XAMPP)
Get-Content db\projectwork_en_v2.sql -Raw | C:\xampp\mysql\bin\mysql.exe -u root
```

Il file crea da sé il database `toogood` (`CREATE DATABASE IF NOT EXISTS`),
quindi questo comando basta da solo — non serve creare il DB a mano prima.
Copia `.env.example` in `.env` solo se vuoi puntare a un server/credenziali
diversi da quelli di default (`DATABASE_URL`, vedi sotto), o cambiare altri
default (`SECRET_KEY`, SMTP, ecc.).

> Nota XAMPP: se al primo avvio `mysqld` fallisce con un errore tipo
> `Aria engine: log data error`, è un log Aria non inizializzato — basta
> rinominare (non serve cancellare) `mysql\data\aria_log_control` e
> `mysql\data\aria_log.00000001`, poi riavviare: MariaDB li rigenera da sé.

## Avvio

Da dentro `backend/` (dove hai già creato il venv, con MySQL già avviato):

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Se il DB non è raggiungibile, l'avvio fallisce subito con un errore chiaro
in log invece che con un errore criptico alla prima richiesta (vedi
`lifespan` in [app/main.py](app/main.py)).

Docs interattive Swagger su http://127.0.0.1:8000/docs.

## Test

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

I test **non** toccano il database di sviluppo: [tests/conftest.py](tests/conftest.py)
punta l'app a un database separato (`toogood_test`), che viene
droppato/ricreato da zero da `db/projectwork_en_v2.sql` a ogni sessione di
test — stesso identico schema e stessi dati seed del DB "vero", ma isolato,
così i test sono ripetibili e non serve mai pulire a mano. Richiede lo
stesso MySQL già avviato per lo sviluppo (stesso `mysql.exe` in
`C:\xampp\mysql\bin`, configurabile con la variabile d'ambiente `MYSQL_BIN`
se diverso).

Copre l'intero flusso: registrazione → verifica email (OTP) → login →
refresh (con rotazione), registrazione venditore con upload licenza (e
creazione automatica del negozio placeholder), forgot/reset password,
upgrade cliente→venditore ([tests/test_auth.py](tests/test_auth.py)), più
CRUD negozio, upload/sostituzione licenza, RBAC admin/vendor, ricerca per
indirizzo/distanza/raggio con verifica numerica della formula di Haversine,
paginazione, visibilità dei negozi non approvati
([tests/test_shops.py](tests/test_shops.py)).

## Dati di prova (seed)

I dati vivono nel database, seedati **una volta** importando
[db/projectwork_en_v2.sql](db/projectwork_en_v2.sql) (non ad ogni avvio
dell'app, a differenza della vecchia versione in-memory) — 4 righe in
`user` e `store`, 2 in tutte le altre tabelle. Tutte le password sono
`Password123`:

| Email | Ruolo | Note |
|---|---|---|
| `admin@example.com` | admin | nessun endpoint pubblico crea admin: solo dato di prova |
| `cliente.demo@example.com` | customer | email già verificata |
| `vivaio.rossi@example.com` | vendor | 2 negozi (`store.userId` può ripetersi): "Vivaio Rossi - Centro" (Firenze, `approved`, visibile in ricerca) e "- Succursale Sud" (`pending`). Le API "il mio negozio" (`/shops/me`) operano sempre sul primo (id più basso) |
| `ortofrutta.bianchi@example.com` | vendor | 2 negozi: "Ortofrutta Bianchi" (Bologna, `pending`) e "- Mercato" (`rejected`) |

`box`, `cart`, `cart_item`, `orders`, `order_item`, `review`, `notification`
hanno anch'esse 2 righe di dati di prova coerenti (FK rispettate), ma
**nessun endpoint le usa ancora** — fanno parte dello schema/seed in
preparazione dei prossimi punti del progetto, non dei punti 1-2 già
implementati.

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
- **Token effimeri (OTP, reset password, refresh token)**: non hanno una
  tabella nello schema dato, quindi restano in memoria di processo
  (`app.database.Repository`, i tre dizionari `pending_verifications`/
  `pending_resets`/`refresh_tokens`) — si perdono se il processo riparte.
  In produzione andrebbero in una cache come Redis (hanno tutti una
  scadenza breve), non necessariamente nella stessa tabella relazionale
  degli utenti.
- **SECRET_KEY**: il default in `app/config.py` è solo per sviluppo locale —
  va sempre sovrascritto in `.env` (o variabile d'ambiente) in qualunque
  ambiente condiviso/deployato.
- **Ricerca geospaziale**: `app/geo.py` fa tutto in Python (Haversine, O(n)
  su tutti i negozi) — va bene per dati di prova, ma su un vero carico
  conviene passare a un indice geospaziale lato DB (MySQL `ST_Distance_Sphere`
  con indice `SPATIAL`, o PostGIS se si migra a Postgres);
  `routers/shops.py` si aspetta solo coppie `(shop, distance_km)`, quindi
  il resto non cambierebbe.
- **Ruolo admin**: non esiste (volutamente) un endpoint pubblico per
  diventare admin — in produzione andrebbe provisionato fuori banda
  (migrazione DB, CLI interna, ...), non tramite l'API pubblica. È
  un'aggiunta minima allo schema originale (`user.role` includeva solo
  `client`/`seller`) — vedi i commenti `-- ADDED:` in
  [db/projectwork_en_v2.sql](db/projectwork_en_v2.sql) per le uniche due
  modifiche fatte rispetto al file fornito (il ruolo admin, e le colonne
  `email_verified`/`created_at` su `user`, necessarie per funzionalità già
  costruite al punto 1).
