'use client';

import * as React from 'react';

import type { CurrentUser } from '@/lib/auth';

const AuthContext = React.createContext<CurrentUser | null>(null);

// Disponibiliza o usuário (resolvido no servidor) para Client Components.
export function AuthProvider({
  user,
  children,
}: {
  user: CurrentUser;
  children: React.ReactNode;
}) {
  return <AuthContext.Provider value={user}>{children}</AuthContext.Provider>;
}

export function useAuth(): CurrentUser {
  const user = React.useContext(AuthContext);
  if (!user)
    throw new Error('useAuth deve ser usado dentro de <AuthProvider>.');
  return user;
}

export function useHasPermission(...permissions: string[]): boolean {
  const { permissions: granted } = useAuth();
  return permissions.every((p) => granted.includes(p));
}
