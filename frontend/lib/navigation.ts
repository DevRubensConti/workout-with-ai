// Fonte da verdade dos menus. Para uma nova página: adicione um item aqui.

export interface NavItem {
  id: string;
  label: string;
  href: string;
  permissions: string[]; // [] = qualquer usuário logado
  matchAny?: boolean; // true: basta UMA permissão (OR). Padrão: exige TODAS.
}

export const NAVIGATION_MENU: NavItem[] = [
  {
    id: 'home',
    label: 'Home',
    href: '/home',
    permissions: [],
  },
  {
    id: 'exercises',
    label: 'Exercícios',
    href: '/exercises',
    permissions: ['workouts:read'],
  },
  {
    id: 'workouts',
    label: 'Meus treinos',
    href: '/workouts',
    permissions: ['workouts:read'],
  },
  {
    id: 'history',
    label: 'Histórico',
    href: '/history',
    permissions: ['workouts:read'],
  },
];

export function getAllowedRoutes(
  userPermissions: string[],
  routes: NavItem[] = NAVIGATION_MENU
): NavItem[] {
  return routes.filter((item) => {
    if (item.permissions.length === 0) return true;
    if (item.matchAny) {
      return item.permissions.some((p) => userPermissions.includes(p));
    }
    return item.permissions.every((p) => userPermissions.includes(p));
  });
}
