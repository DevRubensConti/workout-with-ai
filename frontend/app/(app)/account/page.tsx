import type { Metadata } from 'next';

import { ChangePasswordForm } from '@/components/auth/change-password-form';
import { TrainingProfileForm } from '@/components/auth/training-profile-form';
import { WorkoutPreferencesForm } from '@/components/auth/workout-preferences-form';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { getCurrentUser } from '@/lib/auth';

export const metadata: Metadata = { title: 'Minha conta' };

export default async function AccountPage() {
  const user = await getCurrentUser();
  if (!user) return null; // o layout já redireciona

  return (
    <div className="container mx-auto max-w-2xl space-y-6 px-4 py-8 md:px-6">
      <h1 className="text-2xl font-bold">Minha conta</h1>

      <Card>
        <CardHeader>
          <CardTitle>Perfil</CardTitle>
          <CardDescription>Seus dados cadastrais.</CardDescription>
        </CardHeader>
        <CardContent>
          <dl className="grid gap-3 text-sm sm:grid-cols-[8rem_1fr]">
            <dt className="text-muted-foreground">Nome</dt>
            <dd className="min-w-0">{user.name}</dd>
            <dt className="text-muted-foreground">E-mail</dt>
            <dd className="min-w-0">{user.email}</dd>
          </dl>
        </CardContent>
      </Card>

      <TrainingProfileForm />
      <WorkoutPreferencesForm />
      <ChangePasswordForm />
    </div>
  );
}
