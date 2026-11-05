import type { Metadata } from 'next';

import { BiomechanicalScaleAdmin } from '@/components/admin/biomechanical-scale-admin';
import { getCurrentUser } from '@/lib/auth';
import { requirePermissions } from '@/lib/permissions';

export const metadata: Metadata = { title: 'Critérios biomecânicos' };

export default async function BiomechanicalScalePage() {
  const user = await getCurrentUser();
  if (!user) return null;
  requirePermissions(user.permissions, ['exercises:manage']);

  return <BiomechanicalScaleAdmin />;
}
