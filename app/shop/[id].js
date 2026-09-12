import { useLocalSearchParams } from 'expo-router';
import { useEffect, useState } from 'react';
import { ActivityIndicator, Linking, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { getShop } from '../../src/api/shops';
import PrimaryButton from '../../src/components/PrimaryButton';
import { colors, radius, spacing } from '../../src/theme';
import { formatSlot, todayWeekday, WEEKDAY_LABELS, WEEKDAYS } from '../../src/utils/schedule';

export default function ShopDetail() {
  const { id } = useLocalSearchParams();
  const [shop, setShop] = useState(null);
  const [error, setError] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const today = todayWeekday();

  useEffect(() => {
    let cancelled = false;
    setIsLoading(true);
    getShop(id)
      .then((result) => {
        if (!cancelled) setShop(result);
      })
      .catch((err) => {
        if (!cancelled) setError(err.message);
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [id]);

  if (isLoading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator color={colors.primary} size="large" />
      </View>
    );
  }

  if (error || !shop) {
    return (
      <View style={styles.center}>
        <Text style={styles.errorText}>{error ?? 'Negozio non trovato.'}</Text>
      </View>
    );
  }

  return (
    <SafeAreaView style={styles.container} edges={['left', 'right', 'bottom']}>
      <ScrollView contentContainerStyle={styles.content}>
        <Text style={styles.name}>{shop.name}</Text>
        <Text style={styles.address}>
          {shop.address}, {shop.city}
        </Text>

        <PrimaryButton
          title={`📞 Chiama ${shop.phone}`}
          variant="outline"
          onPress={() => Linking.openURL(`tel:${shop.phone}`)}
          style={styles.callButton}
        />

        <Section title="Orari di apertura" schedule={shop.opening_hours} today={today} />
        <Section title="Fascia di ritiro" schedule={shop.pickup_window} today={today} />
      </ScrollView>
    </SafeAreaView>
  );
}

function Section({ title, schedule, today }) {
  const byDay = Object.fromEntries(schedule.map((slot) => [slot.day, slot]));
  return (
    <View style={styles.section}>
      <Text style={styles.sectionTitle}>{title}</Text>
      {WEEKDAYS.map((day) => (
        <View key={day} style={[styles.row, day === today && styles.rowToday]}>
          <Text style={[styles.dayLabel, day === today && styles.todayText]}>{WEEKDAY_LABELS[day]}</Text>
          <Text style={[styles.slotText, day === today && styles.todayText]}>{formatSlot(byDay[day])}</Text>
        </View>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.background },
  content: { padding: spacing.lg },
  name: { fontSize: 24, fontWeight: '800', color: colors.text },
  address: { fontSize: 15, color: colors.textMuted, marginTop: spacing.xs },
  callButton: { marginTop: spacing.md, marginBottom: spacing.lg },
  errorText: { color: colors.error, padding: spacing.lg, textAlign: 'center' },
  section: {
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.md,
    marginBottom: spacing.md,
  },
  sectionTitle: { fontSize: 15, fontWeight: '700', color: colors.text, marginBottom: spacing.sm },
  row: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: spacing.xs,
  },
  rowToday: { backgroundColor: colors.background, borderRadius: radius.sm, paddingHorizontal: spacing.xs },
  dayLabel: { color: colors.text },
  slotText: { color: colors.textMuted },
  todayText: { fontWeight: '700', color: colors.primaryDark },
});
