import { createContext, useContext, useEffect, useMemo, useState } from 'react';
import * as authApi from '../api/auth';
import { onAuthExpired } from '../api/client';
import { registerForPushNotificationsAsync, unregisterCurrentPushToken } from '../utils/pushNotifications';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    authApi
      .getSessionUser()
      .then(setUser)
      .finally(() => setIsLoading(false));
  }, []);

  // Fires when a stored refresh token is no longer valid (expired, or the
  // backend restarted and lost its in-memory state) — clear the session even
  // if nothing on screen explicitly called logout().
  useEffect(() => onAuthExpired(() => setUser(null)), []);

  // Registra questo dispositivo per le push (Firebase Cloud Messaging) ogni
  // volta che c'è una sessione attiva — sia al primo avvio (sessione già
  // salvata) sia subito dopo login/registrazione. No-op silenzioso se il
  // push remoto non è disponibile (Expo Go) o il permesso viene negato —
  // vedi src/utils/pushNotifications.js.
  useEffect(() => {
    if (user) registerForPushNotificationsAsync();
  }, [user?.id]);

  const value = useMemo(
    () => ({
      user,
      isLoading,
      async registerCustomer(data) {
        const registered = await authApi.registerCustomer(data);
        setUser(registered);
        return registered;
      },
      async registerVendor(data) {
        const registered = await authApi.registerVendor(data);
        setUser(registered);
        return registered;
      },
      async login(data) {
        const loggedIn = await authApi.login(data);
        setUser(loggedIn);
        return loggedIn;
      },
      async logout() {
        await unregisterCurrentPushToken();
        await authApi.logout();
        setUser(null);
      },
      // Re-fetches the profile from the backend (license status changed,
      // shop created/edited, ...) without a full logout/login round trip.
      async refreshUser() {
        const refreshed = await authApi.refreshUser();
        setUser(refreshed);
        return refreshed;
      },
    }),
    [user, isLoading]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return ctx;
}
