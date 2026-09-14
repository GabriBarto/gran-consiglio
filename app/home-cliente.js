import * as Location from 'expo-location';
import { useRouter } from 'expo-router';
import { useEffect, useState } from 'react';
import { ActivityIndicator, FlatList, Pressable, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { listNotifications } from '../src/api/notifications';
import { searchShops } from '../src/api/shops';
import FormField from '../src/components/FormField';
import PrimaryButton from '../src/components/PrimaryButton';
import { useAuth } from '../src/context/AuthContext';
import { colors, radius, spacing } from '../src/theme';

const RADIUS_OPTIONS_KM = [5, 10, 20, 50];

export default function HomeCliente() {
  const router = useRouter();
  const { user, logout } = useAuth();

  const [city, setCity] = useState('');
  const [coords, setCoords] = useState(null); // { lat, lng } once "vicino a me" is used
  const [radiusKm, setRadiusKm] = useState(10);
  const [shops, setShops] = useState([]);
  const [isSearching, setIsSearching] = useState(false);
  const [isLocating, setIsLocating] = useState(false);
  const [error, setError] = useState(null);
  const [hasSearched, setHasSearched] = useState(false);
  const [unreadCount, setUnreadCount] = useState(0);

  useEffect(() => {
    listNotifications()
      .then((items) => setUnreadCount(items.filter((n) => !n.is_read).length))
      .catch(() => {}); // non-fatal: the rest of the screen works without this
  }, []);

  async function runSearch({ withCoords = coords, withRadius = radiusKm } = {}) {
    setError(null);
    setIsSearching(true);
    try {
      const result = await searchShops({
        city: city.trim() || undefined,
        lat: withCoords?.lat,
        lng: withCoords?.lng,
        radiusKm: withCoords ? withRadius : undefined,
      });
      setShops(result.items);
      setHasSearched(true);
    } catch (err) {
      setError(err.message);
    } finally {
      setIsSearching(false);
    }
  }

  async function handleUseLocation() {
    setError(null);
    setIsLocating(true);
    try {
      const { status } = await Location.requestForegroundPermissionsAsync();
      if (status !== 'granted') {
        setError('Permesso di localizzazione negato.');
        return;
      }
      const position = await Location.getCurrentPositionAsync({});
      const nextCoords = { lat: position.coords.latitude, lng: position.coords.longitude };
      setCoords(nextCoords);
      await runSearch({ withCoords: nextCoords, withRadius: radiusKm });
    } catch {
      setError('Impossibile ottenere la posizione attuale.');
    } finally {
      setIsLocating(false);
    }
  }

  async function handleRadiusChange(km) {
    setRadiusKm(km);
    if (coords) await runSearch({ withRadius: km });
  }

  async function handleLogout() {
    await logout();
    router.replace('/');
  }

  return (
    <SafeAreaView style={styles.container} edges={['top', 'left', 'right']}>
      <FlatList
        data={shops}
        keyExtractor={(item) => item.id}
        contentContainerStyle={styles.listContent}
        ListHeaderComponent={
          <View>
            <View style={styles.header}>
              <View>
                <Text style={styles.title}>Ciao, {user?.username}! 🪴</Text>
                <Text style={styles.subtitle}>Trova vivai e fiorai vicino a te.</Text>
              </View>
              <View style={styles.headerActions}>
                <PrimaryButton title="I miei ordini 🧾" variant="outline" onPress={() => router.push('/orders')} />
                <PrimaryButton
                  title={unreadCount > 0 ? `Notifiche 🔔 (${unreadCount})` : 'Notifiche 🔔'}
                  variant="outline"
                  onPress={() => router.push('/notifications')}
                  style={styles.logoutButton}
                />
                <PrimaryButton title="Esci" variant="outline" onPress={handleLogout} style={styles.logoutButton} />
              </View>
            </View>

            <View style={styles.searchRow}>
              <FormField
                label="Città"
                placeholder="es. Firenze"
                value={city}
                onChangeText={setCity}
                style={styles.cityField}
                onSubmitEditing={() => runSearch()}
              />
              <PrimaryButton title="Cerca" onPress={() => runSearch()} loading={isSearching} style={styles.searchButton} />
            </View>

            <PrimaryButton
              title={coords ? '📍 Posizione aggiornata' : '📍 Cerca vicino a me'}
              variant="outline"
              onPress={handleUseLocation}
              loading={isLocating}
            />

            {coords ? (
              <View style={styles.radiusRow}>
                {RADIUS_OPTIONS_KM.map((km) => (
                  <Pressable
                    key={km}
                    onPress={() => handleRadiusChange(km)}
                    style={[styles.chip, radiusKm === km && styles.chipActive]}
                  >
                    <Text style={[styles.chipText, radiusKm === km && styles.chipTextActive]}>{km} km</Text>
                  </Pressable>
                ))}
              </View>
            ) : null}

            {error ? (
              <View style={styles.errorBox}>
                <Text style={styles.errorText}>{error}</Text>
              </View>
            ) : null}

            {isSearching ? <ActivityIndicator color={colors.primary} style={styles.spinner} /> : null}

            {!isSearching && hasSearched && shops.length === 0 ? (
              <Text style={styles.emptyText}>Nessun vivaio o fioraio trovato. Prova un'altra città o raggio.</Text>
            ) : null}
          </View>
        }
        renderItem={({ item }) => (
          <Pressable style={styles.card} onPress={() => router.push(`/shop/${item.id}`)}>
            <Text style={styles.cardName}>{item.name}</Text>
            <Text style={styles.cardAddress}>{item.address}</Text>
            <View style={styles.cardFooter}>
              <Text style={styles.cardPhone}>📞 {item.phone}</Text>
              {item.distance_km != null ? (
                <Text style={styles.cardDistance}>{item.distance_km.toFixed(1)} km</Text>
              ) : null}
            </View>
          </Pressable>
        )}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  listContent: { padding: spacing.lg, paddingBottom: spacing.xl },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: spacing.lg,
  },
  title: { fontSize: 20, fontWeight: '800', color: colors.text },
  subtitle: { fontSize: 14, color: colors.textMuted, marginTop: spacing.xs },
  headerActions: { alignItems: 'flex-end' },
  logoutButton: { marginTop: spacing.sm },
  searchRow: { flexDirection: 'row', gap: spacing.sm, alignItems: 'flex-start' },
  cityField: { flex: 1 },
  searchButton: { marginTop: spacing.md + 6, minWidth: 90 },
  radiusRow: { flexDirection: 'row', gap: spacing.xs, marginTop: spacing.sm, flexWrap: 'wrap' },
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
  errorBox: {
    backgroundColor: colors.errorBackground,
    borderRadius: 8,
    padding: spacing.sm,
    marginTop: spacing.md,
  },
  errorText: { color: colors.error },
  spinner: { marginTop: spacing.lg },
  emptyText: { textAlign: 'center', color: colors.textMuted, marginTop: spacing.lg },
  card: {
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.md,
    marginTop: spacing.md,
  },
  cardName: { fontSize: 16, fontWeight: '700', color: colors.text },
  cardAddress: { fontSize: 14, color: colors.textMuted, marginTop: spacing.xs },
  cardFooter: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginTop: spacing.sm,
  },
  cardPhone: { fontSize: 13, color: colors.text },
  cardDistance: { fontSize: 13, color: colors.primaryDark, fontWeight: '700' },
});
