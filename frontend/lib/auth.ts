import 'server-only';

import { cookies } from 'next/headers';
import { cache } from 'react';

export interface CurrentUser {
  id: string;
  name: string;
  email: string;
  role: string;
  permissions: string[];
}

const SERVER_API_URL =
  process.env.API_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  'http://localhost:8000';

/**
 * Usuário logado, validado pela API (fonte da verdade: banco).
 * `cache` deduplica a chamada dentro da mesma requisição (layout + page).
 * Retorna null se não houver sessão válida.
 */
export const getCurrentUser = cache(async (): Promise<CurrentUser | null> => {
  const cookieStore = await cookies();
  const token = cookieStore.get('access_token')?.value;
  if (!token) return null;

  const response = await fetch(`${SERVER_API_URL}/auth/me`, {
    headers: { cookie: `access_token=${token}` },
    cache: 'no-store',
  });

  if (!response.ok) return null;
  return (await response.json()) as CurrentUser;
});
