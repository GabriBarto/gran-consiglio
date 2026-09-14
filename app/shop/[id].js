import { useLocalSearchParams, useRouter } from 'expo-router';
import { useEffect, useState } from 'react';
import { ActivityIndicator, Linking, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { addCartItem, checkoutCart, getCart, removeCartItem, setCartItemQuantity } from '../../src/api/cart';
import { listShopBoxes } from '../../src/api/boxes';
import { getShop } from '../../src/api/shops';
import { colors, radius, spacing } from '../../src/theme';
import PrimaryButton from '../../src/components/PrimaryButton';

export default function ShopDetail() {
  const router = useRouter();
  const { id } = useLocalSearchParams();
  const [shop, setShop] = useState(null);
  const [error, setError] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  const [boxes, setBoxes] = useState([]);
  const [isLoadingBoxes, setIsLoadingBoxes] = useState(true);
  const [boxesError, setBoxesError] = useState(null);

  const [cart, setCart] = useState(null);
  const [cartError, setCartError] = useState(null);
  const [busyBoxId, setBusyBoxId] = useState(null);

  const [isCheckingOut, setIsCheckingOut] = useState(false);
  const [checkoutError, setCheckoutError] = useState(null);
  const [bookedOrder, setBookedOrder] = useState(null);

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

    setIsLoadingBoxes(true);
    listShopBoxes(id)
      .then((result) => {
        if (!cancelled) setBoxes(result);
      })
      .catch((err) => {
        if (!cancelled) setBoxesError(err.message);
      })
      .finally(() => {
        if (!cancelled) setIsLoadingBoxes(false);
      });

    getCart(id)
      .then((result) => {
        if (!cancelled) setCart(result);
      })
      .catch((err) => {
        if (!cancelled) setCartError(err.message);
      });

    return () => {
      cancelled = true;
    };
  }, [id]);

  function quantityInCart(boxId) {
    return cart?.items.find((item) => item.box_id === boxId)?.quantity ?? 0;
  }

  async function refreshAvailability() {
    try {
      setBoxes(await listShopBoxes(id));
    } catch {
      // Non-fatal: the cart/checkout result is still shown correctly even
      // if this background refresh fails.
    }
  }

  async function handleAddToCart(box) {
    setBusyBoxId(box.id);
    setCartError(null);
    try {
      setCart(await addCartItem(id, box.id, 1));
    } catch (err) {
      setCartError(err.message);
    } finally {
      setBusyBoxId(null);
    }
  }

  async function handleChangeQuantity(box, nextQuantity) {
    setBusyBoxId(box.id);
    setCartError(null);
    try {
      setCart(nextQuantity <= 0 ? await removeCartItem(id, box.id) : await setCartItemQuantity(id, box.id, nextQuantity));
    } catch (err) {
      setCartError(err.message);
    } finally {
      setBusyBoxId(null);
    }
  }

  async function handleCheckout() {
    setIsCheckingOut(true);
    setCheckoutError(null);
    try {
      const order = await checkoutCart(id);
      setBookedOrder(order);
      setCart(await getCart(id));
      await refreshAvailability();
    } catch (err) {
      setCheckoutError(err.message);
    } finally {
      setIsCheckingOut(false);
    }
  }

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
        <Text style={styles.address}>{shop.address}</Text>

        <PrimaryButton
          title={`📞 Chiama ${shop.phone}`}
          variant="outline"
          onPress={() => Linking.openURL(`tel:${shop.phone}`)}
          style={styles.callButton}
        />

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Orari</Text>
          <Row label="Apertura" value={shop.opening_time} />
          <Row label="Ritiro box per il cliente" value={`${shop.pickup_window_start}–${shop.pickup_window_end}`} />
        </View>

        {bookedOrder ? (
          <View style={styles.confirmationCard}>
            <Text style={styles.confirmationTitle}>Prenotazione confermata! 🎉</Text>
            <Text style={styles.confirmationBody}>
              Ritira tra le {bookedOrder.pickup_window.replace('-', ' e le ')} — totale € {bookedOrder.total_price.toFixed(2)}.
            </Text>
            <PrimaryButton
              title="Vai a I miei ordini"
              variant="outline"
              onPress={() => router.push('/orders')}
              style={styles.confirmationButton}
            />
          </View>
        ) : null}

        <Text style={styles.boxesTitle}>Box disponibili 📦</Text>
        {isLoadingBoxes ? <ActivityIndicator color={colors.primary} style={styles.boxesSpinner} /> : null}
        {boxesError ? <Text style={styles.errorText}>{boxesError}</Text> : null}
        {!isLoadingBoxes && !boxesError && boxes.length === 0 ? (
          <Text style={styles.emptyText}>Questo negozio non ha box disponibili al momento.</Text>
        ) : null}
        {boxes.map((box) => {
          const inCart = quantityInCart(box.id);
          const isBusy = busyBoxId === box.id;
          return (
            <View key={box.id} style={styles.boxCard}>
              <View style={styles.boxCardHeader}>
                <Text style={styles.boxName}>{box.name}</Text>
                <Text style={styles.boxPrice}>€ {box.price.toFixed(2)}</Text>
              </View>
              <Text style={styles.boxDescription}>{box.description}</Text>
              <Text style={styles.boxMeta}>
                {box.category} · Allergeni: {box.allergens}
              </Text>
              <Text style={styles.boxMeta}>
                Ritiro {box.pickup_window_start}–{box.pickup_window_end} · Scade il{' '}
                {new Date(box.expire_at).toLocaleString()}
              </Text>
              <Text style={[styles.boxAvailability, box.available === 0 && styles.boxSoldOut]}>
                {box.available > 0 ? `${box.available} disponibili` : 'Esaurita'}
              </Text>

              {box.available === 0 && inCart === 0 ? null : inCart === 0 ? (
                <PrimaryButton
                  title="+ Aggiungi al carrello"
                  onPress={() => handleAddToCart(box)}
                  loading={isBusy}
                  style={styles.addButton}
                />
              ) : (
                <View style={styles.quantityRow}>
                  <PrimaryButton
                    title="−"
                    variant="outline"
                    onPress={() => handleChangeQuantity(box, inCart - 1)}
                    loading={isBusy}
                    style={styles.quantityButton}
                  />
                  <Text style={styles.quantityText}>{inCart} nel carrello</Text>
                  <PrimaryButton
                    title="+"
                    variant="outline"
                    disabled={inCart >= box.available}
                    onPress={() => handleChangeQuantity(box, inCart + 1)}
                    loading={isBusy}
                    style={styles.quantityButton}
                  />
                </View>
              )}
            </View>
          );
        })}

        {cartError ? <Text style={styles.errorText}>{cartError}</Text> : null}

        {cart && cart.items.length > 0 ? (
          <View style={styles.cartSummary}>
            <Text style={styles.sectionTitle}>Il tuo carrello</Text>
            {cart.items.map((item) => (
              <View key={item.box_id} style={styles.cartRow}>
                <Text style={styles.cartRowText}>
                  {item.quantity}× {item.box_name}
                </Text>
                <Text style={styles.cartRowText}>€ {item.subtotal.toFixed(2)}</Text>
              </View>
            ))}
            <View style={styles.cartTotalRow}>
              <Text style={styles.cartTotalLabel}>Totale</Text>
              <Text style={styles.cartTotalValue}>€ {cart.total_price.toFixed(2)}</Text>
            </View>
            {checkoutError ? <Text style={styles.errorText}>{checkoutError}</Text> : null}
            <PrimaryButton
              title="Prenota e ritira"
              onPress={handleCheckout}
              loading={isCheckingOut}
              style={styles.checkoutButton}
            />
          </View>
        ) : null}
      </ScrollView>
    </SafeAreaView>
  );
}

