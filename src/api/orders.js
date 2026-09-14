// ---------------------------------------------------------------------------
// Order endpoints — backend/app/routers/orders.py.
// ---------------------------------------------------------------------------
import { apiRequest } from './client';

// Customer: own booking history.
export async function listMyOrders() {
  return apiRequest('/orders', { auth: true });
}

export async function getOrder(orderId) {
  return apiRequest(`/orders/${encodeURIComponent(orderId)}`, { auth: true });
}

export async function cancelMyOrder(orderId) {
  return apiRequest(`/orders/${encodeURIComponent(orderId)}/cancel`, { method: 'POST', auth: true });
}

// Vendor: bookings for their own shop.
export async function listShopOrders() {
  return apiRequest('/shops/me/orders', { auth: true });
}

// state: 'pickedUp' | 'cancelled' — the only two the backend accepts here.
export async function setShopOrderState(orderId, state) {
  return apiRequest(`/shops/me/orders/${encodeURIComponent(orderId)}`, {
    method: 'PATCH',
    auth: true,
    json: { state },
  });
}
