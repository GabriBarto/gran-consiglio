// ---------------------------------------------------------------------------
// Ricerca indirizzi con Google Places API (New), via REST: nessun modulo
// nativo, quindi funziona uguale su Expo Go, iOS, Android e web.
//
// Richiede EXPO_PUBLIC_GOOGLE_MAPS_API_KEY (vedi .env.example) con "Places
// API (New)" abilitata. Senza chiave `isPlacesConfigured()` è false e il form
// ricade sull'inserimento manuale di lat/lng.
// ---------------------------------------------------------------------------
const API_KEY = process.env.EXPO_PUBLIC_GOOGLE_MAPS_API_KEY;
const BASE = 'https://places.googleapis.com/v1';

export function isPlacesConfigured() {
  return Boolean(API_KEY);
}

// Il session token raggruppa autocomplete + details in un'unica sessione di
// fatturazione Google: se ne genera uno nuovo a ogni indirizzo scelto.
export function newSessionToken() {
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 12)}`;
}

async function placesFetch(path, { method = 'GET', body, fieldMask, signal } = {}) {
  const res = await fetch(`${BASE}${path}`, {
    method,
    signal,
    headers: {
      'Content-Type': 'application/json',
      'X-Goog-Api-Key': API_KEY,
      ...(fieldMask ? { 'X-Goog-FieldMask': fieldMask } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    throw new Error('Ricerca indirizzo non disponibile, riprova più tardi.');
  }
  return res.json();
}

// -> [{ placeId, text }]
export async function autocompleteAddress(input, sessionToken, signal) {
  const data = await placesFetch('/places:autocomplete', {
    method: 'POST',
    signal,
    body: {
      input,
      sessionToken,
      languageCode: 'it',
      regionCode: 'IT',
      includedPrimaryTypes: ['street_address', 'premise', 'subpremise', 'route'],
    },
    fieldMask: 'suggestions.placePrediction.placeId,suggestions.placePrediction.text.text',
  });
  return (data.suggestions ?? [])
    .map((s) => s.placePrediction)
    .filter(Boolean)
    .map((p) => ({ placeId: p.placeId, text: p.text?.text ?? '' }));
}

// -> { address, lat, lng }
export async function getPlaceDetails(placeId, sessionToken) {
  const data = await placesFetch(
    `/places/${encodeURIComponent(placeId)}?sessionToken=${encodeURIComponent(sessionToken)}&languageCode=it`,
    { fieldMask: 'formattedAddress,location' },
  );
  return {
    address: data.formattedAddress,
    lat: data.location.latitude,
    lng: data.location.longitude,
  };
}
