import * as DocumentPicker from 'expo-document-picker';
import * as Location from 'expo-location';
import { useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';
import FormField from './FormField';
import PrimaryButton from './PrimaryButton';
import { colors, radius, spacing } from '../theme';
import { isValidPhone, isValidTime } from '../validation';

// Create/edit form for a vendor's own shop (backend/app/schemas.py::ShopRequest:
// name, address, lat/lng, phone, opening_time, pickup_window_start/end — a
// single daily schedule, not per-weekday, and no separate city field).
// `initialShop` (a ShopPublic from the backend) prefills for editing; when
// absent this is the rare "create from scratch" flow (most vendors already
// have a placeholder shop auto-created at registration — see
// backend/app/routers/auth.py), which per POST /shops also needs a license
// file.
export default function ShopForm({ initialShop, onSubmit, onCancel, submitLabel }) {
  const isCreating = !initialShop;

  const [name, setName] = useState(initialShop?.name ?? '');
  const [address, setAddress] = useState(initialShop?.address ?? '');
  const [phone, setPhone] = useState(initialShop?.phone ?? '');
  const [lat, setLat] = useState(initialShop?.lat != null ? String(initialShop.lat) : '');
  const [lng, setLng] = useState(initialShop?.lng != null ? String(initialShop.lng) : '');
  const [openingTime, setOpeningTime] = useState(initialShop?.opening_time ?? '09:00');
  const [pickupStart, setPickupStart] = useState(initialShop?.pickup_window_start ?? '18:00');
  const [pickupEnd, setPickupEnd] = useState(initialShop?.pickup_window_end ?? '19:00');
  const [licenseFile, setLicenseFile] = useState(null);
  const [isLocating, setIsLocating] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState(null);

  async function handleUseCurrentPosition() {
    setError(null);
    setIsLocating(true);
    try {
      const { status } = await Location.requestForegroundPermissionsAsync();
      if (status !== 'granted') {
        setError('Permesso di localizzazione negato: inserisci lat/lng manualmente.');
        return;
      }
      const position = await Location.getCurrentPositionAsync({});
      setLat(position.coords.latitude.toFixed(5));
      setLng(position.coords.longitude.toFixed(5));
    } catch {
      setError('Impossibile ottenere la posizione attuale.');
    } finally {
      setIsLocating(false);
    }
  }

  async function handlePickLicense() {
    const result = await DocumentPicker.getDocumentAsync({
      type: ['application/pdf', 'image/*'],
      copyToCacheDirectory: true,
    });
    if (result.canceled) return;
    setLicenseFile(result.assets[0]);
  }

  function validate() {
    if (name.trim().length < 2) return 'Il nome del negozio deve avere almeno 2 caratteri.';
    if (!address.trim()) return "L'indirizzo è obbligatorio.";
    if (!isValidPhone(phone)) return 'Inserisci un recapito telefonico valido.';
    const latNum = Number(lat);
    const lngNum = Number(lng);
    if (!lat || Number.isNaN(latNum) || latNum < -90 || latNum > 90) {
      return 'La latitudine deve essere un numero tra -90 e 90.';
    }
    if (!lng || Number.isNaN(lngNum) || lngNum < -180 || lngNum > 180) {
      return 'La longitudine deve essere un numero tra -180 e 180.';
    }
    if (!isValidTime(openingTime)) return "Orario di apertura: usa il formato HH:MM (es. 08:00).";
    if (!isValidTime(pickupStart) || !isValidTime(pickupEnd)) {
      return 'Fascia di ritiro: usa il formato HH:MM (es. 18:00).';
    }
    if (pickupStart >= pickupEnd) {
      return "La fascia di ritiro deve avere un orario di inizio precedente a quello di fine.";
    }
    if (isCreating && !licenseFile) {
      return 'Carica un documento della licenza di vendita.';
    }
    return null;
  }

  async function handleSubmit() {
    const validationError = validate();
    if (validationError) {
      setError(validationError);
      return;
    }
    setError(null);
    setIsSubmitting(true);
    try {
      await onSubmit({
        name: name.trim(),
        address: address.trim(),
        phone: phone.trim(),
        lat: Number(lat),
        lng: Number(lng),
        opening_time: openingTime,
        pickup_window_start: pickupStart,
        pickup_window_end: pickupEnd,
        ...(isCreating ? { licenseFile } : {}),
      });
    } catch (err) {
      setError(err.message);
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <View>
      <FormField label="Nome del negozio" placeholder="es. Vivaio Rossi" value={name} onChangeText={setName} />
      <FormField
        label="Indirizzo (via e città)"
        placeholder="es. Via delle Rose 12, Firenze"
        value={address}
        onChangeText={setAddress}
      />
      <FormField
        label="Telefono"
        placeholder="+39 333 1234567"
        keyboardType="phone-pad"
        value={phone}
        onChangeText={setPhone}
      />

      <View style={styles.coordsRow}>
        <FormField
          label="Latitudine"
          placeholder="43.7696"
          keyboardType="numbers-and-punctuation"
          value={lat}
          onChangeText={setLat}
          style={styles.coordField}
        />
        <FormField
          label="Longitudine"
          placeholder="11.2558"
          keyboardType="numbers-and-punctuation"
          value={lng}
          onChangeText={setLng}
          style={styles.coordField}
        />
      </View>
      <PrimaryButton
        title="📍 Usa la mia posizione attuale"
        variant="outline"
        loading={isLocating}
        onPress={handleUseCurrentPosition}
        style={styles.locateButton}
      />

      <FormField
        label="Orario di apertura (HH:MM)"
        placeholder="09:00"
        value={openingTime}
        onChangeText={setOpeningTime}
        maxLength={5}
      />
      <View style={styles.coordsRow}>
        <FormField
          label="Ritiro dalle (HH:MM)"
          placeholder="18:00"
          value={pickupStart}
          onChangeText={setPickupStart}
          style={styles.coordField}
          maxLength={5}
        />
        <FormField
          label="alle (HH:MM)"
          placeholder="19:00"
          value={pickupEnd}
          onChangeText={setPickupEnd}
          style={styles.coordField}
          maxLength={5}
        />
      </View>

      {isCreating ? (
        <View style={styles.licenseSection}>
          <Text style={styles.sectionLabel}>Licenza di vendita</Text>
          <PrimaryButton
            title={licenseFile ? 'Cambia documento' : 'Carica documento (PDF o immagine)'}
            variant="outline"
            onPress={handlePickLicense}
          />
          {licenseFile ? <Text style={styles.licenseName}>📎 {licenseFile.name}</Text> : null}
        </View>
      ) : null}

      {error ? (
        <View style={styles.errorBox}>
          <Text style={styles.errorText}>{error}</Text>
        </View>
      ) : null}

      <PrimaryButton title={submitLabel ?? 'Salva'} onPress={handleSubmit} loading={isSubmitting} />
      {onCancel ? (
        <PrimaryButton title="Annulla" variant="outline" onPress={onCancel} style={styles.cancelButton} />
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  coordsRow: { flexDirection: 'row', gap: spacing.sm },
  coordField: { flex: 1 },
  locateButton: { marginBottom: spacing.md },
  sectionLabel: { fontSize: 14, fontWeight: '600', color: colors.text, marginBottom: spacing.xs },
  licenseSection: {
    marginBottom: spacing.md,
    padding: spacing.md,
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
  },
  licenseName: { marginTop: spacing.sm, color: colors.text },
  errorBox: {
    backgroundColor: colors.errorBackground,
    borderRadius: radius.sm,
    padding: spacing.sm,
    marginBottom: spacing.md,
  },
  errorText: { color: colors.error },
  cancelButton: { marginTop: spacing.sm },
});
