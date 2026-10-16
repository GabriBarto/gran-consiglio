// ---------------------------------------------------------------------------
// Ricerca indirizzi con Photon (https://photon.komoot.io), un geocoder
// gratuito basato sui dati di OpenStreetMap: nessuna chiave API, nessun
// account, funziona via fetch su Expo Go, iOS, Android e web.
//
// L'istanza pubblica è a uso "ragionevole" (niente carichi massicci): per
// l'autocompletamento di un form venditore va bene. Se un giorno servisse
// di più, Photon si può ospitare da soli e basta cambiare BASE.
// ---------------------------------------------------------------------------
const BASE = 'https://photon.komoot.io/api/';

// Riquadro dell'Italia (lon_min, lat_min, lon_max, lat_max): evita risultati esteri.
const ITALY_BBOX = '6.6,35.4,18.8,47.1';

function formatAddress(p) {
  const street = [p.street ?? p.name, p.housenumber].filter(Boolean).join(' ');
  const town = [p.postcode, p.city ?? p.town ?? p.village ?? p.county].filter(Boolean).join(' ');
  return [street, town].filter(Boolean).join(', ');
}

// -> [{ id, text, address, lat, lng }]
export async function searchAddresses(query, signal) {
  const url = `${BASE}?q=${encodeURIComponent(query)}&limit=6&bbox=${ITALY_BBOX}`;
  const res = await fetch(url, { signal });
  if (!res.ok) throw new Error('Ricerca indirizzo non disponibile, riprova più tardi.');
  const data = await res.json();
  return (data.features ?? [])
    .filter((f) => f.properties?.countrycode === 'IT' && f.geometry?.coordinates)
    .map((f) => {
      const address = formatAddress(f.properties);
      const [lng, lat] = f.geometry.coordinates;
      return { id: `${f.properties.osm_type}${f.properties.osm_id}`, text: address, address, lat, lng };
    })
    .filter((r) => r.address);
}
