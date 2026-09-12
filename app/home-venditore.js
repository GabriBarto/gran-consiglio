import * as DocumentPicker from 'expo-document-picker';
import { useRouter } from 'expo-router';
import { useEffect, useState } from 'react';
import { ActivityIndicator, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { reuploadLicense } from '../src/api/auth';
import { createShop, getMyShop, updateMyShop } from '../src/api/shops';
import PrimaryButton from '../src/components/PrimaryButton';
import ShopForm from '../src/components/ShopForm';
import { useAuth } from '../src/context/AuthContext';
import { colors, radius, spacing } from '../src/theme';
import { formatSlot, todayWeekday, WEEKDAY_LABELS } from '../src/utils/schedule';

const LICENSE_LABEL = {
  pending_review: 'Licenza in fase di verifica ⏳',
  approved: 'Licenza verificata ✅',
  rejected: 'Licenza rifiutata ❌',
};

export default function HomeVenditore() {
  const router = useRouter();
  const { user, logout, refreshUser } = useAuth();

  const [shop, setShop] = useState(undefined); // undefined = not loaded yet, null = no shop yet
  const [isLoadingShop, setIsLoadingShop] = useState(false);
  const [shopError, setShopError] = useState(null);
  const [isEditing, setIsEditing] = useState(false);

  const [isPickingLicense, setIsPickingLicense] = useState(false);
  const [licenseError, setLicenseError] = useState(null);

  // A shop's own license_status (reviewed by the admin, see
  // backend/app/routers/admin.py) starts at pending_review the moment it's
  // created and is what actually shows up in the admin queue — it's
  // independent of the vendor account's license.status. So the vendor must
  // be able to create/edit their shop regardless of their account's license
  // state: gating this behind "approved" would mean no shop is ever created
  // for the admin to approve in the first place.
  useEffect(() => {
    setIsLoadingShop(true);
    setShopError(null);
    getMyShop()
      .then(setShop)
      .catch((err) => setShopError(err.message))
      .finally(() => setIsLoadingShop(false));
  }, []);

  async function handleLogout() {
    await logout();
    router.replace('/');
  }

  async function handleShopSubmit(payload) {
    const saved = shop ? await updateMyShop(payload) : await createShop(payload);
    setShop(saved);
    setIsEditing(false);
  }

  async function handleReuploadLicense() {
    setLicenseError(null);
    const result = await DocumentPicker.getDocumentAsync({
      type: ['application/pdf', 'image/*'],
      copyToCacheDirectory: true,
    });
    if (result.canceled) return;
    setIsPickingLicense(true);
    try {
      await reuploadLicense(result.assets[0]);
      await refreshUser();
    } catch (err) {
      setLicenseError(err.message);
    } finally {
      setIsPickingLicense(false);
    }
  }

  return (
    <SafeAreaView style={styles.container} edges={['top', 'left', 'right']}>
      <ScrollView contentContainerStyle={styles.content}>
        <View style={styles.header}>
          <View>
            <Text style={styles.title}>Bentornato, {user?.username}! 🏪</Text>
            <Text style={styles.subtitle}>{user?.email}</Text>
          </View>
          <PrimaryButton title="Esci" variant="outline" onPress={handleLogout} />
        </View>

        <View style={styles.statusBadge}>
          <Text style={styles.statusText}>
            {LICENSE_LABEL[user?.licenseStatus] ?? 'Stato licenza sconosciuto'}
          </Text>
        </View>

        {user?.licenseStatus !== 'approved' ? (
          <View style={[styles.card, styles.licenseCard]}>
            <Text style={styles.body}>
              {user?.licenseStatus === 'rejected'
                ? 'La licenza caricata non è stata accettata. Ricaricane una nuova per essere rivalutato — puoi comunque continuare a curare il profilo del tuo negozio nel frattempo.'
                : 'Il nostro team sta verificando il documento di licenza caricato in fase di registrazione. Nel frattempo puoi già impostare il tuo negozio qui sotto: sarà visibile ai clienti non appena la licenza sarà approvata.'}
            </Text>
            {user?.licenseStatus === 'rejected' ? (
              <PrimaryButton
                title="Ricarica documento licenza"
                onPress={handleReuploadLicense}
                loading={isPickingLicense}
                style={styles.reuploadButton}
              />
            ) : null}
            {licenseError ? <Text style={styles.errorText}>{licenseError}</Text> : null}
          </View>
        ) : null}

        <ShopSection
          shop={shop}
          isLoading={isLoadingShop}
          error={shopError}
          isEditing={isEditing}
          onEdit={() => setIsEditing(true)}
          onCancelEdit={() => setIsEditing(false)}
          onSubmit={handleShopSubmit}
        />
      </ScrollView>
    </SafeAreaView>
  );
}

function ShopSection({ shop, isLoading, error, isEditing, onEdit, onCancelEdit, onSubmit }) {
  if (isLoading) {
    return <ActivityIndicator color={colors.primary} style={{ marginTop: spacing.lg }} />;
  }
  if (error) {
    return <Text style={styles.errorText}>{error}</Text>;
  }

  if (!shop || isEditing) {
    return (
      <View style={styles.card}>
        <Text style={styles.cardTitle}>{shop ? 'Modifica il tuo negozio' : 'Crea il tuo negozio'}</Text>
        <ShopForm
          initialShop={shop ?? undefined}
          submitLabel={shop ? 'Salva modifiche' : 'Crea negozio'}
          onSubmit={onSubmit}
          onCancel={shop ? onCancelEdit : undefined}
        />
      </View>
    );
  }

  const today = todayWeekday();
  return (
    <View style={styles.card}>
      <Text style={styles.cardTitle}>{shop.name}</Text>
      <Text style={styles.body}>
        {shop.address}, {shop.city}
      </Text>
      <Text style={styles.body}>📞 {shop.phone}</Text>
      <Text style={styles.todayHours}>
        Oggi ({WEEKDAY_LABELS[today]}): apertura {formatSlot(shop.opening_hours.find((s) => s.day === today))} ·
        ritiro {formatSlot(shop.pickup_window.find((s) => s.day === today))}
      </Text>
      <PrimaryButton title="Modifica negozio" variant="outline" onPress={onEdit} style={styles.editButton} />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  content: { padding: spacing.lg, paddingBottom: spacing.xl },
  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: spacing.md },
  title: { fontSize: 20, fontWeight: '800', color: colors.text },
  subtitle: { fontSize: 14, color: colors.textMuted, marginTop: spacing.xs },
  statusBadge: {
    alignSelf: 'flex-start',
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.lg,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
    marginBottom: spacing.md,
  },
  statusText: { color: colors.text, fontWeight: '600' },
  licenseCard: { marginBottom: spacing.md },
  card: {
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.md,
  },
  cardTitle: { fontSize: 17, fontWeight: '700', color: colors.text, marginBottom: spacing.sm },
  body: { fontSize: 15, color: colors.textMuted, marginTop: spacing.xs },
  todayHours: { fontSize: 14, color: colors.primaryDark, fontWeight: '600', marginTop: spacing.sm },
  editButton: { marginTop: spacing.md },
  reuploadButton: { marginTop: spacing.md },
  errorText: { color: colors.error, marginTop: spacing.sm },
});
