'use client';

import { useEffect, useState } from 'react';
import { Award } from 'lucide-react';
import { ApiError, apiFetch } from '@/lib/api';
import { Button } from '@/components/ui/button';
import type { ConsistencyProgress as Progress } from '@/lib/sessions';
import { cn } from '@/lib/utils';

export function ConsistencyProgress() {
  const [data, setData] = useState<Progress | null>(null);
  const [error, setError] = useState('');
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    apiFetch<Progress>('/sessions/progress/consistency', {
      signal: controller.signal,
      cache: 'no-store',
    })
      .then((value) => {
        if (!controller.signal.aborted) {
          setData(value);
          setError('');
        }
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted)
          setError(
            error instanceof ApiError
              ? error.message
              : 'Não foi possível carregar suas conquistas.'
          );
      });
    return () => controller.abort();
  }, [retry]);
  return (
    <section
      aria-label="Conquistas de consistência"
      className="bg-card rounded-2xl border p-4"
    >
      <h2 className="flex items-center gap-2 font-semibold">
        <Award className="text-primary size-5" /> Conquistas de consistência
      </h2>
      {error ? (
        <div role="alert">
          <p className="text-destructive mt-2 text-sm">{error}</p>
          <Button
            variant="outline"
            onClick={() => setRetry((value) => value + 1)}
          >
            Tentar novamente
          </Button>
        </div>
      ) : data ? (
        <>
          <p className="text-muted-foreground mt-1 text-sm">
            {data.completed_sessions} treinos concluídos com séries realizadas.
            Cada treino conta uma vez.
          </p>
          <ul className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-3">
            {data.achievements.map((item) => (
              <li
                key={item.sessions_required}
                className={cn(
                  'rounded-xl border p-3 text-xs',
                  item.unlocked
                    ? 'bg-accent border-primary/30 text-accent-foreground'
                    : 'text-muted-foreground'
                )}
              >
                <Award className="mb-1 size-4" />
                <p className="font-semibold">{item.label}</p>
                <p>
                  {item.sessions_required} treino(s) ·{' '}
                  {item.unlocked ? 'Conquistado' : 'Em progresso'}
                </p>
              </li>
            ))}
          </ul>
          <p className="text-muted-foreground mt-3 text-xs">
            Respeite recuperação e descanso. Não é necessário treinar todos os
            dias.
          </p>
        </>
      ) : (
        <p role="status" className="text-muted-foreground mt-2 text-sm">
          Carregando conquistas…
        </p>
      )}
    </section>
  );
}
