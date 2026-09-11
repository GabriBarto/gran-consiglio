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