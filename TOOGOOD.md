Setup di progetto
Aggiunto Expo Router (file-based routing, standard SDK 57) → main in package.json ora punta a expo-router/entry, rimossi i vecchi App.js/index.js.
Nuove dipendenze: expo-router, react-native-safe-area-context, react-native-screens, @react-native-async-storage/async-storage, expo-document-picker (upload licenza), expo-crypto (hash password), babel-preset-expo (devDependency, mancava).
Schermate (app/)
index.js — welcome screen con Accedi / Registrati come cliente / Registrati come venditore.
login.js — email + password, comune a entrambi i ruoli.
register-cliente.js — email, password, conferma password, nome utente.
register-venditore.js — stessi campi + telefono, indirizzo negozio, upload documento licenza (PDF/immagine via expo-document-picker), con nota che il nome utente può essere il nome del negozio.
home-cliente.js / home-venditore.js — placeholder minimi post-login per chiudere il flusso (il resto delle AZIONI CLIENTE/VENDITORE che hai elencato è fuori scope di questa richiesta, che riguardava solo login/registrazione).
Logica condivisa (src/)
api/auth.js — mock backend locale (AsyncStorage) che implementa davvero l'unicità di email/username e l'hash della password (SHA-256 via expo-crypto), con commenti chiari che va sostituito da un vero backend prima del rilascio (unicità, licenza da verificare, hashing sicuro devono vivere lato server).
context/AuthContext.js, validation.js, components/FormField.js, components/PrimaryButton.js, theme.js.
Nota: la licenza viene solo caricata e marcata pending_review — la verifica vera e propria richiede un pannello admin/backend, non incluso qui.

Collegamento al backend reale + home + pannello admin
Verificato il backend Python (backend/): dipendenze installate, 12/12 test passati, provato a mano l'intero flusso (registrazione, login JWT, CRUD negozio, ricerca, coda admin) con il server avviato — funziona.
src/api/auth.js non è più un mock: chiama il vero backend via il nuovo src/api/client.js (fetch + JWT in AsyncStorage + un retry automatico su /auth/refresh). Rimosso expo-crypto (non serve più: l'hashing password vive lato server). Rimossi isUsernameTaken/isEmailTaken e il loro uso nei form di registrazione — il backend non espone un endpoint di disponibilità (per non far trapelare l'esistenza di un account); un'email/username già in uso torna come errore 409 al submit.
Nuovi src/api/shops.js e src/api/admin.js per, rispettivamente, ricerca/gestione negozio e coda di revisione licenze.
home-cliente.js: ricerca negozi approvati per città e/o "vicino a me" (expo-location + raggio in km, nuova dipendenza), lista risultati, dettaglio in app/shop/[id].js con orari settimanali completi e tap-to-call.
home-venditore.js: stato licenza reale; se approvata, crea/modifica il proprio negozio (src/components/ShopForm.js + DayScheduleEditor.js per gli orari giorno per giorno); se rifiutata, permette di ricaricare il documento.
Nuovo app/admin.js (solo ruolo admin, redirect altrimenti): coda negozi con filtri per stato, conteggi, approva/rifiuta/rimetti in attesa. Estensione minima e additiva del backend (backend/app/schemas.py::AdminShopReview, backend/app/routers/admin.py) per mostrare username/email del venditore accanto al negozio — ShopPublic da solo espone solo vendor_id.
Login/index instradano ora anche il ruolo admin verso /admin.
Config: .env / .env.example con EXPO_PUBLIC_API_BASE_URL (va avviato il backend con --host 0.0.0.0 per essere raggiungibile da un telefono fisico sulla LAN).

Email e Password per l'accesso (fittizio):
(password Password123 per tutti):
cliente.demo@example.com
vivaio.rossi@example.com (venditore, licenza già approvata)
ortofrutta.bianchi@example.com (venditore, licenza in attesa)
admin@example.com
