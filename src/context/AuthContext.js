import { createContext, useContext, useEffect, useMemo, useState } from 'react';
import * as authApi from '../api/auth';

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
        await authApi.logout();
        setUser(null);
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
