'use client';

import Link from 'next/link';
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

export function ForgotPasswordForm() {
  const [isLoading, setIsLoading] = useState(false);
  const [sent, setSent] = useState(false);

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsLoading(true);

    const form = new FormData(event.currentTarget);

    try {
      await apiFetch('/auth/forgot-password', {
        method: 'POST',
        body: { email: form.get('email') },
      });
      setSent(true);
    } catch (error) {
      toast.error('Não foi possível enviar o link', {
        description:
          error instanceof ApiError ? error.message : 'Tente novamente.',
      });
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <Card className="w-full max-w-md">
      <CardHeader>
        <CardTitle className="text-2xl">Recuperar senha</CardTitle>
        <CardDescription>
          {sent
            ? 'Se o e-mail estiver cadastrado, você receberá um link para redefinir a senha.'
            : 'Informe seu e-mail para receber o link de redefinição.'}
        </CardDescription>
      </CardHeader>

      {!sent && (
        <form onSubmit={onSubmit}>
          <CardContent className="space-y-2">
            <Label htmlFor="email">E-mail</Label>
            <Input
              id="email"
              name="email"
              type="email"
              autoComplete="email"
              placeholder="voce@exemplo.com"
              required
            />
          </CardContent>

          <CardFooter className="pt-6">
            <Button type="submit" className="w-full" disabled={isLoading}>
              {isLoading ? 'Enviando...' : 'Enviar link'}
            </Button>
          </CardFooter>
        </form>
      )}

      <CardFooter className={sent ? '' : 'justify-center'}>
        <Link
          href="/login"
          className="text-muted-foreground hover:text-primary inline-flex min-h-11 items-center text-sm"
        >
          Voltar para o login
        </Link>
      </CardFooter>
    </Card>
  );
}
