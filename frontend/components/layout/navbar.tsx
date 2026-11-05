'use client';

import {
  ClipboardList,
  Dumbbell,
  History,
  House,
  LogOut,
  Moon,
  SlidersHorizontal,
  Sun,
  User,
} from 'lucide-react';
import { useTheme } from 'next-themes';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';

import { useAuth } from '@/components/auth-provider';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { apiFetch } from '@/lib/api';
import { APP_NAME } from '@/lib/config';
import { cn } from '@/lib/utils';

interface NavbarProps {
  navItems: { id: string; label: string; href: string }[];
}

const mobileIcons = {
  home: House,
  exercises: Dumbbell,
  workouts: ClipboardList,
  history: History,
  'biomechanical-scale': SlidersHorizontal,
};

export function Navbar({ navItems }: NavbarProps) {
  const user = useAuth();
  const pathname = usePathname();
  const router = useRouter();
  const { resolvedTheme, setTheme } = useTheme();

  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    // Evita mismatch de hidratação do ícone de tema
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setMounted(true);
  }, []);

  const isActive = (href: string) =>
    pathname === href || pathname.startsWith(`${href}/`);

  const handleLogout = async () => {
    try {
      await apiFetch('/auth/logout', { method: 'POST' });
    } catch (error) {
      console.error('Erro ao fazer logout:', error);
    } finally {
      router.push('/login');
      router.refresh();
    }
  };

  const links = () =>
    navItems.map((item) => (
      <Link
        key={item.id}
        href={item.href}
        aria-current={isActive(item.href) ? 'page' : undefined}
        className={cn(
          'inline-flex min-h-11 items-center transition-colors',
          isActive(item.href)
            ? 'text-primary font-bold'
            : 'text-muted-foreground hover:text-primary'
        )}
      >
        {item.label}
      </Link>
    ));

  return (
    <>
      <header className="bg-background md:bg-background/95 sticky top-0 z-40 w-full border-b pt-[env(safe-area-inset-top)] md:backdrop-blur">
        <div className="container mx-auto flex h-16 items-center justify-between gap-2 px-4 md:px-6">
          <Link
            href="/home"
            className="flex min-h-11 min-w-0 items-center gap-2 font-bold"
          >
            <Dumbbell className="text-primary size-5" />
            <span className="truncate">{APP_NAME}</span>
          </Link>

          <nav
            aria-label="Navegação principal"
            className="hidden gap-6 text-sm font-medium md:flex"
          >
            {links()}
          </nav>

          <div className="flex shrink-0 items-center gap-1">
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="rounded-full"
              onClick={() =>
                setTheme(resolvedTheme === 'dark' ? 'light' : 'dark')
              }
              aria-label={
                mounted && resolvedTheme === 'dark'
                  ? 'Ativar tema claro'
                  : 'Ativar tema escuro'
              }
            >
              {mounted && resolvedTheme === 'dark' ? <Sun /> : <Moon />}
            </Button>

            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" size="icon" aria-label="Menu da conta">
                  <User />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-56">
                <DropdownMenuLabel>
                  <span className="block truncate">{user.name}</span>
                  <span className="text-muted-foreground block truncate text-xs font-normal">
                    {user.email}
                  </span>
                </DropdownMenuLabel>
                <DropdownMenuSeparator />
                <DropdownMenuItem asChild>
                  <Link href="/account" className="cursor-pointer">
                    <User /> Minha conta
                  </Link>
                </DropdownMenuItem>
                <DropdownMenuItem
                  onSelect={handleLogout}
                  className="cursor-pointer"
                >
                  <LogOut /> Sair
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>
      </header>
      <nav
        aria-label="Navegação principal no celular"
        className="bg-background fixed inset-x-0 bottom-0 z-40 flex h-[var(--mobile-nav-height)] items-start border-t pr-[max(0.5rem,env(safe-area-inset-right))] pb-[env(safe-area-inset-bottom)] pl-[max(0.5rem,env(safe-area-inset-left))] md:hidden"
      >
        {navItems.map((item) => {
          const Icon =
            mobileIcons[item.id as keyof typeof mobileIcons] ?? ClipboardList;
          return (
            <Link
              key={item.id}
              href={item.href}
              prefetch={false}
              aria-current={isActive(item.href) ? 'page' : undefined}
              className={cn(
                'flex h-[4.5rem] min-w-0 flex-1 flex-col items-center justify-center gap-1 rounded-lg px-1 text-center text-xs font-medium',
                isActive(item.href)
                  ? 'text-accent-foreground bg-accent'
                  : 'text-muted-foreground hover:bg-accent'
              )}
            >
              <Icon aria-hidden className="size-5" />
              <span>{item.label}</span>
            </Link>
          );
        })}
      </nav>
    </>
  );
}
