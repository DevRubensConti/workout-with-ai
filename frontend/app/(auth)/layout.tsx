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
    <div className="flex min-h-screen flex-col items-center justify-center gap-6 p-4">
      <Link href="/login" className="flex items-center gap-2 text-xl font-bold">
        <span className="bg-primary text-primary-foreground flex size-10 items-center justify-center rounded-lg">
          <Dumbbell className="size-5" />
        </span>
        {APP_NAME}
      </Link>
      {children}
    </div>
  );
}
