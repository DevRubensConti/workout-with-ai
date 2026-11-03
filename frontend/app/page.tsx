import { redirect } from 'next/navigation';

// O proxy já manda quem não tem sessão para /login.
export default function RootPage() {
  redirect('/home');
}
