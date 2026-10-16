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

// Confirms payment on the caller's own order: 'pendingPayment' -> 'paid'.
// Stands in for a real payment gateway callback (none integrated yet —
// see backend/app/routers/orders.py::pay_order).
export async function payOrder(orderId) {
  return apiRequest(`/orders/${encodeURIComponent(orderId)}/pay`, { method: 'POST', auth: true });
}

// Vendor: bookings for their own shop.
export async function listShopOrders() {
  return apiRequest('/shops/me/orders', { auth: true });
}

// state: 'readyForPickup' | 'pickedUp' | 'cancelled' — the only three the
// backend accepts here; whether the order's *current* state allows the
// requested one is enforced by the backend's order state machine (see
// backend/app/order_state_machine.py) and surfaced as a 409 otherwise.
export async function setShopOrderState(orderId, state) {
  return apiRequest(`/shops/me/orders/${encodeURIComponent(orderId)}`, {
    method: 'PATCH',
    auth: true,
    json: { state },
  });
}
