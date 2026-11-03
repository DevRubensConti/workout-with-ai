import type { Metadata } from 'next';

import { GenerateFlow } from '@/components/workouts/generate-flow';
import { getCurrentUser } from '@/lib/auth';
import { requirePermissions } from '@/lib/permissions';

export const metadata: Metadata = { title: 'Gerar treino' };

export default async function GenerateWorkoutPage() {
  const user = await getCurrentUser();
  if (!user) return null;
  requirePermissions(user.permissions, ['workouts:write']);

  return <GenerateFlow />;
}
