import { useRouter } from 'expo-router';
import { StyleSheet, Text } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import PrimaryButton from '../src/components/PrimaryButton';
import { useAuth } from '../src/context/AuthContext';
import { colors, spacing } from '../src/theme';

// Placeholder home screen for a logged-in customer. The real marketplace
// (città/zona/distanza, elenco negozi, box, carrello, pagamento, recensioni)
// is a separate feature — this just confirms the auth flow end-to-end.
export default function HomeCliente() {
  const router = useRouter();
  const { user, logout } = useAuth();

  async function handleLogout() {
    await logout();
    router.replace('/');
  }

  return (
    <SafeAreaView style={styles.container}>
      <Text style={styles.emoji}>🪴</Text>
      <Text style={styles.title}>Ciao, {user?.username}!</Text>
      <Text style={styles.subtitle}>{user?.email}</Text>
      <Text style={styles.body}>
        Presto qui potrai impostare città e zona per scoprire i vivai e i fiorai vicino a te.
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
  body: {
    marginTop: spacing.lg,
    fontSize: 15,
    color: colors.textMuted,
    textAlign: 'center',
  },
  logout: { marginTop: spacing.xl, minWidth: 160 },
});
