'use client';

import {
  CalendarCheck,
  ChevronLeft,
  ChevronRight,
  Clock,
  Dumbbell,
  Flame,
} from 'lucide-react';
import Link from 'next/link';
import { useEffect, useState } from 'react';

import { Button } from '@/components/ui/button';
import { ApiError, apiFetch } from '@/lib/api';
import {
  formatDateTime,
  formatDuration,
  formatVolume,
  type SessionListResponse,
} from '@/lib/sessions';
import { cn } from '@/lib/utils';

interface State {
  key: number;
  data?: SessionListResponse;
  error?: string;
}

export function SessionHistory() {
  const [page, setPage] = useState(1);
  const [retry, setRetry] = useState(0);
  const [state, setState] = useState<State | null>(null);
  const requestKey = page * 1000 + retry;

  useEffect(() => {
    const controller = new AbortController();
    apiFetch<SessionListResponse>(`/sessions?page=${page}&page_size=15`, {
      cache: 'no-store',
      signal: controller.signal,
    })
      .then((data) => {
        if (!controller.signal.aborted) setState({ key: requestKey, data });
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        setState({
          key: requestKey,
          error:
            error instanceof ApiError
              ? error.message
              : 'Não foi possível carregar o histórico.',
        });
      });
    return () => controller.abort();
  }, [page, requestKey]);

  const loading = state?.key !== requestKey;
  const data = state?.error ? undefined : state?.data;
  const error = state?.key === requestKey ? state.error : undefined;

  return (
    <div className="container mx-auto max-w-3xl space-y-6 px-4 py-8 md:px-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight md:text-3xl">
          Histórico
        </h1>
        <p className="text-muted-foreground mt-1 text-sm">
          Os treinos que você já realizou.
          {data && data.total > 0 && ` ${data.total} no total.`}
        </p>
      </div>

      {error ? (
        <div
          role="alert"
          className="bg-card flex flex-col items-center gap-3 rounded-xl border px-6 py-12 text-center"
        >
          <p className="text-destructive text-sm">{error}</p>
          <Button onClick={() => setRetry((value) => value + 1)}>
            Tentar novamente
          </Button>
        </div>
      ) : state === null ? (
        <div aria-hidden className="space-y-3">
          {[0, 1, 2].map((item) => (
            <div
              key={item}
              className="bg-muted h-24 animate-pulse rounded-xl"
            />
          ))}
        </div>
      ) : data && data.items.length === 0 ? (
        <div className="bg-card flex flex-col items-center gap-4 rounded-2xl border px-6 py-16 text-center">
          <span className="bg-primary/10 text-primary flex size-14 items-center justify-center rounded-2xl">
            <CalendarCheck className="size-7" />
          </span>
          <div className="space-y-1">
            <p className="text-lg font-semibold">Nenhum treino registrado</p>
            <p className="text-muted-foreground max-w-sm text-sm">
              Abra o seu treino atual e toque em &quot;Iniciar treino&quot; para
              começar a registrar cargas e repetições.
            </p>
          </div>
          <Button asChild>
            <Link href="/workouts">Ir para meus treinos</Link>
          </Button>
        </div>
      ) : (
        <ul
          aria-busy={loading}
          className={cn(
            'space-y-3 transition-opacity',
            loading && 'pointer-events-none opacity-50'
          )}
        >
          {data?.items.map((item) => (
            <li key={item.id}>
              <Link
                href={`/sessions/${item.id}`}
                className="bg-card hover:border-primary/50 block rounded-xl border p-4 shadow-sm transition-colors"
              >
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div>
                    <p className="font-semibold">{item.day_name ?? 'Treino'}</p>
                    <p className="text-muted-foreground text-sm">
                      {item.plan_name ? `${item.plan_name} · ` : ''}
                      {formatDateTime(item.started_at)}
                    </p>
                  </div>
                  {item.perceived_effort !== null && (
                    <span className="bg-muted inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-medium">
                      <Flame className="size-3.5" /> {item.perceived_effort}/10
                    </span>
                  )}
                </div>
                <p className="text-muted-foreground mt-3 flex flex-wrap gap-x-4 gap-y-1 text-sm">
                  {item.duration_seconds !== null && (
                    <span className="inline-flex items-center gap-1">
                      <Clock className="size-4" />
                      {formatDuration(item.duration_seconds)}
                    </span>
                  )}
                  <span className="inline-flex items-center gap-1">
                    <Dumbbell className="size-4" />
                    {item.completed_sets}{' '}
                    {item.completed_sets === 1 ? 'série' : 'séries'}
                  </span>
                  {item.volume_kg > 0 && (
                    <span>{formatVolume(item.volume_kg)} de volume</span>
                  )}
                </p>
              </Link>
            </li>
          ))}
        </ul>
      )}

      {data && data.total_pages > 1 && !error && (
        <nav
          aria-label="Paginação do histórico"
          className="flex items-center justify-between gap-3"
        >
          <Button
            variant="outline"
            disabled={data.page <= 1 || loading}
            onClick={() => setPage((value) => value - 1)}
          >
            <ChevronLeft /> Anterior
          </Button>
          <span className="text-muted-foreground text-sm">
            Página {data.page} de {data.total_pages}
          </span>
          <Button
            variant="outline"
            disabled={data.page >= data.total_pages || loading}
            onClick={() => setPage((value) => value + 1)}
          >
            Próxima <ChevronRight />
          </Button>
        </nav>
      )}
    </div>
  );
}
