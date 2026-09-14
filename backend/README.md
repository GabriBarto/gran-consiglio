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
| Upload/gestione documento licenza venditore (storage esterno, non su DB) | `POST /auth/register/vendor` (multipart) — [app/storage.py](app/storage.py) (salva su disco e restituisce un URL reale, servito da questa stessa API — mai il file nel DB — l'URL finisce in `store.licenseUrl`, vedi punto 2) |
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

## 3. Box ("surprise bag") — il cuore in stile Too Good To Go

| Requisito | Dove |
|---|---|
| CRUD box del proprio negozio (nome, prezzo, descrizione, categoria, allergeni, quantità, fascia di ritiro, scadenza) | `POST /shops/me/boxes`, `GET /shops/me/boxes`, `PUT /shops/me/boxes/{box_id}`, `DELETE /shops/me/boxes/{box_id}` — tutti vendor-only e scoperti solo sulle box del **proprio** negozio (404, non 403, su una box di un altro vendor) — [app/routers/boxes.py](app/routers/boxes.py) |
| Il cliente vede le box cliccando un negozio | `GET /shops/{shop_id}/boxes` — pubblico, stesso criterio di visibilità di `GET /shops/{shop_id}`: solo negozi `approved`, 404 altrimenti |
| Quantità disponibile calcolata, non impostabile dal vendor | Ogni `BoxPublic` riporta `available = max_boxes - sold_boxes`; `sold_boxes` non è nemmeno un campo di `BoxRequest` — si muove solo tramite il checkout (punto 4), mai impostato a mano |

Una box ha una propria fascia di ritiro (`pickup_window_start/end`,
indipendente da quella generale del negozio: es. un fornaio può avere pane
del mattino e dolci della sera con orari diversi) e una scadenza
(`expire_at`, timestamp completo) dopo la quale andrebbe rimossa dal
catalogo — l'API non la nasconde automaticamente ancora (nessun job/cron in
questo scope), è responsabilità del vendor eliminarla o del prossimo step
implementarlo lato server.

## 4. Carrello e prenotazione (cliente)

| Requisito | Dove |
|---|---|
| Aggiungere una box al carrello, cambiare quantità, rimuoverla, svuotare il carrello | `POST /shops/{shop_id}/cart/items`, `PUT .../cart/items/{box_id}`, `DELETE .../cart/items/{box_id}`, `DELETE /shops/{shop_id}/cart` — qualunque utente autenticato, un carrello per coppia (cliente, negozio) — [app/routers/cart.py](app/routers/cart.py) |
| Vedere il carrello corrente di un negozio | `GET /shops/{shop_id}/cart` — righe con nome/prezzo/quantità/subtotale, più `available` **corrente** di ogni box (per avvisare prima del checkout se qualcuno ha esaurito nel frattempo) |
| Prenotare (checkout) | `POST /shops/{shop_id}/cart/checkout` — crea un `Order` da tutte le righe del carrello in un colpo solo, **ri-valida e blocca** (`SELECT ... FOR UPDATE`) la disponibilità di ogni box prima di confermare: se anche una sola riga non c'è più in quella quantità, l'intero checkout fallisce (409) e il carrello resta intatto, così il cliente può solo aggiustare le quantità e riprovare — niente prenotazioni parziali |

Un carrello può mescolare box con fasce di ritiro diverse dello stesso
negozio (es. pane del mattino + dolci della sera): dato che `orders` ha
un solo campo `pickupWindow`, il checkout lo calcola come l'intervallo più
ampio che le contiene tutte (inizio più presto–fine più tardi), non la
somma letterale delle singole fasce.

## 5. Ordini (prenotazioni) e ritiro

| Requisito | Dove |
|---|---|
| Storico prenotazioni del cliente | `GET /orders`, `GET /orders/{order_id}` (proprietario, il vendor del negozio, o un admin) — [app/routers/orders.py](app/routers/orders.py) |
| Il cliente conferma il pagamento | `POST /orders/{order_id}/pay` — `pendingPayment` → `paid`. Non c'è ancora un vero gateway di pagamento integrato: questo endpoint fa da stand-in (va sempre a buon fine se chiamato nello stato giusto) fino a quando non se ne collega uno reale, senza che il resto del flusso cambi |
| Il cliente annulla una prenotazione | `POST /orders/{order_id}/cancel` — da qualunque stato non terminale (`pendingPayment`/`paid`/`readyForPickup`); **ripristina** la quantità sulle box coinvolte (`sold_boxes -= quantity`) |
| Il vendor gestisce le prenotazioni del proprio negozio | `GET /shops/me/orders`, `PATCH /shops/me/orders/{order_id}` (`{"state": "readyForPickup"}` a box pronta, `{"state": "pickedUp"}` a ritiro avvenuto, o `{"state": "cancelled"}` per un cliente che non si è presentato — anche questo ripristina la disponibilità) |

