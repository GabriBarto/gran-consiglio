import * as ImagePicker from 'expo-image-picker';
import { useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Image,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { createRecoverySheet, listPlantSpecies } from '../src/api/plantCare';
import FormField from '../src/components/FormField';
import PrimaryButton from '../src/components/PrimaryButton';
import { colors, radius, spacing } from '../src/theme';

// Must match settings.max_plant_photo_size_mb in backend/app/config.py.
const MAX_PHOTO_MB = 5;
const MAX_SYMPTOMS_LENGTH = 1000;

// quality < 1 re-encodes the picked photo, which keeps typical phone photos
// (often 5-10 MB at full quality) under the backend's size limit.
const PICKER_OPTIONS = { mediaTypes: 'images', quality: 0.7 };

const SOURCE_LABEL = {
  catalog: 'Specie scelta da te',
  plantnet: 'Riconosciuta dalla foto (PlantNet)',
  ai_vision: "Riconosciuta dalla foto (AI)",
};

const CONFIDENCE_LABEL = {
  alta: 'affidabilità alta',
  media: 'affidabilità media',
  bassa: 'affidabilità bassa',
  non_determinabile: 'specie non determinabile',
};

// AI "scheda di recupero pianta" (backend/app/routers/plant_care.py): pick
// a species and/or take or choose a photo, optionally describe the symptoms,
// and get an orientative recovery sheet — always shown with its disclaimer.
export default function PlantCare() {
  const [species, setSpecies] = useState([]);
  const [speciesId, setSpeciesId] = useState(null);
  const [photo, setPhoto] = useState(null); // expo-image-picker asset
  const [symptoms, setSymptoms] = useState('');
  const [sheet, setSheet] = useState(null);
  const [isLoadingSpecies, setIsLoadingSpecies] = useState(true);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    listPlantSpecies()
      .then(setSpecies)
      .catch((err) => setError(err.message))
      .finally(() => setIsLoadingSpecies(false));
  }, []);

  function applyPickedAsset(result) {
    // On web `canceled` isn't reported, so also guard on assets.
    if (result.canceled || !result.assets?.length) return;
    const asset = result.assets[0];
    if (asset.fileSize && asset.fileSize > MAX_PHOTO_MB * 1024 * 1024) {
      setError(`La foto supera i ${MAX_PHOTO_MB} MB. Scegline una più leggera.`);
      return;
    }
    setError(null);
    setPhoto(asset);
  }

  async function handleTakePhoto() {
    setError(null);
    try {
      if (Platform.OS !== 'web') {
        const { granted } = await ImagePicker.requestCameraPermissionsAsync();
        if (!granted) {
          setError('Permesso fotocamera negato. Puoi abilitarlo dalle impostazioni del telefono.');
          return;
        }
      }
      applyPickedAsset(await ImagePicker.launchCameraAsync(PICKER_OPTIONS));
    } catch {
      setError('Impossibile aprire la fotocamera.');
    }
  }

  async function handlePickPhoto() {
    setError(null);
    try {
      applyPickedAsset(await ImagePicker.launchImageLibraryAsync(PICKER_OPTIONS));
    } catch {
      setError('Impossibile aprire la galleria.');
    }
  }

  async function handleAnalyze() {
    setError(null);
    setIsAnalyzing(true);
    try {
      setSheet(await createRecoverySheet({ speciesId, symptoms, photo }));
    } catch (err) {
      setError(err.message);
    } finally {
      setIsAnalyzing(false);
    }
  }

  function handleReset() {
    setSheet(null);
    setPhoto(null);
    setSpeciesId(null);
    setSymptoms('');
    setError(null);
  }

  const canAnalyze = Boolean(speciesId || photo);

  return (
    <KeyboardAvoidingView style={styles.flex} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
        {sheet ? (
          <SheetView sheet={sheet} photoUri={photo?.uri} onReset={handleReset} />
        ) : (
          <View>
            <Text style={styles.intro}>
              Scatta o scegli una foto della pianta, oppure selezionane la specie: riceverai una scheda con i
              consigli per farla riprendere.
            </Text>

            <Text style={styles.sectionTitle}>Foto della pianta</Text>
            {photo ? (
              <View style={styles.photoBox}>
                <Image source={{ uri: photo.uri }} style={styles.photo} resizeMode="cover" />
                <View style={styles.photoActions}>
                  <PrimaryButton title="Cambia foto" variant="outline" onPress={handlePickPhoto} style={styles.flex} />
                  <PrimaryButton title="Rimuovi" variant="outline" onPress={() => setPhoto(null)} style={styles.flex} />
                </View>
              </View>
            ) : (
              <View style={styles.photoActions}>
                <PrimaryButton title="📷 Scatta foto" variant="outline" onPress={handleTakePhoto} style={styles.flex} />
                <PrimaryButton title="🖼️ Galleria" variant="outline" onPress={handlePickPhoto} style={styles.flex} />
              </View>
            )}

            <Text style={styles.sectionTitle}>Specie {photo ? '(facoltativa)' : ''}</Text>
            <Text style={styles.hint}>
              {photo
                ? 'Se non la conosci, lasciala vuota: verrà riconosciuta dalla foto.'
                : 'Scegli la specie, oppure aggiungi una foto.'}
            </Text>
            {isLoadingSpecies ? (
              <ActivityIndicator color={colors.primary} style={styles.spinner} />
            ) : (
              <View style={styles.chips}>
                {species.map((item) => {
                  const selected = item.id === speciesId;
                  return (
                    <Pressable
                      key={item.id}
                      onPress={() => setSpeciesId(selected ? null : item.id)}
                      style={[styles.chip, selected && styles.chipActive]}
                    >
                      <Text style={[styles.chipText, selected && styles.chipTextActive]}>{item.common_name}</Text>
                    </Pressable>
                  );
                })}
              </View>
            )}

            <FormField
              label="Cosa noti? (facoltativo)"
              placeholder="es. foglie gialle con bordi marroni, annaffio ogni 2 giorni"
              value={symptoms}
              onChangeText={setSymptoms}
              multiline
              maxLength={MAX_SYMPTOMS_LENGTH}
              autoCapitalize="sentences"
              autoCorrect
              style={styles.symptoms}
            />

            {error ? (
              <View style={styles.errorBox}>
                <Text style={styles.errorText}>{error}</Text>
              </View>
            ) : null}

            <PrimaryButton
              title="Analizza la pianta 🌱"
              onPress={handleAnalyze}
              loading={isAnalyzing}
              disabled={!canAnalyze}
            />
            {isAnalyzing ? <Text style={styles.hint}>Analisi in corso, può richiedere fino a 30 secondi…</Text> : null}
          </View>
        )}
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

function SheetView({ sheet, photoUri, onReset }) {
  const sourceLabel = SOURCE_LABEL[sheet.identification_source];
  const confidence = CONFIDENCE_LABEL[sheet.identification_confidence] ?? sheet.identification_confidence;
  return (
    <View>
      {photoUri ? <Image source={{ uri: photoUri }} style={styles.photo} resizeMode="cover" /> : null}

      <View style={styles.card}>
        <Text style={styles.species}>{sheet.species}</Text>
        <Text style={styles.hint}>
          {sourceLabel}
          {sheet.identification_source === 'catalog' ? '' : ` · ${confidence}`}
        </Text>
        <Text style={styles.body}>{sheet.health_assessment}</Text>
      </View>

      <SheetSection title="🔎 Cause probabili" items={sheet.likely_causes} />
      <SheetSection title="🩹 Cosa fare" items={sheet.recovery_steps} numbered />
      <SheetSection title="🌿 Cure quotidiane" items={sheet.care_tips} />
      <SheetSection title="⚠️ Quando rivolgersi a un vivaista" items={sheet.warning_signs} />

      {/* Legal "orientativa" notice: always shown, text comes from the backend. */}
      <View style={styles.disclaimerBox}>
        <Text style={styles.disclaimerTitle}>Avvertenza</Text>
        <Text style={styles.disclaimerText}>{sheet.disclaimer}</Text>
      </View>

      <PrimaryButton title="Nuova analisi" variant="outline" onPress={onReset} />
    </View>
  );
}

function SheetSection({ title, items, numbered = false }) {
  if (!items?.length) return null;
  return (
    <View style={styles.card}>
      <Text style={styles.cardTitle}>{title}</Text>
      {items.map((item, index) => (
        <View key={index} style={styles.listRow}>
          <Text style={styles.bullet}>{numbered ? `${index + 1}.` : '•'}</Text>
          <Text style={styles.listText}>{item}</Text>
        </View>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  content: { padding: spacing.lg, paddingBottom: spacing.xl },
  intro: { fontSize: 15, color: colors.text, marginBottom: spacing.md },
  sectionTitle: { fontSize: 16, fontWeight: '700', color: colors.text, marginTop: spacing.md, marginBottom: spacing.xs },
  hint: { fontSize: 13, color: colors.textMuted, marginBottom: spacing.sm },
  photoBox: { gap: spacing.sm },
  photo: { width: '100%', aspectRatio: 4 / 3, borderRadius: radius.md, backgroundColor: colors.border },
  photoActions: { flexDirection: 'row', gap: spacing.sm },
  spinner: { marginVertical: spacing.md },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.xs, marginBottom: spacing.md },
  chip: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.lg,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
    backgroundColor: colors.surface,
  },
  chipActive: { backgroundColor: colors.primary, borderColor: colors.primary },
  chipText: { color: colors.text, fontWeight: '600' },
  chipTextActive: { color: '#fff' },
  symptoms: { marginTop: spacing.sm },
  errorBox: { backgroundColor: colors.errorBackground, borderRadius: 8, padding: spacing.sm, marginBottom: spacing.md },
  errorText: { color: colors.error },
  card: {
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.md,
    marginTop: spacing.md,
  },
  species: { fontSize: 18, fontWeight: '800', color: colors.text, marginBottom: spacing.xs },
  body: { fontSize: 15, color: colors.text, lineHeight: 21 },
  cardTitle: { fontSize: 16, fontWeight: '700', color: colors.text, marginBottom: spacing.sm },
  listRow: { flexDirection: 'row', gap: spacing.sm, marginBottom: spacing.xs },
  bullet: { fontSize: 15, color: colors.primaryDark, fontWeight: '700', minWidth: 16 },
  listText: { flex: 1, fontSize: 15, color: colors.text, lineHeight: 21 },
  disclaimerBox: {
    backgroundColor: '#FFF8E1',
    borderColor: colors.info,
    borderWidth: 1,
    borderRadius: radius.md,
    padding: spacing.md,
    marginVertical: spacing.md,
  },
  disclaimerTitle: { fontSize: 14, fontWeight: '700', color: colors.text, marginBottom: spacing.xs },
  disclaimerText: { fontSize: 13, color: colors.text, lineHeight: 19 },
});
