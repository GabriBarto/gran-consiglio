// ---------------------------------------------------------------------------
// MOCK backend layer.
//
// There is no real server yet, so this module persists users on-device with
// AsyncStorage just so the registration/login screens are fully functional
// end-to-end (unique username/email checks, login, session restore).
//
// Before shipping, replace the bodies of these functions with real HTTP
// calls to your backend (which must own password hashing, the username/email
// uniqueness constraint, and the seller-license review process). Nothing in
// the UI layer should need to change — it only talks to this module.
// ---------------------------------------------------------------------------
import AsyncStorage from '@react-native-async-storage/async-storage';
import * as Crypto from 'expo-crypto';
import { normalizeIdentifier } from '../validation';

const USERS_KEY = 'toogood/users';
const SESSION_KEY = 'toogood/session';

async function readUsers() {
  const raw = await AsyncStorage.getItem(USERS_KEY);
  return raw ? JSON.parse(raw) : [];
}

async function writeUsers(users) {
  await AsyncStorage.setItem(USERS_KEY, JSON.stringify(users));
}

// SHA-256 is only used here to avoid storing plaintext passwords in the local
// mock database. It is NOT a substitute for a proper server-side algorithm
// like bcrypt/argon2 with per-user salt — do that on the real backend.
async function hashPassword(password) {
  return Crypto.digestStringAsync(Crypto.CryptoDigestAlgorithm.SHA256, password);
}

export async function isUsernameTaken(username) {
  const users = await readUsers();
  const target = normalizeIdentifier(username);
  return users.some((u) => normalizeIdentifier(u.username) === target);
}

export async function isEmailTaken(email) {
  const users = await readUsers();
  const target = normalizeIdentifier(email);
  return users.some((u) => normalizeIdentifier(u.email) === target);
}

async function assertUniqueIdentity(users, { email, username }) {
  const normalizedEmail = normalizeIdentifier(email);
  const normalizedUsername = normalizeIdentifier(username);
  if (users.some((u) => normalizeIdentifier(u.email) === normalizedEmail)) {
    throw new Error('Questa email è già registrata.');
  }
  if (users.some((u) => normalizeIdentifier(u.username) === normalizedUsername)) {
    throw new Error('Questo nome utente è già in uso, scegline un altro.');
  }
}

export async function registerCustomer({ email, password, username }) {
  const users = await readUsers();
  await assertUniqueIdentity(users, { email, username });

  const user = {
    id: `cust_${Date.now()}`,
    role: 'customer',
    email: email.trim(),
    username: username.trim(),
    passwordHash: await hashPassword(password),
    createdAt: new Date().toISOString(),
  };

  await writeUsers([...users, user]);
  await AsyncStorage.setItem(SESSION_KEY, user.id);
  return toPublicUser(user);
}

export async function registerVendor({ email, password, username, phone, shopAddress, license }) {
  const users = await readUsers();
  await assertUniqueIdentity(users, { email, username });

  const user = {
    id: `vend_${Date.now()}`,
    role: 'vendor',
    email: email.trim(),
    username: username.trim(),
    passwordHash: await hashPassword(password),
    phone: phone.trim(),
    shopAddress: shopAddress.trim(),
    license: license ? { name: license.name, mimeType: license.mimeType ?? null } : null,
    // A real backend would flip this to 'approved'/'rejected' once a human
    // (or automated check) has reviewed the uploaded license document.
    licenseStatus: 'pending_review',
    createdAt: new Date().toISOString(),
  };

  await writeUsers([...users, user]);
  await AsyncStorage.setItem(SESSION_KEY, user.id);
  return toPublicUser(user);
}

export async function login({ email, password }) {
  const users = await readUsers();
  const target = normalizeIdentifier(email);
  const user = users.find((u) => normalizeIdentifier(u.email) === target);
  if (!user) {
    throw new Error('Email o password non corretti.');
  }
  const hashed = await hashPassword(password);
  if (hashed !== user.passwordHash) {
    throw new Error('Email o password non corretti.');
  }
  await AsyncStorage.setItem(SESSION_KEY, user.id);
  return toPublicUser(user);
}

export async function logout() {
  await AsyncStorage.removeItem(SESSION_KEY);
}

export async function getSessionUser() {
  const id = await AsyncStorage.getItem(SESSION_KEY);
  if (!id) return null;
  const users = await readUsers();
  const user = users.find((u) => u.id === id);
  return user ? toPublicUser(user) : null;
}

// Never expose the password hash to the UI layer.
function toPublicUser(user) {
  const { passwordHash, ...publicUser } = user;
  return publicUser;
}