### Macchina a stati dell'ordine

```
pendingPayment ──pay()──▶ paid ──mark_ready()──▶ readyForPickup ──mark_picked_up()──▶ pickedUp
      │                    │                            │
      └──────────────┴─────cancel()/expire()────────────┘
                       (da uno qualunque dei tre) ──▶ cancelled / expired
```

Tutta la logica vive in [app/order_state_machine.py](app/order_state_machine.py)
(il grafo delle transizioni valide — niente salti di stato, es. da
`pendingPayment` direttamente a `pickedUp`) e
[app/order_events.py](app/order_events.py) (gli effetti collaterali di ogni
transizione). `Repository._transition_order` in
[app/database.py](app/database.py) è l'unico punto che scrive
`orders.state`: valida la transizione, ripristina lo stock se l'ordine
esce dal ciclo senza essere ritirato, scrive il nuovo stato e lancia gli
eventi — tutto nella stessa transazione. Una transizione non valida
(salto di stato, o una mossa da uno stato terminale) alza
`InvalidOrderTransition`, mappato a 409 dai router.

`pickedUp`, `cancelled` ed `expired` sono terminali. `expired` esiste per
una futura pulizia automatica delle prenotazioni scadute mai ritirate
(nessun job/cron in questo scope, stessa nota del punto 3 sulla scadenza
delle box — vedi `Repository.expire_order`) — non è mai impostato a mano,
nessun router lo espone.

Ogni transizione (tranne l'ingresso in `pendingPayment`, il punto di
partenza) lancia due tipi di trigger:
- **notifica**: una riga in `notification` più una push (Firebase Cloud
  Messaging) e un'email, entrambe best-effort — vedi punto 6 sotto
  ([app/order_events.py](app/order_events.py)) — un fallimento qui non fa
  mai fallire/annullare la transizione stessa;
- **sblocco recensione**: arrivare a `pickedUp` marca `review_unlocked:
  true` su `OrderPublic` e genera una notifica di tipo `reviewRequest` —
  il segnale che la recensione è ora valida da lasciare. Scriverla non è
  ancora implementato (nessun endpoint usa `ReviewRow` in scrittura), è il
  prossimo pezzo che si aggancerà a questo trigger.

## 6. Notifiche

| Requisito | Dove |
|---|---|
| Storico notifiche in-app (tipo, testo, letta/non letta, data) | `GET /notifications`, `POST /notifications/{id}/read`, `POST /notifications/read-all` — [app/routers/notifications.py](app/routers/notifications.py). Tabella `notification`, già presente nello schema/seed originale ma scritta da nessun endpoint finché non è arrivata la macchina a stati degli ordini (punto 5) |
| Push (Firebase Cloud Messaging) | `POST/DELETE /users/me/push-tokens` registra/rimuove il token nativo FCM/APNs del dispositivo corrente (tabella `push_token`, aggiunta in questa pass — vedi `-- ADDED` in [db/projectwork_en_v2.sql](db/projectwork_en_v2.sql)); l'invio vero e proprio è in [app/push_utils.py](app/push_utils.py), via `firebase-admin` |
| Trigger: nuovo ordine → notifica al venditore | Al checkout ([app/order_events.py](app/order_events.py)::`fire_new_order_event`, chiamato da `Repository.checkout_cart`) |
| Trigger: ordine pronto/promemoria ritiro → notifica al cliente | Transizione `paid` → `readyForPickup` (già parte della macchina a stati, punto 5 — tipo `pickupReminder`) |

Ogni trigger di notifica (`app/order_events.py::_notify_user`) fa sempre le
stesse tre cose, ognuna best-effort e indipendente dalle altre: scrive una
riga in `notification`, invia una push a ogni dispositivo registrato
dell'utente, invia un'email. Un fallimento su una gamba (token push
scaduto, SMTP giù, Firebase non configurato) non blocca le altre né la
transizione che l'ha scatenato.

**Firebase — mock di default, stesso pattern dell'email**: senza
`FIREBASE_CREDENTIALS_FILE` configurato, le push vengono solo loggate in
console ([app/push_utils.py](app/push_utils.py)), mai spedite davvero —
l'API resta comunque completamente testabile end-to-end. Per attivarle
davvero: scarica una chiave di service account dalla console Firebase
(Project settings → Service accounts → Generate new private key) e
imposta `FIREBASE_CREDENTIALS_FILE=/percorso/alla/chiave.json` in `.env`.

Questo copre solo l'invio *verso* Firebase — far arrivare la push su un
telefono richiede anche, lato Expo (progetto root, non `backend/`): un
vero progetto Firebase con un'app Android/iOS registrata, il
`google-services.json` di quel progetto agganciato in `app.json`, e una
**development build** (non Expo Go: dalla SDK 53 Expo Go non supporta più
le push remote su Android — vedi
[src/utils/pushNotifications.js](../src/utils/pushNotifications.js)).