function Row({ label, value }) {
  return (
    <View style={styles.row}>
      <Text style={styles.rowLabel}>{label}</Text>
      <Text style={styles.rowValue}>{value}</Text>
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
  errorText: { color: colors.error, marginTop: spacing.sm },
  section: {
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.md,
    marginBottom: spacing.md,
  },
  sectionTitle: { fontSize: 15, fontWeight: '700', color: colors.text, marginBottom: spacing.sm },
  row: { flexDirection: 'row', justifyContent: 'space-between', paddingVertical: spacing.xs },
  rowLabel: { color: colors.text },
  rowValue: { color: colors.textMuted, fontWeight: '600' },
  confirmationCard: {
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.primary,
    padding: spacing.md,
    marginBottom: spacing.md,
  },
  confirmationTitle: { fontSize: 16, fontWeight: '800', color: colors.primaryDark },
  confirmationBody: { fontSize: 14, color: colors.textMuted, marginTop: spacing.xs },
  confirmationButton: { marginTop: spacing.md },
  boxesTitle: { fontSize: 18, fontWeight: '800', color: colors.text, marginTop: spacing.sm, marginBottom: spacing.md },
  boxesSpinner: { marginBottom: spacing.md },
  emptyText: { color: colors.textMuted, textAlign: 'center', marginTop: spacing.md },
  boxCard: {
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.md,
    marginBottom: spacing.md,
  },
  boxCardHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start' },
  boxName: { fontSize: 16, fontWeight: '700', color: colors.text, flexShrink: 1 },
  boxPrice: { fontSize: 16, fontWeight: '800', color: colors.primaryDark },
  boxDescription: { fontSize: 14, color: colors.textMuted, marginTop: spacing.xs },
  boxMeta: { fontSize: 13, color: colors.textMuted, marginTop: spacing.xs },
  boxAvailability: { fontSize: 13, fontWeight: '700', color: colors.primaryDark, marginTop: spacing.sm },
  boxSoldOut: { color: colors.error },
  addButton: { marginTop: spacing.md },
  quantityRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.md, marginTop: spacing.md },
  quantityButton: { width: 48 },
  quantityText: { flex: 1, textAlign: 'center', color: colors.text, fontWeight: '600' },
  cartSummary: {
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.md,
    marginTop: spacing.sm,
  },
  cartRow: { flexDirection: 'row', justifyContent: 'space-between', paddingVertical: spacing.xs },
  cartRowText: { color: colors.text },
  cartTotalRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    borderTopWidth: 1,
    borderTopColor: colors.border,
    marginTop: spacing.sm,
    paddingTop: spacing.sm,
  },
  cartTotalLabel: { fontWeight: '700', color: colors.text },
  cartTotalValue: { fontWeight: '800', color: colors.primaryDark },
  checkoutButton: { marginTop: spacing.md },
});
