import type { Metadata } from 'next';

import { WorkoutBuilder } from '@/components/workouts/workout-builder';
import { getCurrentUser } from '@/lib/auth';
import { requirePermissions } from '@/lib/permissions';

export const metadata: Metadata = { title: 'Novo treino' };

export default async function NewWorkoutPage() {
  const user = await getCurrentUser();
  if (!user) return null;
  requirePermissions(user.permissions, ['workouts:write']);

  return <WorkoutBuilder />;
}
