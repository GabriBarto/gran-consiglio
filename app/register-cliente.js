import { useRouter } from 'expo-router';
import { useRef, useState } from 'react';
import { KeyboardAvoidingView, Platform, ScrollView, StyleSheet, Text, View } from 'react-native';
import FormField from '../src/components/FormField';
import PrimaryButton from '../src/components/PrimaryButton';
import { useAuth } from '../src/context/AuthContext';
import { colors, spacing } from '../src/theme';
import { isUsernameTaken } from '../src/api/auth';
import { isValidEmail, validatePassword, validateUsername } from '../src/validation';

export default function RegisterCliente() {
  const router = useRouter();
  const { registerCustomer } = useAuth();

  const [form, setForm] = useState({ email: '', password: '', confirmPassword: '', username: '' });
  const [errors, setErrors] = useState({});
  const [formError, setFormError] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  // Guards against a stale "già in uso" result if the user keeps typing.
  const usernameCheckId = useRef(0);

  function setField(key, value) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  async function validate() {
    const next = {};
    if (!isValidEmail(form.email)) next.email = 'Inserisci un indirizzo email valido.';

    const usernameError = validateUsername(form.username);
    if (usernameError) next.username = usernameError;

    const passwordError = validatePassword(form.password);
    if (passwordError) next.password = passwordError;

    if (form.confirmPassword !== form.password) {
      next.confirmPassword = 'Le password non coincidono.';
    }

    if (!usernameError && (await isUsernameTaken(form.username))) {
      next.username = 'Questo nome utente è già in uso, scegline un altro.';
    }

    setErrors(next);
    return Object.keys(next).length === 0;
  }

  async function handleSubmit() {
    setFormError(null);
    const checkId = ++usernameCheckId.current;
    const isValid = await validate();
    if (checkId !== usernameCheckId.current || !isValid) return;

    setIsSubmitting(true);
    try {
      await registerCustomer(form);
      router.replace('/home-cliente');
    } catch (err) {
      setFormError(err.message);
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <KeyboardAvoidingView style={styles.flex} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <ScrollView contentContainerStyle={styles.container} keyboardShouldPersistTaps="handled">
        <Text style={styles.title}>Crea il tuo account cliente</Text>
        <Text style={styles.subtitle}>
          Scopri box di piante salvate vicino a te a un prezzo speciale.
        </Text>

        <FormField
          label="Nome utente"
          placeholder="es. mario.rossi"
          value={form.username}
          onChangeText={(v) => setField('username', v)}
          error={errors.username}
        />
        <FormField
          label="Email"
          placeholder="mario.rossi@email.com"
          keyboardType="email-address"
          value={form.email}
          onChangeText={(v) => setField('email', v)}
          error={errors.email}
        />
        <FormField
          label="Password"
          placeholder="Almeno 8 caratteri, con lettere e numeri"
          secureTextEntry
          value={form.password}
          onChangeText={(v) => setField('password', v)}
          error={errors.password}
        />
        <FormField
          label="Conferma password"
          placeholder="Ripeti la password"
          secureTextEntry
          value={form.confirmPassword}
          onChangeText={(v) => setField('confirmPassword', v)}
          error={errors.confirmPassword}
        />

        {formError ? (
          <View style={styles.formErrorBox}>
            <Text style={styles.formErrorText}>{formError}</Text>
          </View>
        ) : null}

        <PrimaryButton title="Registrati" onPress={handleSubmit} loading={isSubmitting} />
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
    fontSize: 22,
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
});
