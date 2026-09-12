import * as DocumentPicker from 'expo-document-picker';
import { useRouter } from 'expo-router';
import { useState } from 'react';
import { KeyboardAvoidingView, Platform, ScrollView, StyleSheet, Text, View } from 'react-native';
import FormField from '../src/components/FormField';
import PrimaryButton from '../src/components/PrimaryButton';
import { useAuth } from '../src/context/AuthContext';
import { colors, radius, spacing } from '../src/theme';
import { isValidEmail, isValidPhone, validatePassword, validateUsername } from '../src/validation';

export default function RegisterVenditore() {
  const router = useRouter();
  const { registerVendor } = useAuth();

  const [form, setForm] = useState({
    email: '',
    password: '',
    confirmPassword: '',
    username: '',
    phone: '',
    shopAddress: '',
  });
  const [license, setLicense] = useState(null);
  const [errors, setErrors] = useState({});
  const [formError, setFormError] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  function setField(key, value) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  async function handlePickLicense() {
    const result = await DocumentPicker.getDocumentAsync({
      type: ['application/pdf', 'image/*'],
      copyToCacheDirectory: true,
    });
    if (result.canceled) return;
    setLicense(result.assets[0]);
    setErrors((prev) => ({ ...prev, license: undefined }));
  }

  // Only format/consistency checks happen client-side; email/username
  // uniqueness is enforced server-side (no "check availability" endpoint,
  // by design) — a duplicate surfaces as a 409 in formError on submit.
  function validate() {
    const next = {};
    if (!isValidEmail(form.email)) next.email = 'Inserisci un indirizzo email valido.';

    const usernameError = validateUsername(form.username);
    if (usernameError) next.username = usernameError;

    const passwordError = validatePassword(form.password);
    if (passwordError) next.password = passwordError;

    if (form.confirmPassword !== form.password) {
      next.confirmPassword = 'Le password non coincidono.';
    }

    if (!isValidPhone(form.phone)) {
      next.phone = 'Inserisci un recapito telefonico valido.';
    }

    if (!form.shopAddress.trim()) {
      next.shopAddress = "Inserisci l'indirizzo del tuo negozio/vivaio.";
    }

    if (!license) {
      next.license = 'Carica un documento della licenza di vendita.';
    }

    setErrors(next);
    return Object.keys(next).length === 0;
  }

  async function handleSubmit() {
    setFormError(null);
    if (!validate()) return;

    setIsSubmitting(true);
    try {
      await registerVendor({ ...form, license });
      router.replace('/home-venditore');
    } catch (err) {
      setFormError(err.message);
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <KeyboardAvoidingView style={styles.flex} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <ScrollView contentContainerStyle={styles.container} keyboardShouldPersistTaps="handled">
        <Text style={styles.title}>Registra il tuo negozio</Text>
        <Text style={styles.subtitle}>
          Vendi le piante in eccesso ai clienti della tua zona. Il tuo account sarà attivo dopo la
          verifica della licenza di vendita.
        </Text>

        <FormField
          label="Nome utente (consigliato: nome del negozio)"
          placeholder="es. Vivaio Rossi"
          value={form.username}
          onChangeText={(v) => setField('username', v)}
          error={errors.username}
        />
        <FormField
          label="Email"
          placeholder="negozio@email.com"
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
        <FormField
          label="Recapito telefonico"
          placeholder="+39 333 1234567"
          keyboardType="phone-pad"
          value={form.phone}
          onChangeText={(v) => setField('phone', v)}
          error={errors.phone}
        />
        <FormField
          label="Indirizzo del negozio"
          placeholder="Via, città, CAP"
          value={form.shopAddress}
          onChangeText={(v) => setField('shopAddress', v)}
          error={errors.shopAddress}
        />

        <View style={styles.licenseSection}>
          <Text style={styles.label}>Licenza di vendita</Text>
          <PrimaryButton
            title={license ? 'Cambia documento' : 'Carica documento (PDF o immagine)'}
            variant="outline"
            onPress={handlePickLicense}
          />
          {license ? <Text style={styles.licenseName}>📎 {license.name}</Text> : null}
          {errors.license ? <Text style={styles.error}>{errors.license}</Text> : null}
          <Text style={styles.hint}>
            Il documento verrà controllato dal nostro team prima che tu possa iniziare a vendere.
          </Text>
        </View>

        {formError ? (
          <View style={styles.formErrorBox}>
            <Text style={styles.formErrorText}>{formError}</Text>
          </View>
        ) : null}

        <PrimaryButton title="Registrati come venditore" onPress={handleSubmit} loading={isSubmitting} />
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
  label: {
    fontSize: 14,
    fontWeight: '600',
    color: colors.text,
    marginBottom: spacing.xs,
  },
  licenseSection: {
    marginBottom: spacing.md,
    padding: spacing.md,
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
  },
  licenseName: {
    marginTop: spacing.sm,
    color: colors.text,
  },
  hint: {
    marginTop: spacing.sm,
    fontSize: 13,
    color: colors.textMuted,
  },
  error: {
    color: colors.error,
    fontSize: 13,
    marginTop: spacing.xs,
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
