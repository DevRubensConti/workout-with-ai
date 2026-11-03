'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';

import { WorkoutBuilder } from '@/components/workouts/workout-builder';
import { Button } from '@/components/ui/button';
import { ApiError, apiFetch } from '@/lib/api';
import type { PlanDetail } from '@/lib/workouts';

interface State {
  plan?: PlanDetail;
  error?: string;
}

// Carrega o treino antes de montar o formulário, que parte de um rascunho local.
export function WorkoutEditor({ planId }: { planId: string }) {
  const [state, setState] = useState<State | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    apiFetch<PlanDetail>(
      `/workouts/${encodeURIComponent(planId)}?locale=pt-BR`,
      {
        cache: 'no-store',
        signal: controller.signal,
      }
    )
      .then((plan) => {
        if (!controller.signal.aborted) setState({ plan });
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        setState({
          error:
            error instanceof ApiError && error.status === 404
              ? 'Treino não encontrado.'
              : error instanceof ApiError
                ? error.message
                : 'Não foi possível carregar o treino.',
        });
      });
    return () => controller.abort();
  }, [planId]);

  if (state === null) {
    return (
      <div
        aria-hidden
        className="container mx-auto max-w-4xl space-y-4 px-4 py-8"
      >
        <div className="bg-muted h-10 w-1/3 animate-pulse rounded" />
        <div className="bg-muted h-64 animate-pulse rounded-xl" />
      </div>
    );
  }

  if (!state.plan) {
    return (
      <div className="container mx-auto max-w-xl px-4 py-16 text-center">
        <p role="alert" className="text-destructive text-sm">
          {state.error}
        </p>
        <Button variant="outline" asChild className="mt-6">
          <Link href="/workouts">Meus treinos</Link>
        </Button>
      </div>
    );
  }

  return <WorkoutBuilder plan={state.plan} />;
}
