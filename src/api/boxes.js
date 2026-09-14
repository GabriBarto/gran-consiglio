// ---------------------------------------------------------------------------
// Box ("surprise bag") endpoints — backend/app/routers/boxes.py.
//
// Field names match backend/app/schemas.py::BoxRequest/BoxPublic exactly:
// price, max_boxes, pickup_window_start/end (HH:MM), expire_at (ISO
// datetime). `sold_boxes`/`available` are server-computed, never sent.
// ---------------------------------------------------------------------------
import { apiRequest } from './client';

// Vendor: manage their own shop's boxes.
export async function listMyBoxes() {
  return apiRequest('/shops/me/boxes', { auth: true });
}

export async function createBox(payload) {
  return apiRequest('/shops/me/boxes', { method: 'POST', auth: true, json: payload });
}

export async function updateBox(boxId, payload) {
  return apiRequest(`/shops/me/boxes/${encodeURIComponent(boxId)}`, { method: 'PUT', auth: true, json: payload });
}

export async function deleteBox(boxId) {
  return apiRequest(`/shops/me/boxes/${encodeURIComponent(boxId)}`, { method: 'DELETE', auth: true });
}

// Public: browse a shop's boxes (customer-facing, no auth) — only ever
// returns something for an admin-approved shop, 404 otherwise.
export async function listShopBoxes(shopId) {
  return apiRequest(`/shops/${encodeURIComponent(shopId)}/boxes`);
}