**Non incluso in questa pass — task periodico per "box in scadenza vicino
a te"**: richiederebbe un job schedulato (Celery beat, come indicato nella
richiesta) che gira periodicamente, cerca box in scadenza vicino agli
utenti (riusando l'Haversine già in [app/geo.py](app/geo.py)) e genera la
notifica di tipo `boxAvailable`/`allergenFlagged`. Non implementato perché
introdurrebbe una dipendenza nuova per tutto il progetto (un broker Redis
+ un secondo processo worker/beat da tenere avviato in locale) — stessa
scelta già fatta per la pulizia automatica degli ordini scaduti (punto 5)
e delle box scadute (punto 3): nessun cron in questo scope, ma
`Repository.expire_order` e questo stesso modulo (`app/order_events.py`)
sono già pronti per essere chiamati da un job del genere quando arriva.

## Setup

Windows (PowerShell):

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

macOS / Linux:

```bash
cd backend
python3 -m venv .venv
./.venv/bin/python -m pip install -r requirements.txt
```

### Database (MySQL/MariaDB)

Qualunque server MySQL/MariaDB locale va bene — sotto le opzioni più comuni
per piattaforma. In tutti i casi il comando finale è lo stesso: importare
[db/projectwork_en_v2.sql](db/projectwork_en_v2.sql), che crea da sé il
database `toogood` (`CREATE DATABASE IF NOT EXISTS`) e lo riempie con i
dati di prova — non serve creare il DB a mano prima.

**Windows — XAMPP** (root, nessuna password, porta 3306: il default di
`DATABASE_URL` in [app/config.py](app/config.py) è già pensato per questo,
non serve un `.env`):

```powershell
# 1. avvia MySQL (XAMPP Control Panel, oppure da riga di comando):
C:\xampp\mysql\bin\mysqld.exe --defaults-file=C:\xampp\mysql\bin\my.ini --standalone

# 2. crea lo schema + i dati di prova
Get-Content db\projectwork_en_v2.sql -Raw | C:\xampp\mysql\bin\mysql.exe -u root
```

> Nota XAMPP: se al primo avvio `mysqld` fallisce con un errore tipo
> `Aria engine: log data error`, è un log Aria non inizializzato — basta
> rinominare (non serve cancellare) `mysql\data\aria_log_control` e
> `mysql\data\aria_log.00000001`, poi riavviare: MariaDB li rigenera da sé.

**macOS — MAMP** (root/root, porta **8889** di default, non 3306 — serve un
`.env`, vedi sotto):

```bash
# 1. avvia MySQL dal MAMP Control Panel (o lancia MAMP.app)

# 2. crea lo schema + i dati di prova
/Applications/MAMP/Library/bin/mysql80/bin/mysql -h127.0.0.1 -P8889 -uroot -proot < db/projectwork_en_v2.sql
```

**macOS/Linux — MySQL/MariaDB da Homebrew o pacchetto di sistema** (di
solito root senza password su 127.0.0.1:3306, come XAMPP — stesso comando
di importazione, adatta utente/porta/host se il tuo setup è diverso):

```bash
mysql -u root < db/projectwork_en_v2.sql
```

Copia `.env.example` in `.env` (già in `.gitignore`, resta locale alla tua
macchina) ogni volta che il tuo server non è il default XAMPP-style
(root, nessuna password, `127.0.0.1:3306`) — tipicamente su MAMP — e
imposta `DATABASE_URL` di conseguenza, es. per MAMP:

```
DATABASE_URL=mysql+pymysql://root:root@127.0.0.1:8889/toogood
```

Nessun'altra parte del codice dipende dalla piattaforma o dal prodotto
usato per il server MySQL: `app/db/engine.py` legge solo `DATABASE_URL`.

## Avvio

Da dentro `backend/` (dove hai già creato il venv, con MySQL già avviato):

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

```bash
./.venv/bin/python -m uvicorn app.main:app --reload
```

Se il DB non è raggiungibile, l'avvio fallisce subito con un errore chiaro
in log invece che con un errore criptico alla prima richiesta (vedi
`lifespan` in [app/main.py](app/main.py)).

Docs interattive Swagger su http://127.0.0.1:8000/docs.

Per farlo raggiungere dall'app Expo su un telefono fisico (stessa Wi-Fi) o
da un emulatore Android, avvialo su tutte le interfacce, non solo
`localhost` — e imposta l'IP LAN del tuo PC/Mac in `EXPO_PUBLIC_API_BASE_URL`
(root del progetto, file `.env`, vedi `.env.example` lì):

```bash
./.venv/bin/python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Test

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

```bash
./.venv/bin/python -m pytest -q
```

I test **non** toccano il database di sviluppo: [tests/conftest.py](tests/conftest.py)
punta l'app a un database separato (`toogood_test`), che viene
droppato/ricreato da zero da `db/projectwork_en_v2.sql` a ogni sessione di
test — stesso identico schema e stessi dati seed del DB "vero", ma isolato,
così i test sono ripetibili e non serve mai pulire a mano. Richiede lo
stesso MySQL già avviato per lo sviluppo.

Il default (nessuna variabile d'ambiente impostata) assume root/nessuna
password su `127.0.0.1:3306` (XAMPP) e cerca il binario `mysql` prima su
`MYSQL_BIN`/`PATH`, poi in un paio di percorsi comuni XAMPP/MAMP. Se il tuo
setup è diverso (es. MAMP su macOS), sovrascrivi con variabili d'ambiente:

```bash
TEST_DB_HOST=127.0.0.1 TEST_DB_PORT=8889 TEST_DB_USER=root TEST_DB_PASSWORD=root \
MYSQL_BIN=/Applications/MAMP/Library/bin/mysql80/bin/mysql \
./.venv/bin/python -m pytest -q
```

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

`box` ha 2 righe seed già visibili tramite `GET /shops/{shop_id}/boxes` (una
su "Vivaio Rossi - Centro", una su "Ortofrutta Bianchi" — entrambe sul
primo negozio `approved` di ciascun vendor).

`orders`/`order_item` hanno 2 righe seed (`cliente.demo@example.com`, già
`pickedUp`) visibili tramite `GET /orders` — servono anche a verificare che
lo storico non parta vuoto solo perché nessuno ha ancora prenotato nulla.
`cart`/`cart_item` invece partono sempre vuote (come `refresh_token` ecc.
sotto): un carrello attivo è per definizione uno stato transitorio, non ha
senso seedarlo.

`review`, `notification` hanno anch'esse 2 righe di dati di prova coerenti
(FK rispettate). `notification` è ora scritta dalla macchina a stati degli
ordini (punto 5, un trigger per transizione — vedi
[app/order_events.py](app/order_events.py)), ma non ha ancora un endpoint
di lettura (`GET /notifications`). `review` resta **non scritta da nessun
endpoint**: lo stato `pickedUp` la "sblocca" concettualmente
(`OrderPublic.review_unlocked`), ma il submit vero e proprio è un pezzo
futuro.

`refresh_token`, `email_verification`, `password_reset` (bookkeeping auth
effimero, vedi "Note per la produzione" sotto) partono invece sempre vuote:
non sono dati di prova, si popolano da sole quando qualcuno si
registra/fa login/richiede un reset.

## Note per la produzione

- **Email — ⚠️ ancora mock, da fare prima del rilascio**: senza `SMTP_HOST`
  configurato in `.env`, le email (verifica account, reset password) vengono
  solo loggate in console (`app/email_utils.py`), mai spedite davvero. È
  l'unico pezzo rimasto non reale in tutto il backend, per scelta esplicita
  (serve un provider a scelta — Resend/SendGrid/Mailgun/SMTP di un vero
  account — che qui non c'era modo di configurare). Per attivarle: imposta
  le variabili `SMTP_*` in `.env` (vedi `.env.example`); il codice le usa
  già, non serve toccare `email_utils.py`.
- **Storage licenze**: i file finiscono su disco locale
  (`backend/uploads/licenses/`, path ancorato alla cartella `backend/`
  indipendentemente da dove lanci il processo) e vengono serviti da questa
  stessa API con un URL reale e funzionante (mount `StaticFiles` in
  `app/main.py`, su `PUBLIC_BASE_URL` + `/uploads/licenses/...`) — non è più
  un dominio fittizio, il file scaricato da quell'URL è quello vero
  caricato dal venditore. Resta comunque disco locale, non un vero bucket:
  in produzione, sostituire `save_license_file()` in `app/storage.py` con
  una chiamata reale a boto3 (S3) o google-cloud-storage (GCS); nessun'altra
  parte dell'app cambia (i router dipendono solo dalla forma di
  `StoredFile`).
- **Token effimeri (OTP, reset password, refresh token)**: hanno ora una
  tabella dedicata ciascuno (`refresh_token`, `email_verification`,
  `password_reset` — vedi le sezioni "ADDED" in
  [db/projectwork_en_v2.sql](db/projectwork_en_v2.sql) e i metodi
  corrispondenti in `app.database.Repository`), quindi sopravvivono a un
  riavvio del processo, a differenza della versione precedente (dizionari
  in memoria). Restano comunque dati ad altissimo churn e scadenza breve:
  su un vero carico di produzione conviene comunque spostarli in una cache
  come Redis, più per performance/pulizia che per correttezza — oggi sono
  corretti anche in MySQL.
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
