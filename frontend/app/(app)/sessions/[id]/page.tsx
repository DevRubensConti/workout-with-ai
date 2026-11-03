import type { Metadata } from 'next';

import { SessionView } from '@/components/sessions/session-view';
import { getCurrentUser } from '@/lib/auth';
import { requirePermissions } from '@/lib/permissions';

export const metadata: Metadata = { title: 'Treino' };

export default async function SessionPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const user = await getCurrentUser();
  if (!user) return null;
  requirePermissions(user.permissions, ['workouts:read']);
  const { id } = await params;

  return (
    <SessionView
      sessionId={id}
      canWrite={user.permissions.includes('workouts:write')}
    />
  );
}
