// ---------------------------------------------------------------------------
// Notification endpoints — backend/app/routers/notifications.py.
// In-app history (populated by the order state machine — see
// backend/app/order_events.py) + push device registration (Firebase Cloud
// Messaging, see src/utils/pushNotifications.js for the client side).
// ---------------------------------------------------------------------------
import { apiRequest } from './client';

export async function listNotifications() {
  return apiRequest('/notifications', { auth: true });
}

export async function markNotificationRead(notificationId) {
  return apiRequest(`/notifications/${encodeURIComponent(notificationId)}/read`, { method: 'POST', auth: true });
}

export async function markAllNotificationsRead() {
  return apiRequest('/notifications/read-all', { method: 'POST', auth: true });
}

// token: the device's *native* FCM/APNs token (Notifications.getDevicePushTokenAsync().data),
// not an Expo push token — see src/utils/pushNotifications.js.
export async function registerPushToken(token, platform) {
  return apiRequest('/users/me/push-tokens', { method: 'POST', auth: true, json: { token, platform } });
}

export async function unregisterPushToken(token) {
  return apiRequest(`/users/me/push-tokens/${encodeURIComponent(token)}`, { method: 'DELETE', auth: true });
}
