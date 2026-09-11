import { useRouter } from 'expo-router';
import { StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import PrimaryButton from '../src/components/PrimaryButton';
import { useAuth } from '../src/context/AuthContext';
import { colors, radius, spacing } from '../src/theme';

const LICENSE_LABEL = {
  pending_review: 'Licenza in fase di verifica ⏳',
  approved: 'Licenza verificata ✅',
  rejected: 'Licenza rifiutata ❌',
};

// Placeholder dashboard for a logged-in vendor. Managing box listings,
// daily quantities, and order notifications is a separate feature — this
// just confirms the auth + license-upload flow end-to-end.
export default function HomeVenditore() {
  const router = useRouter();
  const { user, logout } = useAuth();

  async function handleLogout() {
    await logout();
    router.replace('/');
  }

  return (
    <SafeAreaView style={styles.container}>
      <Text style={styles.emoji}>🏪</Text>
      <Text style={styles.title}>Bentornato, {user?.username}!</Text>
      <Text style={styles.subtitle}>{user?.email}</Text>

      <View style={styles.statusBadge}>
        <Text style={styles.statusText}>
          {LICENSE_LABEL[user?.licenseStatus] ?? 'Stato licenza sconosciuto'}
        </Text>
      </View>

      <Text style={styles.body}>
        Presto da qui potrai aggiungere le tue box (descrizione e prezzo), aggiornare le quantità
        disponibili ogni giorno e ricevere una notifica quando arriva un ordine.
      </Text>

      <PrimaryButton title="Esci" variant="outline" onPress={handleLogout} style={styles.logout} />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
    alignItems: 'center',
    justifyContent: 'center',
    padding: spacing.lg,
  },
  emoji: { fontSize: 56, marginBottom: spacing.md },
  title: { fontSize: 22, fontWeight: '800', color: colors.text },
  subtitle: { fontSize: 14, color: colors.textMuted, marginTop: spacing.xs },
  statusBadge: {
    marginTop: spacing.md,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.lg,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
  },
  statusText: { color: colors.text, fontWeight: '600' },
  body: {
    marginTop: spacing.lg,
    fontSize: 15,
    color: colors.textMuted,
    textAlign: 'center',
  },
  logout: { marginTop: spacing.xl, minWidth: 160 },
});
