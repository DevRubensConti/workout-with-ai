import type { Metadata } from 'next';

import { WorkoutDetail } from '@/components/workouts/workout-detail';
import { getCurrentUser } from '@/lib/auth';
import { requirePermissions } from '@/lib/permissions';

export const metadata: Metadata = { title: 'Treino' };

export default async function WorkoutPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const user = await getCurrentUser();
  if (!user) return null;
  requirePermissions(user.permissions, ['workouts:read']);
  const { id } = await params;

  return (
    <WorkoutDetail
      planId={id}
      canWrite={user.permissions.includes('workouts:write')}
    />
  );
}
