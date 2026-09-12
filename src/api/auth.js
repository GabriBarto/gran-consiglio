// ---------------------------------------------------------------------------
// Auth against the real backend (backend/app/routers/auth.py, users.py).
//
// Registration endpoints don't return tokens (only the created user), so
// registerCustomer/registerVendor log in right after, to keep the existing
// UX where "registrati" leaves you already logged in.
// ---------------------------------------------------------------------------
import { File } from 'expo-file-system';
import { apiRequest, clearTokens, hasStoredSession, storeTokens } from './client';

// Expo SDK 57 makes the WinterCG-compliant `expo/fetch` the global fetch
// (see docs.expo.dev/versions/v57.0.0/sdk/expo — "On native platforms... the
// expo/fetch implementation becomes the global fetch by default"). Its
// FormData is spec-compliant and only knows how to send actual Blob/File
// parts — the classic React Native trick of appending a plain
// { uri, name, type } object (which only the old bridge's Networking module
// understood) is silently rejected, so the request never leaves the device.
// expo-file-system's File class implements Blob and works with it directly.
function toUploadFile(pickedDocument) {
  return new File(pickedDocument.uri);
}

// Backend field names (snake_case, license nested) -> the flatter shape the
// screens already use (see the old mock in git history for the shape this
// mirrors).
function mapUser(user) {
  if (!user) return null;
  return {
    id: user.id,
    role: user.role,
    email: user.email,
    username: user.username,
    emailVerified: user.email_verified,
    phone: user.phone ?? null,
    shopAddress: user.shop_address ?? null,
    license: user.license ?? null,
    licenseStatus: user.license?.status ?? null,
    createdAt: user.created_at,
  };
}

export async function registerCustomer({ email, password, confirmPassword, username }) {
  await apiRequest('/auth/register/customer', {
    method: 'POST',
    json: { email: email.trim(), username: username.trim(), password, password_confirm: confirmPassword },
  });
  return login({ email, password });
}

export async function registerVendor({ email, password, confirmPassword, username, phone, shopAddress, license }) {
  const form = new FormData();
  form.append('email', email.trim());
  form.append('username', username.trim());
  form.append('password', password);
  form.append('password_confirm', confirmPassword);
  form.append('phone', phone.trim());
  form.append('shop_address', shopAddress.trim());
  form.append('license_file', toUploadFile(license), license.name ?? 'licenza');

  await apiRequest('/auth/register/vendor', { method: 'POST', form });
  return login({ email, password });
}

export async function login({ email, password }) {
  const tokens = await apiRequest('/auth/login', {
    method: 'POST',
    json: { email: email.trim(), password },
  });
  await storeTokens(tokens);
  const user = await apiRequest('/users/me', { auth: true });
  return mapUser(user);
}

export async function logout() {
  await clearTokens();
}

export async function getSessionUser() {
  if (!(await hasStoredSession())) return null;
  try {
    const user = await apiRequest('/users/me', { auth: true });
    return mapUser(user);
  } catch {
    // Refresh token missing/expired, or server unreachable at startup —
    // treat as logged out rather than crashing the app on launch.
    await clearTokens();
    return null;
  }
}

export async function refreshUser() {
  const user = await apiRequest('/users/me', { auth: true });
  return mapUser(user);
}

export async function reuploadLicense(license) {
  const form = new FormData();
  form.append('license_file', toUploadFile(license), license.name ?? 'licenza');
  const user = await apiRequest('/users/me/license', { method: 'PUT', auth: true, form });
  return mapUser(user);
}
