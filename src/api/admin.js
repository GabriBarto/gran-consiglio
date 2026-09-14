// ---------------------------------------------------------------------------
// Admin-only endpoints — backend/app/routers/admin.py.
// ---------------------------------------------------------------------------
import { apiRequest } from './client';

// status: undefined/null = all, or 'pending_review' | 'approved' | 'rejected'.
export async function listShopsForReview(status) {
  const qs = status ? `?status=${encodeURIComponent(status)}` : '';
  return apiRequest(`/admin/shops${qs}`, { auth: true });
}

export async function setShopLicenseStatus(shopId, status) {
  return apiRequest(`/admin/shops/${encodeURIComponent(shopId)}/license-status`, {
    method: 'PATCH',
    auth: true,
    json: { status },
  });
}
