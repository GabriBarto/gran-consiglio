// ---------------------------------------------------------------------------
// AI "scheda di recupero pianta" — backend/app/routers/plant_care.py.
//
// The response always carries a `disclaimer` string: show it next to the
// sheet, it is the legal "orientativa" notice.
// ---------------------------------------------------------------------------
import { apiRequest } from './client';
import { toUploadFile } from '../utils/files';

// Public: species list for the picker ({ id, common_name, scientific_name }).
export async function listPlantSpecies() {
  return apiRequest('/plant-care/species');
}

// Needs at least one of speciesId / photo (an expo-image-picker asset).
// symptoms is optional free text (max 1000 chars).
export async function createRecoverySheet({ speciesId, symptoms, photo } = {}) {
  const form = new FormData();
  if (speciesId) form.append('species_id', speciesId);
  if (symptoms?.trim()) form.append('symptoms', symptoms.trim());
  if (photo) {
    // On web the picker hands back a real browser File (asset.file, web
    // only) — expo-file-system's File only wraps native file:// URIs.
    const part = photo.file ?? toUploadFile(photo);
    // fileName can be null on Android: the URI's last segment still carries
    // the real extension, which the backend uses if the MIME type is generic.
    const name = photo.fileName ?? photo.file?.name ?? photo.uri?.split('/').pop() ?? 'pianta.jpg';
    form.append('photo', part, name);
  }
  return apiRequest('/plant-care/recovery-sheet', { method: 'POST', auth: true, form });
}
