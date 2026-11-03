import type { Metadata } from 'next';

import { SessionHistory } from '@/components/sessions/session-history';
import { getCurrentUser } from '@/lib/auth';
import { requirePermissions } from '@/lib/permissions';

export const metadata: Metadata = { title: 'Histórico' };

export default async function HistoryPage() {
  const user = await getCurrentUser();
  if (!user) return null;
  requirePermissions(user.permissions, ['workouts:read']);

  return <SessionHistory />;
}
