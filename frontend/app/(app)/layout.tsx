import { redirect } from 'next/navigation';

import { AuthProvider } from '@/components/auth-provider';
import { Footer } from '@/components/layout/footer';
import { Navbar } from '@/components/layout/navbar';
import { getCurrentUser } from '@/lib/auth';
import { getAllowedRoutes } from '@/lib/navigation';

// Layout das telas autenticadas. O usuário vem da API (não só do JWT), então
// usuário desativado/removido é barrado aqui mesmo com cookie ainda "válido".
export default async function AppLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const user = await getCurrentUser();
  if (!user) redirect('/login?session=expired');

  const navItems = getAllowedRoutes(user.permissions);

  return (
    <AuthProvider user={user}>
      <div className="relative flex min-h-dvh min-w-0 flex-col pb-[var(--mobile-nav-height)] md:pb-0">
        <a
          href="#main-content"
          className="bg-background focus-visible:ring-ring sr-only z-[60] rounded-md p-3 focus:not-sr-only focus:fixed focus:top-2 focus:left-2"
        >
          Pular para o conteúdo
        </a>
        <Navbar navItems={navItems} />
        <main
          id="main-content"
          tabIndex={-1}
          className="min-w-0 flex-1 outline-none"
        >
          {children}
        </main>
        <Footer />
      </div>
    </AuthProvider>
  );
}
