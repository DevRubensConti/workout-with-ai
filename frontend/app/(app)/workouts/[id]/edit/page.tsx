import type { Metadata } from 'next';

import { WorkoutEditor } from '@/components/workouts/workout-editor';
import { getCurrentUser } from '@/lib/auth';
import { requirePermissions } from '@/lib/permissions';

export const metadata: Metadata = { title: 'Editar treino' };

export default async function EditWorkoutPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const user = await getCurrentUser();
  if (!user) return null;
  requirePermissions(user.permissions, ['workouts:write']);
  const { id } = await params;

  return <WorkoutEditor planId={id} />;
}
