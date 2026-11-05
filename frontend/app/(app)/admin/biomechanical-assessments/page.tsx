import type { Metadata } from 'next';

import { BiomechanicalAssessmentsAdmin } from '@/components/admin/biomechanical-assessments-admin';
import { getCurrentUser } from '@/lib/auth';
import { requirePermissions } from '@/lib/permissions';

export const metadata: Metadata = { title: 'Avaliações biomecânicas' };

export default async function BiomechanicalAssessmentsPage({
  searchParams,
}: {
  searchParams: Promise<{ exercise_id?: string }>;
}) {
  const user = await getCurrentUser();
  if (!user) return null;
  requirePermissions(user.permissions, ['exercises:manage']);
  const params = await searchParams;

  return <BiomechanicalAssessmentsAdmin exerciseId={params.exercise_id} />;
}
