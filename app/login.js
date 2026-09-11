import { Link, useRouter } from 'expo-router';
import { useState } from 'react';
import { KeyboardAvoidingView, Platform, ScrollView, StyleSheet, Text, View } from 'react-native';
import FormField from '../src/components/FormField';
import PrimaryButton from '../src/components/PrimaryButton';
import { useAuth } from '../src/context/AuthContext';
import { colors, spacing } from '../src/theme';
import { isValidEmail } from '../src/validation';

export default function Login() {
  const router = useRouter();
  const { login } = useAuth();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [errors, setErrors] = useState({});
  const [formError, setFormError] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  function validate() {
    const next = {};
    if (!isValidEmail(email)) next.email = 'Inserisci un indirizzo email valido.';
    if (!password) next.password = 'Inserisci la tua password.';
    setErrors(next);
    return Object.keys(next).length === 0;
  }

  async function handleSubmit() {
    setFormError(null);
    if (!validate()) return;

    setIsSubmitting(true);
    try {
      const user = await login({ email, password });
      router.replace(user.role === 'vendor' ? '/home-venditore' : '/home-cliente');
    } catch (err) {
      setFormError(err.message);
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <KeyboardAvoidingView
      style={styles.flex}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
    >
      <ScrollView contentContainerStyle={styles.container} keyboardShouldPersistTaps="handled">
        <Text style={styles.title}>Bentornato 🌿</Text>
        <Text style={styles.subtitle}>Accedi al tuo account cliente o venditore.</Text>

        <FormField
          label="Email"
          placeholder="mario.rossi@email.com"
          keyboardType="email-address"
          value={email}
          onChangeText={setEmail}
          error={errors.email}
        />
        <FormField
          label="Password"
          placeholder="La tua password"
          secureTextEntry
          value={password}
          onChangeText={setPassword}
          error={errors.password}
        />

        {formError ? (
          <View style={styles.formErrorBox}>
            <Text style={styles.formErrorText}>{formError}</Text>
          </View>
        ) : null}

        <PrimaryButton title="Accedi" onPress={handleSubmit} loading={isSubmitting} />

        <View style={styles.footer}>
          <Text style={styles.footerText}>Non hai un account?</Text>
          <Link href="/register-cliente" style={styles.link}>
            Registrati come cliente
          </Link>
          <Link href="/register-venditore" style={styles.link}>
            Registrati come venditore
          </Link>
        </View>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  container: {
    flexGrow: 1,
    padding: spacing.lg,
    backgroundColor: colors.background,
  },
  title: {
    fontSize: 24,
    fontWeight: '800',
    color: colors.text,
    marginBottom: spacing.xs,
  },
  subtitle: {
    fontSize: 15,
    color: colors.textMuted,
    marginBottom: spacing.lg,
  },
  formErrorBox: {
    backgroundColor: colors.errorBackground,
    borderRadius: 8,
    padding: spacing.sm,
    marginBottom: spacing.md,
  },
  formErrorText: {
    color: colors.error,
  },
  footer: {
    marginTop: spacing.xl,
    alignItems: 'center',
    gap: spacing.xs,
  },
  footerText: {
    color: colors.textMuted,
    marginBottom: spacing.xs,
  },
  link: {
    color: colors.primary,
    fontWeight: '600',
  },
});
