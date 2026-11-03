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
      <div className="relative flex min-h-screen flex-col">
        <Navbar navItems={navItems} />
        <main className="flex-1">{children}</main>
        <Footer />
      </div>
    </AuthProvider>
  );
}
