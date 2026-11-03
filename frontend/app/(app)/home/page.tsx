import { Bot, ClipboardList, Dumbbell, TrendingUp } from 'lucide-react';
import type { Metadata } from 'next';
import Link from 'next/link';

import {
  Card,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { getCurrentUser } from '@/lib/auth';

export const metadata: Metadata = { title: 'Home' };

// Módulos do produto; os que ainda não têm tela ficam como "Em breve".
const modules = [
  {
    title: 'Assistente de IA',
    description:
      'Gere um treino com Gemini, considerando seu perfil e suas preferências.',
    icon: Bot,
    href: '/workouts/generate',
  },
  {
    title: 'Meus treinos',
    description: 'Crie e acompanhe as suas fichas de treino.',
    icon: ClipboardList,
    href: '/workouts',
  },
  {
    title: 'Progresso',
    description: 'Evolução de cargas, frequência e metas ao longo do tempo.',
    icon: TrendingUp,
    href: undefined,
  },
];

export default async function HomePage() {
  const user = await getCurrentUser();
  const firstName = user?.name.split(' ')[0];

  return (
    <div className="container mx-auto px-4 py-8 md:px-6">
      <div className="mb-8 flex items-center gap-3">
        <span className="bg-primary text-primary-foreground flex size-12 items-center justify-center rounded-xl">
          <Dumbbell className="size-6" />
        </span>
        <div>
          <h1 className="text-2xl font-bold">Olá, {firstName}!</h1>
          <p className="text-muted-foreground text-sm">
            Bem-vindo ao seu assistente de treinos.
          </p>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        {modules.map(({ title, description, icon: Icon, href }) => {
          const card = (
            <Card
              className={
                href
                  ? 'hover:border-primary/50 h-full transition-colors'
                  : 'h-full'
              }
            >
              <CardHeader>
                <div className="flex items-center justify-between">
                  <Icon className="text-primary size-6" />
                  {!href && (
                    <span className="bg-muted text-muted-foreground rounded-full px-2 py-0.5 text-xs">
                      Em breve
                    </span>
                  )}
                </div>
                <CardTitle className="pt-2">{title}</CardTitle>
                <CardDescription>{description}</CardDescription>
              </CardHeader>
            </Card>
          );
          return href ? (
            <Link key={title} href={href} className="rounded-xl">
              {card}
            </Link>
          ) : (
            <div key={title}>{card}</div>
          );
        })}
      </div>
    </div>
  );
}
