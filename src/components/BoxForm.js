import { useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';
import FormField from './FormField';
import PrimaryButton from './PrimaryButton';
import { colors, radius, spacing } from '../theme';
import { isValidDate, isValidTime } from '../validation';

function pad(n) {
  return String(n).padStart(2, '0');
}

// A box's expire_at (backend/app/schemas.py::BoxRequest) is one ISO
// datetime, but it's friendlier to edit as separate date/time text fields
// (same HH:MM style already used for shop hours) — split for display...
function splitLocalDateTime(isoString) {
  const d = new Date(isoString);
  return {
    date: `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`,
    time: `${pad(d.getHours())}:${pad(d.getMinutes())}`,
  };
}

// ...and joined back into one ISO (UTC) datetime on submit. Both sides are
// parsed/formatted in the device's local time zone, so "ritira entro le
// 20:00" means 20:00 wherever the vendor actually is.
function joinToIso(date, time) {
  return new Date(`${date}T${time}:00`).toISOString();
}

function defaultExpiry() {
  const in6Hours = new Date(Date.now() + 6 * 60 * 60 * 1000);
  return splitLocalDateTime(in6Hours.toISOString());
}

// Create/edit form for one of a vendor's boxes ("surprise bags" — the
// Too-Good-To-Go-style core of the app; see backend/app/schemas.py::BoxRequest).
// `initialBox` (a BoxPublic from the backend) prefills for editing.
export default function BoxForm({ initialBox, onSubmit, onCancel, submitLabel }) {
  const initialExpiry = initialBox ? splitLocalDateTime(initialBox.expire_at) : defaultExpiry();

  const [name, setName] = useState(initialBox?.name ?? '');
  const [description, setDescription] = useState(initialBox?.description ?? '');
  const [category, setCategory] = useState(initialBox?.category ?? '');
  const [allergens, setAllergens] = useState(initialBox?.allergens ?? 'Nessuno');
  const [price, setPrice] = useState(initialBox?.price != null ? String(initialBox.price) : '');
  const [maxBoxes, setMaxBoxes] = useState(initialBox?.max_boxes != null ? String(initialBox.max_boxes) : '');
  const [pickupStart, setPickupStart] = useState(initialBox?.pickup_window_start ?? '18:00');
  const [pickupEnd, setPickupEnd] = useState(initialBox?.pickup_window_end ?? '19:00');
  const [expireDate, setExpireDate] = useState(initialExpiry.date);
  const [expireTime, setExpireTime] = useState(initialExpiry.time);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState(null);

  function validate() {
    if (name.trim().length < 2) return 'Il nome della box deve avere almeno 2 caratteri.';
    if (!description.trim()) return 'La descrizione è obbligatoria.';
    if (!category.trim()) return 'Indica una categoria (es. Frutta e Verdura, Panetteria...).';
    if (!allergens.trim()) return "Indica gli allergeni, anche solo 'Nessuno'.";
    const priceNum = Number(price.replace(',', '.'));
    if (!price || Number.isNaN(priceNum) || priceNum <= 0) return 'Il prezzo deve essere un numero maggiore di 0.';
    const quantity = Number(maxBoxes);
    if (!maxBoxes || !Number.isInteger(quantity) || quantity <= 0) {
      return 'La quantità disponibile deve essere un numero intero maggiore di 0.';
    }
    if (!isValidTime(pickupStart) || !isValidTime(pickupEnd)) {
      return 'Fascia di ritiro: usa il formato HH:MM (es. 18:00).';
    }
    if (pickupStart >= pickupEnd) {
      return "La fascia di ritiro deve avere un orario di inizio precedente a quello di fine.";
    }
    if (!isValidDate(expireDate)) return 'Data di scadenza: usa il formato AAAA-MM-GG.';
    if (!isValidTime(expireTime)) return 'Orario di scadenza: usa il formato HH:MM.';
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
        description: description.trim(),
        category: category.trim(),
        allergens: allergens.trim(),
        price: Number(price.replace(',', '.')),
        max_boxes: Number(maxBoxes),
        pickup_window_start: pickupStart,
        pickup_window_end: pickupEnd,
        expire_at: joinToIso(expireDate, expireTime),
      });
    } catch (err) {
      setError(err.message);
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <View>
      <FormField label="Nome della box" placeholder="es. Box Frutta Mista" value={name} onChangeText={setName} />
      <FormField
        label="Descrizione"
        placeholder="es. Cassetta di frutta di stagione in eccedenza"
        value={description}
        onChangeText={setDescription}
        multiline
      />
      <FormField
        label="Categoria"
        placeholder="es. Frutta e Verdura, Panetteria..."
        value={category}
        onChangeText={setCategory}
      />
      <FormField
        label="Allergeni"
        placeholder="es. Glutine, Uova — oppure 'Nessuno'"
        value={allergens}
        onChangeText={setAllergens}
      />

      <View style={styles.row}>
        <FormField
          label="Prezzo (€)"
          placeholder="4.99"
          keyboardType="decimal-pad"
          value={price}
          onChangeText={setPrice}
          style={styles.rowField}
        />
        <FormField
          label="Quantità disponibile"
          placeholder="5"
          keyboardType="number-pad"
          value={maxBoxes}
          onChangeText={setMaxBoxes}
          style={styles.rowField}
        />
      </View>

      <View style={styles.row}>
        <FormField
          label="Ritiro dalle (HH:MM)"
          placeholder="18:00"
          value={pickupStart}
          onChangeText={setPickupStart}
          style={styles.rowField}
          maxLength={5}
        />
        <FormField
          label="alle (HH:MM)"
          placeholder="19:00"
          value={pickupEnd}
          onChangeText={setPickupEnd}
          style={styles.rowField}
          maxLength={5}
        />
      </View>

      <View style={styles.row}>
        <FormField
          label="Scade il (AAAA-MM-GG)"
          placeholder="2026-09-13"
          value={expireDate}
          onChangeText={setExpireDate}
          style={styles.rowField}
          maxLength={10}
        />
        <FormField
          label="Alle ore (HH:MM)"
          placeholder="20:00"
          value={expireTime}
          onChangeText={setExpireTime}
          style={styles.rowField}
          maxLength={5}
        />
      </View>

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
  row: { flexDirection: 'row', gap: spacing.sm },
  rowField: { flex: 1 },
  errorBox: {
    backgroundColor: colors.errorBackground,
    borderRadius: radius.sm,
    padding: spacing.sm,
    marginBottom: spacing.md,
  },
  errorText: { color: colors.error },
  cancelButton: { marginTop: spacing.sm },
});
