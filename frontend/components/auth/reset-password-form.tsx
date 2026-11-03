'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useState } from 'react';
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

export function ResetPasswordForm({ token }: { token?: string }) {
  const router = useRouter();
  const [isLoading, setIsLoading] = useState(false);

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const form = new FormData(event.currentTarget);
    const password = String(form.get('password'));

    if (password.length < 8) {
      toast.error('A senha deve ter pelo menos 8 caracteres.');
      return;
    }
    if (password !== form.get('confirmPassword')) {
      toast.error('As senhas não coincidem.');
      return;
    }

    setIsLoading(true);

    try {
      await apiFetch('/auth/reset-password', {
        method: 'POST',
        body: { token, new_password: password },
      });
      toast.success('Senha redefinida!', {
        description: 'Entre com a nova senha.',
      });
      router.push('/login');
    } catch (error) {
      toast.error('Não foi possível redefinir a senha', {
        description:
          error instanceof ApiError ? error.message : 'Tente novamente.',
      });
      setIsLoading(false);
    }
  }

  if (!token) {
    return (
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle className="text-2xl">Link inválido</CardTitle>
          <CardDescription>
            O link de recuperação está incompleto. Solicite um novo.
          </CardDescription>
        </CardHeader>
        <CardFooter>
          <Button asChild className="w-full">
            <Link href="/forgot-password">Solicitar novo link</Link>
          </Button>
        </CardFooter>
      </Card>
    );
  }

  return (
    <Card className="w-full max-w-md">
      <CardHeader>
        <CardTitle className="text-2xl">Nova senha</CardTitle>
        <CardDescription>Crie uma nova senha segura.</CardDescription>
      </CardHeader>

      <form onSubmit={onSubmit}>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="password">Nova senha</Label>
            <Input
              id="password"
              name="password"
              type="password"
              autoComplete="new-password"
              placeholder="Mínimo de 8 caracteres"
              minLength={8}
              required
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="confirmPassword">Confirme a nova senha</Label>
            <Input
              id="confirmPassword"
              name="confirmPassword"
              type="password"
              autoComplete="new-password"
              required
            />
          </div>
        </CardContent>

        <CardFooter className="pt-6">
          <Button type="submit" className="w-full" disabled={isLoading}>
            {isLoading ? 'Salvando...' : 'Redefinir senha'}
          </Button>
        </CardFooter>
      </form>
    </Card>
  );
}
