// ---------------------------------------------------------------------------
// Device push-token registration (Firebase Cloud Messaging) — pairs with
// the backend's Firebase Admin SDK integration (backend/app/push_utils.py)
// and src/api/notifications.js. Called from AuthContext on
// login/session-restore (register) and on logout (unregister).
//
// Push remoto NON è disponibile in Expo Go da SDK 53 in poi su Android —
// serve una development build (`npx expo run:android` / `eas build
// --profile development`), vedi backend/README.md § 6. In Expo Go questo
// modulo fa nulla, in silenzio: l'app resta comunque completamente
// utilizzabile — lo storico notifiche in-app (app/notifications.js)
// funziona sempre, indipendentemente dal push.
// ---------------------------------------------------------------------------
import Constants from 'expo-constants';
import * as Notifications from 'expo-notifications';
import { Platform } from 'react-native';
import { registerPushToken, unregisterPushToken } from '../api/notifications';

// Tenuto solo per poterlo deregistrare al logout — non persistito: si
// ri-registra da sé al prossimo avvio/login (vedi AuthContext.js).
let currentToken = null;

function isExpoGo() {
  // Constants.appOwnership: 'expo' in Expo Go, 'standalone' in una build
  // pubblicata/EAS, null in una development build — solo 'expo' su
  // Android non supporta il push remoto.
  return Constants.appOwnership === 'expo';
}

export async function registerForPushNotificationsAsync() {
  if (isExpoGo() && Platform.OS === 'android') {
    return;
  }

  try {
    if (Platform.OS === 'android') {
      // Necessario su Android 13+ prima che il prompt di permesso appaia
      // e prima di poter ottenere un token — vedi doc expo-notifications.
      await Notifications.setNotificationChannelAsync('default', {
        name: 'Notifiche',
        importance: Notifications.AndroidImportance.DEFAULT,
      });
    }

    let { status } = await Notifications.getPermissionsAsync();
    if (status !== 'granted') {
      ({ status } = await Notifications.requestPermissionsAsync());
    }
    if (status !== 'granted') return;

    const { data: token } = await Notifications.getDevicePushTokenAsync();
    currentToken = token;
    await registerPushToken(token, Platform.OS);
  } catch {
    // Best-effort: l'assenza di push (dev client senza google-services.json
    // configurato, permesso negato, ecc.) non deve mai impedire l'uso
    // dell'app.
  }
}

export async function unregisterCurrentPushToken() {
  if (!currentToken) return;
  const token = currentToken;
  currentToken = null;
  try {
    await unregisterPushToken(token);
  } catch {
    // Best-effort anche qui: il logout deve andare a buon fine comunque.
  }
}
