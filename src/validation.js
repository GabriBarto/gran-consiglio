// Shared form validation rules for the registration/login flows.
// Kept dependency-free (plain regex/string checks) on purpose.

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
// Letters (incl. accented), digits, spaces, underscore and hyphen — spaces are
// allowed so a vendor can use their shop name ("Vivaio Rossi") as username.
const USERNAME_RE = /^[\p{L}0-9 _-]{3,30}$/u;
const PHONE_RE = /^[+\d][\d\s-]{7,18}$/;
// 24h "HH:MM" — mirrors backend TIME_RE in app/schemas.py (shop opening/pickup times).
const TIME_RE = /^([01]\d|2[0-3]):[0-5]\d$/;
// "YYYY-MM-DD" — used for a box's pickup-by date (see src/components/BoxForm.js).
const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;

export function isValidEmail(email) {
  return EMAIL_RE.test(String(email).trim());
}

// Returns an error message, or null if the password is acceptable.
export function validatePassword(password) {
  if (!password || password.length < 8) {
    return 'La password deve contenere almeno 8 caratteri.';
  }
  if (!/[A-Za-z]/.test(password) || !/[0-9]/.test(password)) {
    return 'La password deve contenere almeno una lettera e un numero.';
  }
  return null;
}

export function validateUsername(username) {
  const trimmed = String(username || '').trim();
  if (!USERNAME_RE.test(trimmed)) {
    return 'Il nome utente deve avere 3-30 caratteri (lettere, numeri, spazi, - o _).';
  }
  return null;
}

export function isValidPhone(phone) {
  return PHONE_RE.test(String(phone).trim());
}

export function isValidTime(value) {
  return TIME_RE.test(String(value || '').trim());
}

export function isValidDate(value) {
  if (!DATE_RE.test(String(value || '').trim())) return false;
  const parsed = new Date(`${value}T00:00:00`);
  return !Number.isNaN(parsed.getTime());
}

// Usernames/emails are stored normalized so "Vivaio Rossi" and "vivaio  rossi"
// are treated as the same identity when checking uniqueness.
export function normalizeIdentifier(value) {
  return String(value || '').trim().toLowerCase().replace(/\s+/g, ' ');
}
