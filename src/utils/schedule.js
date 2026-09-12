// Shared helpers for the weekly opening_hours / pickup_window arrays used by
// backend.app.schemas.DaySchedule (one entry per weekday, HH:MM 24h strings
// or closed: true) — see backend/app/schemas.py.

export const WEEKDAYS = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'];

export const WEEKDAY_LABELS = {
  mon: 'Lunedì',
  tue: 'Martedì',
  wed: 'Mercoledì',
  thu: 'Giovedì',
  fri: 'Venerdì',
  sat: 'Sabato',
  sun: 'Domenica',
};

export const WEEKDAY_SHORT = {
  mon: 'Lun',
  tue: 'Mar',
  wed: 'Mer',
  thu: 'Gio',
  fri: 'Ven',
  sat: 'Sab',
  sun: 'Dom',
};

const TIME_RE = /^([01]\d|2[0-3]):[0-5]\d$/;

export function isValidTime(value) {
  return TIME_RE.test(value);
}

export function defaultSchedule(start, end, closedDays = ['sun']) {
  return WEEKDAYS.map((day) =>
    closedDays.includes(day) ? { day, closed: true, start: null, end: null } : { day, closed: false, start, end }
  );
}

// Mirrors backend DaySchedule's own validation (see schemas.py) so obvious
// mistakes are caught before a round trip to the server.
export function validateSchedule(schedule, label) {
  for (const slot of schedule) {
    if (slot.closed) continue;
    if (!slot.start || !slot.end || !isValidTime(slot.start) || !isValidTime(slot.end)) {
      return `${label} — ${WEEKDAY_LABELS[slot.day]}: usa il formato HH:MM (es. 08:00).`;
    }
    if (slot.start >= slot.end) {
      return `${label} — ${WEEKDAY_LABELS[slot.day]}: l'orario di inizio deve precedere quello di fine.`;
    }
  }
  return null;
}

export function todayWeekday() {
  const idx = new Date().getDay(); // 0 = Sunday .. 6 = Saturday
  return idx === 0 ? 'sun' : WEEKDAYS[idx - 1];
}

export function formatSlot(slot) {
  if (!slot || slot.closed) return 'Chiuso';
  return `${slot.start}–${slot.end}`;
}
