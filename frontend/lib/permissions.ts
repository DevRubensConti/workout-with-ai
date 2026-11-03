import { redirect } from 'next/navigation';

/**
 * Uso em Server Components/pages: bloqueia a rota se faltar permissão.
 * Ex.: requirePermissions(user.permissions, ['workout:read'])
 */
export function requirePermissions(
  userPermissions: string[],
  requiredPermissions: string[],
  matchAny = false
) {
  const hasAccess = matchAny
    ? requiredPermissions.some((p) => userPermissions.includes(p))
    : requiredPermissions.every((p) => userPermissions.includes(p));

  if (!hasAccess) redirect('/unauthorized');
}
