import { Dumbbell } from 'lucide-react';
import Link from 'next/link';

import { APP_NAME } from '@/lib/config';

// Layout das telas públicas (login, cadastro, recuperação de senha)
export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <main className="flex min-h-dvh flex-col items-center justify-center gap-6 px-4 pt-[max(1.5rem,env(safe-area-inset-top))] pb-[max(1.5rem,env(safe-area-inset-bottom))] sm:p-6">
      <Link href="/login" className="flex items-center gap-2 text-xl font-bold">
        <span className="bg-primary text-primary-foreground flex size-10 items-center justify-center rounded-lg">
          <Dumbbell className="size-5" />
        </span>
        {APP_NAME}
      </Link>
      {children}
    </main>
  );
}
