import * as DocumentPicker from 'expo-document-picker';
import { useRouter } from 'expo-router';
import { useEffect, useState } from 'react';
import { ActivityIndicator, Alert, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { createBox, deleteBox, listMyBoxes, updateBox } from '../src/api/boxes';
import { listShopOrders, setShopOrderState } from '../src/api/orders';
import { createShop, getMyShop, replaceLicense, updateMyShop } from '../src/api/shops';
import BoxForm from '../src/components/BoxForm';
import PrimaryButton from '../src/components/PrimaryButton';
import ShopForm from '../src/components/ShopForm';
import { useAuth } from '../src/context/AuthContext';
import { colors, radius, spacing } from '../src/theme';

const LICENSE_LABEL = {
  pending_review: 'Licenza in fase di verifica ⏳',
  approved: 'Licenza verificata ✅',
  rejected: 'Licenza rifiutata ❌',
};

export default function HomeVenditore() {
  const router = useRouter();
  const { user, logout } = useAuth();

  const [shop, setShop] = useState(undefined); // undefined = not loaded yet, null = no shop yet
  const [isLoadingShop, setIsLoadingShop] = useState(false);
  const [shopError, setShopError] = useState(null);
  const [isEditing, setIsEditing] = useState(false);

  const [isPickingLicense, setIsPickingLicense] = useState(false);
  const [licenseError, setLicenseError] = useState(null);

  const [boxes, setBoxes] = useState([]);
  const [isLoadingBoxes, setIsLoadingBoxes] = useState(false);
  const [boxesError, setBoxesError] = useState(null);
  // null = hidden, 'new' = create form, or a box object = editing that box.
  const [boxFormTarget, setBoxFormTarget] = useState(null);
  const [deletingBoxId, setDeletingBoxId] = useState(null);

  const [orders, setOrders] = useState([]);
  const [isLoadingOrders, setIsLoadingOrders] = useState(false);
  const [ordersError, setOrdersError] = useState(null);
  const [updatingOrderId, setUpdatingOrderId] = useState(null);

  // The real DB schema ties license_url/verificationStatus to `store`, not
  // to `user` (see backend/db/projectwork_en_v2.sql) — so license status
  // lives on the shop object, not on the account.
  const licenseStatus = shop?.license_status;

  // A shop's own license_status (reviewed by the admin, see
  // backend/app/routers/admin.py) starts at pending_review the moment it's
  // created — the vendor must be able to create/edit their shop regardless
  // of it, gating this behind "approved" would mean no shop is ever
  // created for the admin to approve in the first place.
  useEffect(() => {
    setIsLoadingShop(true);
    setShopError(null);
    getMyShop()
      .then(setShop)
      .catch((err) => setShopError(err.message))
      .finally(() => setIsLoadingShop(false));
  }, []);

  // Boxes belong to the shop (POST /shops/me/boxes needs one to already
  // exist), so wait for it to load first — a vendor can manage boxes
  // regardless of license status, same reasoning as the shop itself above:
  // customers just won't see them until the shop is approved.
  useEffect(() => {
    if (!shop) return;
    loadBoxes();
    loadOrders();
  }, [shop]);

  async function loadBoxes() {
    setIsLoadingBoxes(true);
    setBoxesError(null);
    try {
      setBoxes(await listMyBoxes());
    } catch (err) {
      setBoxesError(err.message);
    } finally {
      setIsLoadingBoxes(false);
    }
  }

  async function loadOrders() {
    setIsLoadingOrders(true);
    setOrdersError(null);
    try {
      setOrders(await listShopOrders());
    } catch (err) {
      setOrdersError(err.message);
    } finally {
      setIsLoadingOrders(false);
    }
  }

  async function handleLogout() {
    await logout();
    router.replace('/');
  }

  async function handleShopSubmit(payload) {
    const saved = shop ? await updateMyShop(payload) : await createShop(payload);
    setShop(saved);
    setIsEditing(false);
  }

  async function handleReuploadLicense() {
    setLicenseError(null);
    const result = await DocumentPicker.getDocumentAsync({
      type: ['application/pdf', 'image/*'],
      copyToCacheDirectory: true,
    });
    if (result.canceled) return;
    setIsPickingLicense(true);
    try {
      const updated = await replaceLicense(result.assets[0]);
      setShop(updated);
    } catch (err) {
      setLicenseError(err.message);
    } finally {
      setIsPickingLicense(false);
    }
  }

  async function handleBoxSubmit(payload) {
    if (boxFormTarget && boxFormTarget !== 'new') {
      await updateBox(boxFormTarget.id, payload);
    } else {
      await createBox(payload);
    }
    setBoxFormTarget(null);
    await loadBoxes();
  }

  function handleDeleteBox(box) {
    Alert.alert('Eliminare questa box?', `"${box.name}" non sarà più visibile ai clienti.`, [
      { text: 'Annulla', style: 'cancel' },
      {
        text: 'Elimina',
        style: 'destructive',
        onPress: async () => {
          setDeletingBoxId(box.id);
          try {
            await deleteBox(box.id);
            await loadBoxes();
          } catch (err) {
            setBoxesError(err.message);
          } finally {
            setDeletingBoxId(null);
          }
        },
      },
    ]);
  }

  async function handleOrderState(order, state) {
    setUpdatingOrderId(order.id);
    setOrdersError(null);
    try {
      await setShopOrderState(order.id, state);
      await Promise.all([loadOrders(), loadBoxes()]); // picked up/cancelled both affect availability
    } catch (err) {
      setOrdersError(err.message);
    } finally {
      setUpdatingOrderId(null);
    }
  }

  function handleCancelOrder(order) {
    Alert.alert('Annullare questa prenotazione?', `Le box di "${order.shop_name}" torneranno disponibili.`, [
      { text: 'No', style: 'cancel' },
      { text: 'Annulla prenotazione', style: 'destructive', onPress: () => handleOrderState(order, 'cancelled') },
    ]);
  }

  return (
    <SafeAreaView style={styles.container} edges={['top', 'left', 'right']}>
      <ScrollView contentContainerStyle={styles.content}>
        <View style={styles.header}>
          <View>
            <Text style={styles.title}>Bentornato, {user?.username}! 🏪</Text>
            <Text style={styles.subtitle}>{user?.email}</Text>
          </View>
          <PrimaryButton title="Esci" variant="outline" onPress={handleLogout} />
        </View>

        {licenseStatus ? (
          <View style={styles.statusBadge}>
            <Text style={styles.statusText}>{LICENSE_LABEL[licenseStatus] ?? 'Stato licenza sconosciuto'}</Text>
          </View>
        ) : null}

        {licenseStatus && licenseStatus !== 'approved' ? (
          <View style={[styles.card, styles.licenseCard]}>
            <Text style={styles.body}>
              {licenseStatus === 'rejected'
                ? 'La licenza caricata non è stata accettata. Ricaricane una nuova per essere rivalutato — puoi comunque continuare a curare il profilo del tuo negozio nel frattempo.'
                : 'Il nostro team sta verificando il documento di licenza caricato in fase di registrazione. Nel frattempo puoi già impostare il tuo negozio qui sotto: sarà visibile ai clienti non appena la licenza sarà approvata.'}
            </Text>
            {licenseStatus === 'rejected' ? (
              <PrimaryButton
                title="Ricarica documento licenza"
                onPress={handleReuploadLicense}
                loading={isPickingLicense}
                style={styles.reuploadButton}
              />
            ) : null}
            {licenseError ? <Text style={styles.errorText}>{licenseError}</Text> : null}
          </View>
        ) : null}

        <ShopSection
          shop={shop}
          isLoading={isLoadingShop}
          error={shopError}
          isEditing={isEditing}
          onEdit={() => setIsEditing(true)}
          onCancelEdit={() => setIsEditing(false)}
          onSubmit={handleShopSubmit}
        />

        {shop ? (
          <BoxesSection
            boxes={boxes}
            isLoading={isLoadingBoxes}
            error={boxesError}
            formTarget={boxFormTarget}
            deletingBoxId={deletingBoxId}
            onAdd={() => setBoxFormTarget('new')}
            onEdit={(box) => setBoxFormTarget(box)}
            onCancelForm={() => setBoxFormTarget(null)}
            onSubmitForm={handleBoxSubmit}
            onDelete={handleDeleteBox}
          />
        ) : null}

        {shop ? (
          <OrdersSection
            orders={orders}
            isLoading={isLoadingOrders}
            error={ordersError}
            updatingOrderId={updatingOrderId}
            onMarkPickedUp={(order) => handleOrderState(order, 'pickedUp')}
            onCancel={handleCancelOrder}
          />
        ) : null}
      </ScrollView>
    </SafeAreaView>
  );
}

function ShopSection({ shop, isLoading, error, isEditing, onEdit, onCancelEdit, onSubmit }) {
  if (isLoading) {
    return <ActivityIndicator color={colors.primary} style={{ marginTop: spacing.lg }} />;
  }
  if (error) {
    return <Text style={styles.errorText}>{error}</Text>;
  }

  if (!shop || isEditing) {
    return (
      <View style={styles.card}>
        <Text style={styles.cardTitle}>{shop ? 'Modifica il tuo negozio' : 'Crea il tuo negozio'}</Text>
        <ShopForm
          initialShop={shop ?? undefined}
          submitLabel={shop ? 'Salva modifiche' : 'Crea negozio'}
          onSubmit={onSubmit}
          onCancel={shop ? onCancelEdit : undefined}
        />
      </View>
    );
  }

  return (
    <View style={styles.card}>
      <Text style={styles.cardTitle}>{shop.name}</Text>
      <Text style={styles.body}>{shop.address}</Text>
      <Text style={styles.body}>📞 {shop.phone}</Text>
      <Text style={styles.todayHours}>
        🕒 Apertura {shop.opening_time} · Ritiro clienti {shop.pickup_window_start}–{shop.pickup_window_end}
      </Text>
      <PrimaryButton title="Modifica negozio" variant="outline" onPress={onEdit} style={styles.editButton} />
    </View>
  );
}

function BoxesSection({
  boxes,
  isLoading,
  error,
  formTarget,
  deletingBoxId,
  onAdd,
  onEdit,
  onCancelForm,
  onSubmitForm,
  onDelete,
}) {
  return (
    <View style={styles.boxesSection}>
      <View style={styles.boxesHeader}>
        <Text style={styles.sectionTitle}>Le tue box 📦</Text>
        {!formTarget ? <PrimaryButton title="+ Aggiungi box" onPress={onAdd} /> : null}
      </View>

      {formTarget ? (
        <View style={[styles.card, styles.boxCard]}>
          <Text style={styles.cardTitle}>{formTarget === 'new' ? 'Nuova box' : 'Modifica box'}</Text>
          <BoxForm
            initialBox={formTarget === 'new' ? undefined : formTarget}
            submitLabel={formTarget === 'new' ? 'Crea box' : 'Salva modifiche'}
            onSubmit={onSubmitForm}
            onCancel={onCancelForm}
          />
        </View>
      ) : null}

      {isLoading ? <ActivityIndicator color={colors.primary} style={{ marginTop: spacing.md }} /> : null}
      {error ? <Text style={styles.errorText}>{error}</Text> : null}

      {!isLoading && !formTarget && boxes.length === 0 ? (
        <Text style={styles.body}>Non hai ancora nessuna box. Aggiungine una per iniziare a vendere.</Text>
      ) : null}

      {boxes.map((box) => (
        <View key={box.id} style={[styles.card, styles.boxCard]}>
          <View style={styles.boxCardHeader}>
            <Text style={styles.cardTitle}>{box.name}</Text>
            <Text style={styles.boxPrice}>€ {box.price.toFixed(2)}</Text>
          </View>
          <Text style={styles.body}>{box.description}</Text>
          <Text style={styles.boxMeta}>
            {box.category} · Allergeni: {box.allergens}
          </Text>
          <Text style={styles.boxMeta}>
            Disponibili: {box.available}/{box.max_boxes} · Ritiro {box.pickup_window_start}–{box.pickup_window_end}
          </Text>
          <Text style={styles.boxMeta}>Scade il {new Date(box.expire_at).toLocaleString()}</Text>
          <View style={styles.boxActions}>
            <PrimaryButton
              title="Modifica"
              variant="outline"
              onPress={() => onEdit(box)}
              style={styles.boxActionButton}
            />
            <PrimaryButton
              title="Elimina"
              variant="outline"
              loading={deletingBoxId === box.id}
              onPress={() => onDelete(box)}
              style={styles.boxActionButton}
            />
          </View>
        </View>
      ))}
    </View>
  );
}

const ORDER_STATE_LABEL = {
  booked: 'Prenotato ⏳',
  pickedUp: 'Ritirato ✅',
  cancelled: 'Annullato ❌',
  expired: 'Scaduto ⌛',
};

function OrdersSection({ orders, isLoading, error, updatingOrderId, onMarkPickedUp, onCancel }) {
  return (
    <View style={styles.boxesSection}>
      <Text style={styles.sectionTitle}>Ordini ricevuti 🧾</Text>

      {isLoading ? <ActivityIndicator color={colors.primary} style={{ marginTop: spacing.md }} /> : null}
      {error ? <Text style={styles.errorText}>{error}</Text> : null}
      {!isLoading && orders.length === 0 ? (
        <Text style={styles.body}>Non hai ancora ricevuto prenotazioni.</Text>
      ) : null}

      {orders.map((order) => (
        <View key={order.id} style={[styles.card, styles.boxCard]}>
          <View style={styles.boxCardHeader}>
            <Text style={styles.cardTitle}>Ordine #{order.id}</Text>
            <Text style={styles.boxMeta}>{ORDER_STATE_LABEL[order.state] ?? order.state}</Text>
          </View>
          {order.items.map((line) => (
            <Text key={line.box_id} style={styles.body}>
              {line.quantity}× {line.box_name}
            </Text>
          ))}
          <Text style={styles.boxMeta}>Ritiro {order.pickup_window}</Text>
          <Text style={styles.boxMeta}>Prenotato il {new Date(order.order_date).toLocaleString()}</Text>
          <Text style={styles.boxPrice}>€ {order.total_price.toFixed(2)}</Text>
          {order.state === 'booked' ? (
            <View style={styles.boxActions}>
              <PrimaryButton
                title="Segna ritirato"
                loading={updatingOrderId === order.id}
                onPress={() => onMarkPickedUp(order)}
                style={styles.boxActionButton}
              />
              <PrimaryButton
                title="Annulla"
                variant="outline"
                loading={updatingOrderId === order.id}
                onPress={() => onCancel(order)}
                style={styles.boxActionButton}
              />
            </View>
          ) : null}
        </View>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  content: { padding: spacing.lg, paddingBottom: spacing.xl },
  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: spacing.md },
  title: { fontSize: 20, fontWeight: '800', color: colors.text },
  subtitle: { fontSize: 14, color: colors.textMuted, marginTop: spacing.xs },
  statusBadge: {
    alignSelf: 'flex-start',
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.lg,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
    marginBottom: spacing.md,
  },
  statusText: { color: colors.text, fontWeight: '600' },
  licenseCard: { marginBottom: spacing.md },
  card: {
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.md,
  },
  cardTitle: { fontSize: 17, fontWeight: '700', color: colors.text, marginBottom: spacing.sm },
  body: { fontSize: 15, color: colors.textMuted, marginTop: spacing.xs },
  todayHours: { fontSize: 14, color: colors.primaryDark, fontWeight: '600', marginTop: spacing.sm },
  editButton: { marginTop: spacing.md },
  reuploadButton: { marginTop: spacing.md },
  errorText: { color: colors.error, marginTop: spacing.sm },
  boxesSection: { marginTop: spacing.lg },
  boxesHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing.md,
  },
  sectionTitle: { fontSize: 18, fontWeight: '800', color: colors.text },
  boxCard: { marginBottom: spacing.md },
  boxCardHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start' },
  boxPrice: { fontSize: 16, fontWeight: '800', color: colors.primaryDark },
  boxMeta: { fontSize: 13, color: colors.textMuted, marginTop: spacing.xs },
  boxActions: { flexDirection: 'row', gap: spacing.sm, marginTop: spacing.md },
  boxActionButton: { flex: 1 },
});
