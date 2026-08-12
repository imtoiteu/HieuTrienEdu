'use client';

import { useRouter } from 'next/navigation';
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';

import {
  ApiError,
  api,
  readStoredTokens,
  storeTokens,
  type AuthResponse,
  type TokenPair,
  type User,
} from '@/lib/api';

interface AuthContextValue {
  user: User | null;
  /** True until the initial "am I logged in?" check has finished. */
  loading: boolean;
  login: (email: string, password: string) => Promise<User>;
  register: (payload: Record<string, unknown>) => Promise<User>;
  logout: () => void;
  refresh: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  const applyAuth = useCallback((response: AuthResponse) => {
    storeTokens(response.tokens);
    setUser(response.user);
    return response.user;
  }, []);

  const loadCurrentUser = useCallback(async (tokens: TokenPair | null) => {
    if (!tokens?.access_token) {
      setUser(null);
      return;
    }
    try {
      setUser(await api.auth.me(tokens.access_token));
    } catch (error) {
      // An expired access token is recoverable — try the refresh token before giving up,
      // otherwise a returning student is logged out for no good reason.
      if (error instanceof ApiError && error.status === 401 && tokens.refresh_token) {
        try {
          const refreshed = await api.auth.refresh(tokens.refresh_token);
          storeTokens(refreshed);
          setUser(await api.auth.me(refreshed.access_token));
          return;
        } catch {
          // fall through to clearing
        }
      }
      storeTokens(null);
      setUser(null);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      await loadCurrentUser(readStoredTokens());
      if (!cancelled) setLoading(false);
    })();
    return () => {
      cancelled = true;
    };
  }, [loadCurrentUser]);

  const login = useCallback(
    async (email: string, password: string) => applyAuth(await api.auth.login(email, password)),
    [applyAuth],
  );

  const register = useCallback(
    async (payload: Record<string, unknown>) => applyAuth(await api.auth.register(payload)),
    [applyAuth],
  );

  const logout = useCallback(() => {
    storeTokens(null);
    setUser(null);
    router.push('/');
  }, [router]);

  const refresh = useCallback(async () => {
    await loadCurrentUser(readStoredTokens());
  }, [loadCurrentUser]);

  const value = useMemo<AuthContextValue>(
    () => ({ user, loading, login, register, logout, refresh }),
    [user, loading, login, register, logout, refresh],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used inside an AuthProvider');
  }
  return context;
}

/**
 * Redirect to the login page unless the user is signed in (and, optionally, holds one of
 * `roles`). Returns the auth state so callers can render a loading state while it resolves.
 */
export function useRequireAuth(locale: string, roles?: User['role'][]) {
  const auth = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (auth.loading) return;
    if (!auth.user) {
      router.replace(`/${locale}/login`);
      return;
    }
    if (roles && roles.length > 0 && !roles.includes(auth.user.role)) {
      router.replace(`/${locale}/dashboard`);
    }
    // `roles` is a literal array at every call site, so comparing by content avoids an
    // effect that re-runs on every render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [auth.loading, auth.user, locale, router, roles?.join(',')]);

  return auth;
}
