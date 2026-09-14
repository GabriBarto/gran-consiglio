// ---------------------------------------------------------------------------
// Auth against the real backend (backend/app/routers/auth.py, users.py).
//
// Registration endpoints don't return tokens (only the created user), so
// registerCustomer/registerVendor log in right after, to keep the existing
// UX where "registrati" leaves you already logged in.
// ---------------------------------------------------------------------------
import { apiRequest, clearTokens, hasStoredSession, storeTokens } from './client';
import { toUploadFile } from '../utils/files';

// Backend field names (snake_case) -> camelCase, and only the fields
// UserPublic actually has (backend/app/schemas.py) — phone/address/license
// used to live on the user in an earlier version of this API but now live
// on the shop instead (see src/api/shops.js), since the real DB schema
// ties them to `store`, not `user`.
function mapUser(user) {
  if (!user) return null;
  return {
    id: user.id,
    role: user.role,
    email: user.email,
    username: user.username,
    emailVerified: user.email_verified,
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
