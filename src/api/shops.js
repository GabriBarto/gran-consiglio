// ---------------------------------------------------------------------------
// Shop (vendor storefront) endpoints — backend/app/routers/shops.py.
//
// Shapes are passed through as the backend returns them (snake_case:
// opening_hours, pickup_window, license_status, vendor_id, ...) since these
// are new screens with no legacy naming to stay compatible with.
// ---------------------------------------------------------------------------
import { apiRequest } from './client';

function buildQuery(params) {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') query.set(key, value);
  });
  const qs = query.toString();
  return qs ? `?${qs}` : '';
}

// Public search — no auth required. Only ever returns admin-approved shops.
export async function searchShops({ city, lat, lng, radiusKm, limit = 20, offset = 0 } = {}) {
  const qs = buildQuery({ city, lat, lng, radius_km: radiusKm, limit, offset });
  return apiRequest(`/shops${qs}`);
}

export async function getShop(shopId) {
  return apiRequest(`/shops/${encodeURIComponent(shopId)}`);
}

// null means "this vendor hasn't created a shop yet", not an error.
export async function getMyShop() {
  return apiRequest('/shops/me', { auth: true, nullOnStatus: [404] });
}

export async function createShop(payload) {
  return apiRequest('/shops', { method: 'POST', auth: true, json: payload });
}

export async function updateMyShop(payload) {
  return apiRequest('/shops/me', { method: 'PUT', auth: true, json: payload });
}
