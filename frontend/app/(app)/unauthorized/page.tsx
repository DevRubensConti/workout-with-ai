import { ShieldAlert } from 'lucide-react';
import type { Metadata } from 'next';
import Link from 'next/link';

import { Button } from '@/components/ui/button';

export const metadata: Metadata = { title: 'Acesso negado' };

export default function UnauthorizedPage() {
  return (
    <div className="container mx-auto flex flex-col items-center gap-4 px-4 py-24 text-center">
      <ShieldAlert className="text-destructive size-12" />
      <h1 className="text-2xl font-bold">Acesso negado</h1>
      <p className="text-muted-foreground">
        Você não tem permissão para acessar esta página.
      </p>
      <Button asChild>
        <Link href="/home">Voltar para a home</Link>
      </Button>
    </div>
  );
}
