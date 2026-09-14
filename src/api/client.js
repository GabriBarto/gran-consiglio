// ---------------------------------------------------------------------------
// Thin HTTP client for the real Python (FastAPI) backend in backend/.
//
// Centralizes: base URL config, JWT storage (AsyncStorage), one-shot
// refresh-token retry on a 401, and turning FastAPI error responses into a
// single Italian message string (so the rest of the app just does
// `catch (err) { setFormError(err.message) }` as before).
// ---------------------------------------------------------------------------
import AsyncStorage from '@react-native-async-storage/async-storage';
import Constants from 'expo-constants';

const TOKENS_KEY = 'toogood/tokens';

// Porta a cui risponde il backend FastAPI (vedi backend/app/main.py /
// il comando uvicorn nel README) — di norma non cambia, quindi resta
// configurabile ma con un default sensato.
const API_PORT = process.env.EXPO_PUBLIC_API_PORT || '8000';

// In sviluppo (Expo Go / dev client), Constants.expoConfig.hostUri è
// popolato da @expo/cli con l'host:porta usati dal telefono per raggiungere
// il dev server Metro (es. "10.10.55.71:8081") — cioè l'IP LAN attuale di
// questo Mac, qualunque sia la rete WiFi a cui è connesso in questo
// momento. Il backend gira sulla stessa macchina, quindi lo stesso IP
// (con la porta del backend, non quella di Metro) è anche l'indirizzo
// giusto per le chiamate API: niente più IP da aggiornare a mano ad ogni
// cambio di rete. Non è disponibile nelle build di produzione (standalone),
// dove va comunque configurato EXPO_PUBLIC_API_BASE_URL.
function getDevServerHost() {
  const hostUri = Constants.expoConfig?.hostUri;
  if (!hostUri) return null;
  const host = hostUri.split('/')[0].split(':')[0];
  return host || null;
}

function getBaseUrl() {
  // Override esplicito (obbligatorio in produzione, opzionale in sviluppo
  // per casi speciali: simulatore -> 127.0.0.1, backend su un'altra
  // macchina, porta non standard, ecc.) ha sempre la precedenza.
  const explicit = process.env.EXPO_PUBLIC_API_BASE_URL;
  if (explicit) return explicit.replace(/\/$/, '');

  const devHost = getDevServerHost();
  if (devHost) {
    return `http://${devHost}:${API_PORT}`;
  }

  throw new Error(
    'Indirizzo del backend non configurato: crea un file .env nella root del progetto (vedi .env.example) con EXPO_PUBLIC_API_BASE_URL, oppure avvia l\'app con "npx expo start" (Expo Go / dev client) così l\'IP viene rilevato automaticamente.'
  );
}

async function getTokens() {
  const raw = await AsyncStorage.getItem(TOKENS_KEY);
  return raw ? JSON.parse(raw) : null;
}

async function setTokens(tokens) {
  if (tokens) {
    await AsyncStorage.setItem(TOKENS_KEY, JSON.stringify(tokens));
  } else {
    await AsyncStorage.removeItem(TOKENS_KEY);
  }
}

// Subscribers notified when a session can no longer be refreshed (e.g. the
// refresh token itself expired) — AuthContext uses this to clear `user`
// even when nothing on screen explicitly called logout().
let authExpiredListeners = [];
export function onAuthExpired(callback) {
  authExpiredListeners.push(callback);
  return () => {
    authExpiredListeners = authExpiredListeners.filter((cb) => cb !== callback);
  };
}

// FastAPI error bodies come in a few shapes depending on where they were
// raised: a plain string detail, a list of Pydantic validation errors, or
// (for the hand-validated multipart vendor registration) {"errors": [...]}.
function extractErrorMessage(data, fallback) {
  const detail = data?.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    const messages = detail.map((item) => item?.msg).filter(Boolean);
    if (messages.length) return messages.join('\n');
  }
  if (detail && Array.isArray(detail.errors)) {
    return detail.errors.join('\n');
  }
  return fallback;
}

async function rawRequest(path, { method = 'GET', json, form, accessToken } = {}) {
  const headers = { Accept: 'application/json' };
  let body;
  if (form) {
    body = form; // FormData: let fetch set its own multipart boundary header.
  } else if (json !== undefined) {
    headers['Content-Type'] = 'application/json';
    body = JSON.stringify(json);
  }
  if (accessToken) {
    headers.Authorization = `Bearer ${accessToken}`;
  }

  // Computed outside the try/catch below on purpose: if EXPO_PUBLIC_API_BASE_URL
  // is missing, that specific error must reach the caller as-is, not get
  // swallowed into the generic "network unreachable" message.
  const url = `${getBaseUrl()}${path}`;

  let response;
  try {
    response = await fetch(url, { method, headers, body });
  } catch (err) {
    throw new Error(
      `Impossibile contattare il server (${url}). Verifica che il backend sia avviato e raggiungibile, e che EXPO_PUBLIC_API_BASE_URL sia corretto.`
    );
  }

  let data = null;
  const text = await response.text();
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      // Non-JSON body (shouldn't normally happen) — leave data as null.
    }
  }
  return { response, data };
}

async function refreshTokens() {
  const tokens = await getTokens();
  if (!tokens?.refresh_token) return null;
  const { response, data } = await rawRequest('/auth/refresh', {
    method: 'POST',
    json: { refresh_token: tokens.refresh_token },
  });
  if (!response.ok) return null;
  await setTokens(data);
  return data;
}

/**
 * @param {string} path e.g. "/shops/me"
 * @param {object} options
 *   - method, json, form: as in rawRequest
 *   - auth: attach the stored access token (and retry once via refresh on 401)
 *   - nullOnStatus: array of HTTP statuses to resolve to `null` instead of throwing
 *     (e.g. 404 for "no shop yet")
 */
export async function apiRequest(path, options = {}) {
  const { auth = false, nullOnStatus = [], ...rest } = options;

  let tokens = auth ? await getTokens() : null;
  if (auth && !tokens?.access_token) {
    throw new Error('Devi accedere per continuare.');
  }

  let { response, data } = await rawRequest(path, { ...rest, accessToken: tokens?.access_token });

  if (auth && response.status === 401) {
    const refreshed = await refreshTokens();
    if (!refreshed) {
      await setTokens(null);
      authExpiredListeners.forEach((cb) => cb());
      throw new Error('Sessione scaduta, effettua di nuovo l\'accesso.');
    }
    ({ response, data } = await rawRequest(path, { ...rest, accessToken: refreshed.access_token }));
  }

  if (!response.ok) {
    if (nullOnStatus.includes(response.status)) return null;
    throw new Error(extractErrorMessage(data, `Errore del server (${response.status}).`));
  }

  return data;
}

export async function storeTokens(tokens) {
  await setTokens(tokens);
}

export async function clearTokens() {
  await setTokens(null);
}

export async function hasStoredSession() {
  const tokens = await getTokens();
  return !!tokens?.access_token;
}
