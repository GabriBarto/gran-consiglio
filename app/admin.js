import { Redirect, useRouter } from 'expo-router';
import { useCallback, useEffect, useState } from 'react';
import { ActivityIndicator, FlatList, Pressable, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { listShopsForReview, setShopLicenseStatus } from '../src/api/admin';
import PrimaryButton from '../src/components/PrimaryButton';
import { useAuth } from '../src/context/AuthContext';
import { colors, radius, spacing } from '../src/theme';

const FILTERS = [
  { key: undefined, label: 'Tutti' },
  { key: 'pending_review', label: 'In attesa' },
  { key: 'approved', label: 'Approvati' },
  { key: 'rejected', label: 'Rifiutati' },
];

const STATUS_LABEL = {
  pending_review: 'In attesa ⏳',
  approved: 'Approvato ✅',
  rejected: 'Rifiutato ❌',
};

// Admin-only queue to review vendor shop licenses (backend/app/routers/admin.py).
// Guarded below: anyone who isn't an admin is bounced back to "/".
export default function AdminPanel() {
  const router = useRouter();
  const { user, isLoading: isAuthLoading, logout } = useAuth();

  const [filter, setFilter] = useState(undefined);
  const [shops, setShops] = useState([]);
  const [counts, setCounts] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [busyShopId, setBusyShopId] = useState(null);

  const load = useCallback(async (statusFilter) => {
    setIsLoading(true);
    setError(null);
    try {
      // Counts always reflect the *whole* queue, not just the active filter,
      // so the summary strip stays meaningful regardless of which chip is
      // selected — only fetch the unfiltered list a second time when needed.
      const [filtered, all] = await Promise.all([
        listShopsForReview(statusFilter),
        statusFilter ? listShopsForReview() : Promise.resolve(null),
      ]);
      setShops(filtered);
      const forCounts = statusFilter ? all : filtered;
      setCounts({
        total: forCounts.length,
        pending_review: forCounts.filter((s) => s.license_status === 'pending_review').length,
        approved: forCounts.filter((s) => s.license_status === 'approved').length,
        rejected: forCounts.filter((s) => s.license_status === 'rejected').length,
      });
    } catch (err) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (user?.role === 'admin') load(filter);
  }, [filter, load, user?.role]);

  if (isAuthLoading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator color={colors.primary} size="large" />
      </View>
    );
  }
  if (!user || user.role !== 'admin') {
    return <Redirect href="/" />;
  }

  async function handleSetStatus(shopId, status) {
    setBusyShopId(shopId);
    try {
      await setShopLicenseStatus(shopId, status);
      await load(filter);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusyShopId(null);
    }
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
              <Text style={styles.title}>Pannello Admin 🛡️</Text>
              <PrimaryButton title="Esci" variant="outline" onPress={handleLogout} />
            </View>

            {counts ? (
              <View style={styles.countsRow}>
                <CountPill label="Totale" value={counts.total} />
                <CountPill label="In attesa" value={counts.pending_review} />
                <CountPill label="Approvati" value={counts.approved} />
                <CountPill label="Rifiutati" value={counts.rejected} />
              </View>
            ) : null}

            <View style={styles.filterRow}>
              {FILTERS.map((f) => (
                <Pressable
                  key={f.label}
                  onPress={() => setFilter(f.key)}
                  style={[styles.chip, filter === f.key && styles.chipActive]}
                >
                  <Text style={[styles.chipText, filter === f.key && styles.chipTextActive]}>{f.label}</Text>
                </Pressable>
              ))}
            </View>

            {error ? <Text style={styles.errorText}>{error}</Text> : null}
            {isLoading ? <ActivityIndicator color={colors.primary} style={styles.spinner} /> : null}
            {!isLoading && shops.length === 0 ? (
              <Text style={styles.emptyText}>Nessun negozio in questa categoria.</Text>
            ) : null}
          </View>
        }
        renderItem={({ item }) => (
          <View style={styles.card}>
            <Text style={styles.cardName}>{item.name}</Text>
            <Text style={styles.cardMeta}>
              {item.vendor_username} · {item.vendor_email}
            </Text>
            <Text style={styles.cardMeta}>
              {item.address} · 📞 {item.phone}
            </Text>
            <Text style={styles.cardStatus}>{STATUS_LABEL[item.license_status]}</Text>
            <View style={styles.actionsRow}>
              {item.license_status !== 'approved' ? (
                <PrimaryButton
                  title="Approva"
                  onPress={() => handleSetStatus(item.id, 'approved')}
                  loading={busyShopId === item.id}
                  style={styles.actionButton}
                />
              ) : null}
              {item.license_status !== 'rejected' ? (
                <PrimaryButton
                  title="Rifiuta"
                  variant="outline"
                  onPress={() => handleSetStatus(item.id, 'rejected')}
                  loading={busyShopId === item.id}
                  style={styles.actionButton}
                />
              ) : null}
              {item.license_status !== 'pending_review' ? (
                <PrimaryButton
                  title="Rimetti in attesa"
                  variant="outline"
                  onPress={() => handleSetStatus(item.id, 'pending_review')}
                  loading={busyShopId === item.id}
                  style={styles.actionButton}
                />
              ) : null}
            </View>
          </View>
        )}
      />
    </SafeAreaView>
  );
}

function CountPill({ label, value }) {
  return (
    <View style={styles.pill}>
      <Text style={styles.pillValue}>{value}</Text>
      <Text style={styles.pillLabel}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.background },
  listContent: { padding: spacing.lg, paddingBottom: spacing.xl },
  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: spacing.md },
  title: { fontSize: 20, fontWeight: '800', color: colors.text },
  countsRow: { flexDirection: 'row', gap: spacing.sm, marginBottom: spacing.md, flexWrap: 'wrap' },
  pill: {
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    alignItems: 'center',
    minWidth: 72,
  },
  pillValue: { fontSize: 18, fontWeight: '800', color: colors.primaryDark },
  pillLabel: { fontSize: 12, color: colors.textMuted },
  filterRow: { flexDirection: 'row', gap: spacing.xs, flexWrap: 'wrap', marginBottom: spacing.md },
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
  errorText: { color: colors.error, marginBottom: spacing.sm },
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
  cardMeta: { fontSize: 13, color: colors.textMuted, marginTop: spacing.xs },
  cardStatus: { fontSize: 14, fontWeight: '700', color: colors.text, marginTop: spacing.sm },
  actionsRow: { flexDirection: 'row', gap: spacing.sm, marginTop: spacing.md, flexWrap: 'wrap' },
  actionButton: { flexGrow: 1, minWidth: 100 },
});
