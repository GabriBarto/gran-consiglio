// ---------------------------------------------------------------------------
// Cart + checkout endpoints — backend/app/routers/cart.py.
//
// A cart is scoped to one (customer, shop) pair — see CartPublic in
// backend/app/schemas.py — matching how pickup happens at one physical shop.
// ---------------------------------------------------------------------------
import { apiRequest } from './client';

export async function getCart(shopId) {
  return apiRequest(`/shops/${encodeURIComponent(shopId)}/cart`, { auth: true });
}

export async function addCartItem(shopId, boxId, quantity = 1) {
  return apiRequest(`/shops/${encodeURIComponent(shopId)}/cart/items`, {
    method: 'POST',
    auth: true,
    json: { box_id: boxId, quantity },
  });
}

export async function setCartItemQuantity(shopId, boxId, quantity) {
  return apiRequest(`/shops/${encodeURIComponent(shopId)}/cart/items/${encodeURIComponent(boxId)}`, {
    method: 'PUT',
    auth: true,
    json: { quantity },
  });
}

export async function removeCartItem(shopId, boxId) {
  return apiRequest(`/shops/${encodeURIComponent(shopId)}/cart/items/${encodeURIComponent(boxId)}`, {
    method: 'DELETE',
    auth: true,
  });
}

export async function clearCart(shopId) {
  return apiRequest(`/shops/${encodeURIComponent(shopId)}/cart`, { method: 'DELETE', auth: true });
}

// Books the whole current cart as one order — see checkoutCart's backend
// counterpart for what happens if availability changed in the meantime.
export async function checkoutCart(shopId) {
  return apiRequest(`/shops/${encodeURIComponent(shopId)}/cart/checkout`, { method: 'POST', auth: true });
}
