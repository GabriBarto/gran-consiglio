import { useEffect, useState } from 'react';
import { ActivityIndicator, FlatList, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { cancelMyOrder, listMyOrders } from '../src/api/orders';
import PrimaryButton from '../src/components/PrimaryButton';
import { colors, radius, spacing } from '../src/theme';

const STATE_LABEL = {
  booked: 'Prenotato ⏳',
  pickedUp: 'Ritirato ✅',
  cancelled: 'Annullato ❌',
  expired: 'Scaduto ⌛',
};

// Customer's own booking history (backend/app/routers/orders.py) — reached
// from the "Prenota e ritira" confirmation on a shop's page, or directly.
export default function MyOrders() {
  const [orders, setOrders] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [cancellingId, setCancellingId] = useState(null);

  useEffect(() => {
    load();
  }, []);

  async function load() {
    setIsLoading(true);
    setError(null);
    try {
      setOrders(await listMyOrders());
    } catch (err) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  }

  async function handleCancel(order) {
    setCancellingId(order.id);
    try {
      await cancelMyOrder(order.id);
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setCancellingId(null);
    }
  }

  return (
    <SafeAreaView style={styles.container} edges={['left', 'right', 'bottom']}>
      <FlatList
        data={orders}
        keyExtractor={(item) => item.id}
        contentContainerStyle={styles.content}
        ListHeaderComponent={
          <View>
            {isLoading ? <ActivityIndicator color={colors.primary} style={styles.spinner} /> : null}
            {error ? <Text style={styles.errorText}>{error}</Text> : null}
            {!isLoading && orders.length === 0 ? (
              <Text style={styles.emptyText}>Non hai ancora nessuna prenotazione.</Text>
            ) : null}
          </View>
        }
        renderItem={({ item }) => (
          <View style={styles.card}>
            <View style={styles.cardHeader}>
              <Text style={styles.shopName}>{item.shop_name}</Text>
              <Text style={styles.stateBadge}>{STATE_LABEL[item.state] ?? item.state}</Text>
            </View>
            {item.items.map((line) => (
              <Text key={line.box_id} style={styles.itemLine}>
                {line.quantity}× {line.box_name} — € {line.subtotal.toFixed(2)}
              </Text>
            ))}
            <Text style={styles.meta}>Ritiro {item.pickup_window}</Text>
            <Text style={styles.meta}>Prenotato il {new Date(item.order_date).toLocaleString()}</Text>
            <Text style={styles.total}>Totale € {item.total_price.toFixed(2)}</Text>
            {item.state === 'booked' ? (
              <PrimaryButton
                title="Annulla prenotazione"
                variant="outline"
                loading={cancellingId === item.id}
                onPress={() => handleCancel(item)}
                style={styles.cancelButton}
              />
            ) : null}
          </View>
        )}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  content: { padding: spacing.lg, paddingBottom: spacing.xl },
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
  cardHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start' },
  shopName: { fontSize: 16, fontWeight: '700', color: colors.text, flexShrink: 1 },
  stateBadge: { fontSize: 13, fontWeight: '700', color: colors.primaryDark },
  itemLine: { fontSize: 14, color: colors.textMuted, marginTop: spacing.xs },
  meta: { fontSize: 13, color: colors.textMuted, marginTop: spacing.xs },
  total: { fontSize: 15, fontWeight: '800', color: colors.text, marginTop: spacing.sm },
  cancelButton: { marginTop: spacing.md },
});
