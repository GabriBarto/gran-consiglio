import { useEffect, useState } from 'react';
import { ActivityIndicator, FlatList, Pressable, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { listNotifications, markAllNotificationsRead, markNotificationRead } from '../src/api/notifications';
import PrimaryButton from '../src/components/PrimaryButton';
import { colors, radius, spacing } from '../src/theme';

const TYPE_LABEL = {
  orderConfirmed: 'Pagamento confermato 💳',
  pickupReminder: 'Pronto per il ritiro 📦',
  reviewRequest: 'Lascia una recensione ⭐',
  boxAvailable: 'Nuova box disponibile 🎁',
  allergenFlagged: 'Allergene segnalato ⚠️',
  other: 'Notifica 🔔',
};

// Storico notifiche in-app (backend/app/routers/notifications.py) —
// popolato dalla macchina a stati degli ordini (backend/app/order_events.py):
// nuovo ordine (venditore), pagamento/pronto per il ritiro/ritirato/
// annullato/scaduto (cliente).
export default function Notifications() {
  const [notifications, setNotifications] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [markingId, setMarkingId] = useState(null);
  const [isMarkingAll, setIsMarkingAll] = useState(false);

  useEffect(() => {
    load();
  }, []);

  async function load() {
    setIsLoading(true);
    setError(null);
    try {
      setNotifications(await listNotifications());
    } catch (err) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  }

  async function handleMarkRead(notification) {
    if (notification.is_read) return;
    setMarkingId(notification.id);
    try {
      const updated = await markNotificationRead(notification.id);
      setNotifications((prev) => prev.map((n) => (n.id === updated.id ? updated : n)));
    } catch (err) {
      setError(err.message);
    } finally {
      setMarkingId(null);
    }
  }

  async function handleMarkAllRead() {
    setIsMarkingAll(true);
    try {
      await markAllNotificationsRead();
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setIsMarkingAll(false);
    }
  }

  const hasUnread = notifications.some((n) => !n.is_read);

  return (
    <SafeAreaView style={styles.container} edges={['left', 'right', 'bottom']}>
      <FlatList
        data={notifications}
        keyExtractor={(item) => item.id}
        contentContainerStyle={styles.content}
        ListHeaderComponent={
          <View>
            {hasUnread ? (
              <PrimaryButton
                title="Segna tutte come lette"
                variant="outline"
                loading={isMarkingAll}
                onPress={handleMarkAllRead}
                style={styles.markAllButton}
              />
            ) : null}
            {isLoading ? <ActivityIndicator color={colors.primary} style={styles.spinner} /> : null}
            {error ? <Text style={styles.errorText}>{error}</Text> : null}
            {!isLoading && notifications.length === 0 ? (
              <Text style={styles.emptyText}>Nessuna notifica per ora.</Text>
            ) : null}
          </View>
        }
        renderItem={({ item }) => (
          <Pressable
            onPress={() => handleMarkRead(item)}
            disabled={item.is_read || markingId === item.id}
            style={[styles.card, !item.is_read && styles.cardUnread]}
          >
            <View style={styles.cardHeader}>
              <Text style={styles.type}>{TYPE_LABEL[item.type] ?? item.type}</Text>
              {!item.is_read ? <View style={styles.unreadDot} /> : null}
            </View>
            <Text style={styles.text}>{item.text}</Text>
            <Text style={styles.date}>{new Date(item.date).toLocaleString()}</Text>
          </Pressable>
        )}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  content: { padding: spacing.lg, paddingBottom: spacing.xl },
  markAllButton: { marginBottom: spacing.md },
  spinner: { marginTop: spacing.lg },
  errorText: { color: colors.error, marginBottom: spacing.md },
  emptyText: { color: colors.textMuted, textAlign: 'center', marginTop: spacing.lg },
  card: {
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.md,
    marginBottom: spacing.md,
  },
  cardUnread: { borderColor: colors.primary },
  cardHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  type: { fontSize: 15, fontWeight: '700', color: colors.text, flexShrink: 1 },
  unreadDot: { width: 10, height: 10, borderRadius: 5, backgroundColor: colors.primary, marginLeft: spacing.sm },
  text: { fontSize: 14, color: colors.textMuted, marginTop: spacing.xs },
  date: { fontSize: 12, color: colors.textMuted, marginTop: spacing.sm },
});
