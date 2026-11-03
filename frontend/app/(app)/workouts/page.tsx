import type { Metadata } from 'next';

import { WorkoutList } from '@/components/workouts/workout-list';
import { getCurrentUser } from '@/lib/auth';
import { requirePermissions } from '@/lib/permissions';

export const metadata: Metadata = { title: 'Meus treinos' };

export default async function WorkoutsPage() {
  const user = await getCurrentUser();
  if (!user) return null; // o layout já redireciona
  requirePermissions(user.permissions, ['workouts:read']);

  return <WorkoutList canWrite={user.permissions.includes('workouts:write')} />;
}
