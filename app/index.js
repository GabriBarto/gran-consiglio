import { Redirect, Link } from 'expo-router';
import { ActivityIndicator, StyleSheet, Text, View } from 'react-native';
import PrimaryButton from '../src/components/PrimaryButton';
import { useAuth } from '../src/context/AuthContext';
import { colors, spacing } from '../src/theme';

export default function Welcome() {
  const { user, isLoading } = useAuth();

  if (isLoading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator color={colors.primary} size="large" />
      </View>
    );
  }

  // Already logged in: skip straight to the right home screen.
  if (user?.role === 'customer') return <Redirect href="/home-cliente" />;
  if (user?.role === 'vendor') return <Redirect href="/home-venditore" />;

  return (
    <View style={styles.container}>
      <View style={styles.hero}>
        <Text style={styles.emoji}>🌱</Text>
        <Text style={styles.title}>tooGood</Text>
        <Text style={styles.subtitle}>
          Salva le piante in eccesso di vivai e fiorai vicino a te, a un prezzo speciale.
        </Text>
      </View>

      <View style={styles.actions}>
        <Link href="/login" asChild>
          <PrimaryButton title="Accedi" />
        </Link>

        <Text style={styles.sectionLabel}>Non hai un account?</Text>

        <Link href="/register-cliente" asChild>
          <PrimaryButton title="Registrati come cliente" variant="outline" />
        </Link>
        <Link href="/register-venditore" asChild>
          <PrimaryButton title="Registrati come venditore" variant="outline" style={styles.gap} />
        </Link>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
    justifyContent: 'space-between',
    padding: spacing.lg,
    paddingTop: spacing.xl * 2,
    paddingBottom: spacing.xl,
  },
  center: {
    flex: 1,
    backgroundColor: colors.background,
    alignItems: 'center',
    justifyContent: 'center',
  },
  hero: {
    alignItems: 'center',
  },
  emoji: {
    fontSize: 56,
    marginBottom: spacing.md,
  },
  title: {
    fontSize: 32,
    fontWeight: '800',
    color: colors.primaryDark,
  },
  subtitle: {
    marginTop: spacing.sm,
    fontSize: 16,
    color: colors.textMuted,
    textAlign: 'center',
    paddingHorizontal: spacing.md,
  },
  actions: {
    gap: spacing.sm,
  },
  sectionLabel: {
    textAlign: 'center',
    color: colors.textMuted,
    marginTop: spacing.md,
    marginBottom: spacing.xs,
  },
  gap: {
    marginTop: spacing.sm,
  },
});
