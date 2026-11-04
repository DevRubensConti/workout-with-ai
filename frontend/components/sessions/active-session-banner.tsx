'use client';

import { ArrowRight, Timer } from 'lucide-react';
import Link from 'next/link';
import { useEffect, useState } from 'react';

import type { SessionDetail } from '@/lib/sessions';
import { apiFetch } from '@/lib/api';

// Aviso de treino em andamento, para retomar de qualquer tela de treinos.
export function ActiveSessionBanner() {
  const [session, setSession] = useState<SessionDetail | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    apiFetch<SessionDetail | null>('/sessions/active', {
      cache: 'no-store',
      signal: controller.signal,
    })
      .then((data) => {
        if (!controller.signal.aborted) setSession(data);
      })
      .catch(() => {
        // O aviso é opcional: em caso de erro, simplesmente não aparece.
      });
    return () => controller.abort();
  }, []);

  if (!session) return null;

  return (
    <Link
      href={`/sessions/${session.id}`}
      className="bg-primary/10 border-primary/30 hover:bg-primary/15 flex items-center gap-3 rounded-xl border px-4 py-3 transition-colors"
    >
      <Timer className="text-primary size-5 shrink-0" />
      <span className="min-w-0 flex-1 text-sm">
        <span className="font-semibold">Treino em andamento</span>
        <span className="text-muted-foreground block truncate">
          {session.plan_name} · {session.day_name}
        </span>
      </span>
      <span className="text-primary inline-flex items-center gap-1 text-sm font-medium">
        <span className="sr-only sm:not-sr-only">Continuar</span>{' '}
        <ArrowRight className="size-4" />
      </span>
    </Link>
  );
}
