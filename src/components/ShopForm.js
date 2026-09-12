import * as Location from 'expo-location';
import { useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';
import DayScheduleEditor from './DayScheduleEditor';
import FormField from './FormField';
import PrimaryButton from './PrimaryButton';
import { colors, radius, spacing } from '../theme';
import { isValidPhone } from '../validation';
import { defaultSchedule, validateSchedule } from '../utils/schedule';

// Create/edit form for a vendor's own shop (backend/app/schemas.py::ShopRequest).
// `initialShop` (a ShopPublic from the backend) prefills for editing; omit it
// for the "create my shop" flow.
export default function ShopForm({ initialShop, onSubmit, onCancel, submitLabel }) {
  const [name, setName] = useState(initialShop?.name ?? '');
  const [address, setAddress] = useState(initialShop?.address ?? '');
  const [city, setCity] = useState(initialShop?.city ?? '');
  const [phone, setPhone] = useState(initialShop?.phone ?? '');
  const [lat, setLat] = useState(initialShop?.lat != null ? String(initialShop.lat) : '');
  const [lng, setLng] = useState(initialShop?.lng != null ? String(initialShop.lng) : '');
  const [openingHours, setOpeningHours] = useState(initialShop?.opening_hours ?? defaultSchedule('08:00', '19:00'));
  const [pickupWindow, setPickupWindow] = useState(initialShop?.pickup_window ?? defaultSchedule('18:00', '19:00'));
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

  function validate() {
    if (name.trim().length < 2) return 'Il nome del negozio deve avere almeno 2 caratteri.';
    if (!address.trim()) return "L'indirizzo è obbligatorio.";
    if (!city.trim()) return 'La città è obbligatoria.';
    if (!isValidPhone(phone)) return 'Inserisci un recapito telefonico valido.';
    const latNum = Number(lat);
    const lngNum = Number(lng);
    if (!lat || Number.isNaN(latNum) || latNum < -90 || latNum > 90) {
      return 'La latitudine deve essere un numero tra -90 e 90.';
    }
    if (!lng || Number.isNaN(lngNum) || lngNum < -180 || lngNum > 180) {
      return 'La longitudine deve essere un numero tra -180 e 180.';
    }
    return (
      validateSchedule(openingHours, 'Orari di apertura') || validateSchedule(pickupWindow, 'Fascia di ritiro')
    );
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
        city: city.trim(),
        phone: phone.trim(),
        lat: Number(lat),
        lng: Number(lng),
        opening_hours: openingHours,
        pickup_window: pickupWindow,
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
      <FormField label="Indirizzo" placeholder="Via, numero civico" value={address} onChangeText={setAddress} />
      <FormField label="Città" placeholder="es. Firenze" value={city} onChangeText={setCity} />
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

      <DayScheduleEditor label="Orari di apertura" value={openingHours} onChange={setOpeningHours} />
      <DayScheduleEditor label="Fascia di ritiro per il cliente" value={pickupWindow} onChange={setPickupWindow} />

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
  errorBox: {
    backgroundColor: colors.errorBackground,
    borderRadius: radius.sm,
    padding: spacing.sm,
    marginBottom: spacing.md,
  },
  errorText: { color: colors.error },
  cancelButton: { marginTop: spacing.sm },
});
