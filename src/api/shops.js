// ---------------------------------------------------------------------------
// Shop (vendor storefront) endpoints — backend/app/routers/shops.py.
//
// Field names match backend/app/schemas.py::ShopRequest/ShopPublic exactly:
// a single daily opening_time, a single daily pickup_window_start/end (not
// a per-weekday schedule — the real DB schema doesn't model that), and a
// free-text address (no separate city column).
// ---------------------------------------------------------------------------
import { apiRequest, backendUrl } from './client';
import { toUploadFile } from '../utils/files';

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

// Creates the vendor's shop from scratch — most vendors never call this
// (registering already auto-creates a placeholder shop, see
// backend/app/routers/auth.py), only reachable if that one was somehow
// deleted. Unlike updateMyShop, the backend requires multipart here (a
// license file is mandatory), so `licenseFile` (an expo-document-picker
// asset) is required.
export async function createShop({ licenseFile, ...fields }) {
  const form = new FormData();
  form.append('name', fields.name);
  form.append('address', fields.address);
  form.append('lat', String(fields.lat));
  form.append('lng', String(fields.lng));
  form.append('phone', fields.phone);
  form.append('opening_time', fields.opening_time);
  form.append('pickup_window_start', fields.pickup_window_start);
  form.append('pickup_window_end', fields.pickup_window_end);
  form.append('license_file', toUploadFile(licenseFile), licenseFile.name ?? 'licenza');
  return apiRequest('/shops', { method: 'POST', auth: true, form });
}

// License documents aren't public: this asks the backend for a download
// link valid a few minutes (admin or the shop's own vendor only), which
// can then be opened in a browser tab / the phone's viewer without our
// Bearer header. Returns the absolute URL.
export async function getLicenseLink(shopId) {
  const { path } = await apiRequest(`/shops/${encodeURIComponent(shopId)}/license/link`, {
    method: 'POST',
    auth: true,
  });
  return backendUrl(path);
}

export async function updateMyShop(payload) {
  return apiRequest('/shops/me', { method: 'PUT', auth: true, json: payload });
}

// Lets a vendor (re)upload their license document (e.g. after a rejection)
// — this resets the shop's license_status to pending_review server-side.
export async function replaceLicense(licenseFile) {
  const form = new FormData();
  form.append('license_file', toUploadFile(licenseFile), licenseFile.name ?? 'licenza');
  return apiRequest('/shops/me/license', { method: 'PUT', auth: true, form });
}
