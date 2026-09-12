import { StyleSheet, Switch, Text, TextInput, View } from 'react-native';
import { colors, radius, spacing } from '../theme';
import { WEEKDAY_SHORT } from '../utils/schedule';

// Editable list of 7 DaySchedule entries (mon..sun), each with a "closed"
// switch and two HH:MM text fields — used for both a shop's opening_hours
// and its pickup_window (see backend/app/schemas.py::DaySchedule).
export default function DayScheduleEditor({ label, value, onChange }) {
  function updateDay(day, patch) {
    onChange(value.map((slot) => (slot.day === day ? { ...slot, ...patch } : slot)));
  }

  function toggleClosed(day, closed) {
    updateDay(day, closed ? { closed: true, start: null, end: null } : { closed: false, start: '08:00', end: '19:00' });
  }

  return (
    <View style={styles.container}>
      <Text style={styles.label}>{label}</Text>
      {value.map((slot) => (
        <View key={slot.day} style={styles.row}>
          <Text style={styles.dayLabel}>{WEEKDAY_SHORT[slot.day]}</Text>
          <Switch
            value={!slot.closed}
            onValueChange={(open) => toggleClosed(slot.day, !open)}
            trackColor={{ true: colors.primary }}
          />
          {slot.closed ? (
            <Text style={styles.closedText}>Chiuso</Text>
          ) : (
            <View style={styles.times}>
              <TextInput
                style={styles.timeInput}
                value={slot.start ?? ''}
                onChangeText={(v) => updateDay(slot.day, { start: v })}
                placeholder="08:00"
                placeholderTextColor={colors.textMuted}
                maxLength={5}
              />
              <Text style={styles.dash}>–</Text>
              <TextInput
                style={styles.timeInput}
                value={slot.end ?? ''}
                onChangeText={(v) => updateDay(slot.day, { end: v })}
                placeholder="19:00"
                placeholderTextColor={colors.textMuted}
                maxLength={5}
              />
            </View>
          )}
        </View>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { marginBottom: spacing.md },
  label: { fontSize: 14, fontWeight: '600', color: colors.text, marginBottom: spacing.sm },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: spacing.xs,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
    gap: spacing.sm,
  },
  dayLabel: { width: 36, fontSize: 14, fontWeight: '600', color: colors.text },
  closedText: { flex: 1, color: colors.textMuted, fontStyle: 'italic' },
  times: { flex: 1, flexDirection: 'row', alignItems: 'center', gap: spacing.xs },
  timeInput: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.sm,
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
    fontSize: 14,
    color: colors.text,
    backgroundColor: colors.surface,
    width: 64,
    textAlign: 'center',
  },
  dash: { color: colors.textMuted },
});
