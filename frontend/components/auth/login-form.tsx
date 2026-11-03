'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';
import { toast } from 'sonner';

import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { apiFetch, ApiError } from '@/lib/api';

export function LoginForm({ sessionExpired }: { sessionExpired: boolean }) {
  const router = useRouter();
  const [isLoading, setIsLoading] = useState(false);

  // Sessão inválida no servidor: limpa o cookie HttpOnly via API.
  useEffect(() => {
    if (!sessionExpired) return;
    apiFetch('/auth/logout', { method: 'POST' })
      .catch(() => {})
      .finally(() => {
        toast.info('Sua sessão expirou. Entre novamente.');
        router.replace('/login');
      });
  }, [sessionExpired, router]);

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsLoading(true);

    const form = new FormData(event.currentTarget);

    try {
      await apiFetch('/auth/login', {
        method: 'POST',
        body: { email: form.get('email'), password: form.get('password') },
      });
      router.push('/home');
      router.refresh();
    } catch (error) {
      toast.error('Erro ao entrar', {
        description:
          error instanceof ApiError ? error.message : 'Tente novamente.',
      });
      setIsLoading(false);
    }
  }

  return (
    <Card className="w-full max-w-md">
      <CardHeader>
        <CardTitle className="text-2xl">Entrar</CardTitle>
        <CardDescription>Acesse sua conta para continuar.</CardDescription>
      </CardHeader>

      <form onSubmit={onSubmit}>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="email">E-mail</Label>
            <Input
              id="email"
              name="email"
              type="email"
              autoComplete="email"
              placeholder="voce@exemplo.com"
              required
            />
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label htmlFor="password">Senha</Label>
              <Link
                href="/forgot-password"
                className="text-muted-foreground hover:text-primary text-xs"
              >
                Esqueceu a senha?
              </Link>
            </div>
            <Input
              id="password"
              name="password"
              type="password"
              autoComplete="current-password"
              placeholder="••••••••"
              required
            />
          </div>
        </CardContent>

        <CardFooter className="flex-col gap-4 pt-6">
          <Button type="submit" className="w-full" disabled={isLoading}>
            {isLoading ? 'Entrando...' : 'Entrar'}
          </Button>
          <p className="text-muted-foreground text-sm">
            Não tem conta?{' '}
            <Link href="/register" className="text-primary font-medium">
              Cadastre-se
            </Link>
          </p>
        </CardFooter>
      </form>
    </Card>
  );
}
