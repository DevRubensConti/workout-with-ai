'use client';

import { Dumbbell, LogOut, Menu, Moon, Sun, User, X } from 'lucide-react';
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

export function Navbar({ navItems }: NavbarProps) {
  const user = useAuth();
  const pathname = usePathname();
  const router = useRouter();
  const { resolvedTheme, setTheme } = useTheme();

  const [mounted, setMounted] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

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

  const links = (mobile: boolean) =>
    navItems.map((item) => (
      <Link
        key={item.id}
        href={item.href}
        aria-current={isActive(item.href) ? 'page' : undefined}
        onClick={() => setMobileMenuOpen(false)}
        className={cn(
          mobile ? 'hover:bg-accent rounded-md px-3 py-2' : 'transition-colors',
          isActive(item.href)
            ? 'text-primary font-bold'
            : 'text-muted-foreground hover:text-primary'
        )}
      >
        {item.label}
      </Link>
    ));

  return (
    <header className="bg-background/95 supports-[backdrop-filter]:bg-background/60 sticky top-0 z-50 w-full border-b backdrop-blur">
      <div className="container mx-auto flex h-16 items-center justify-between px-4 md:px-6">
        <Link href="/home" className="flex items-center gap-2 font-bold">
          <Dumbbell className="text-primary size-5" />
          {APP_NAME}
        </Link>

        <nav className="hidden gap-6 text-sm font-medium md:flex">
          {links(false)}
        </nav>

        <div className="flex items-center gap-1">
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="md:hidden"
            onClick={() => setMobileMenuOpen((open) => !open)}
            aria-label={mobileMenuOpen ? 'Fechar menu' : 'Abrir menu'}
            aria-expanded={mobileMenuOpen}
          >
            {mobileMenuOpen ? <X /> : <Menu />}
          </Button>

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

      {mobileMenuOpen && (
        <div className="bg-background/95 border-t md:hidden">
          <nav className="container mx-auto flex flex-col gap-1 px-4 py-3 text-sm">
            {links(true)}
          </nav>
        </div>
      )}
    </header>
  );
}
