import type { Metadata } from 'next';

import { ExerciseCatalog } from '@/components/exercises/exercise-catalog';
import { getCurrentUser } from '@/lib/auth';
import { requirePermissions } from '@/lib/permissions';

export const metadata: Metadata = { title: 'Catálogo de exercícios' };

export default async function ExercisesPage() {
  const user = await getCurrentUser();
  if (!user) return null;
  requirePermissions(user.permissions, ['workouts:read']);

  return <ExerciseCatalog />;
}
