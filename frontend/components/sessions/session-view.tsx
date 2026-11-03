'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';

import { SessionRunner } from '@/components/sessions/session-runner';
import { SessionSummaryView } from '@/components/sessions/session-summary-view';
import { Button } from '@/components/ui/button';
import { ApiError, apiFetch } from '@/lib/api';
import type { SessionDetail } from '@/lib/sessions';

interface State {
  session?: SessionDetail;
  error?: string;
  notFound?: boolean;
}

export function SessionView({
  sessionId,
  canWrite,
}: {
  sessionId: string;
  canWrite: boolean;
}) {
  const router = useRouter();
  const [state, setState] = useState<State | null>(null);
  const [retry, setRetry] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    apiFetch<SessionDetail>(`/sessions/${encodeURIComponent(sessionId)}`, {
      cache: 'no-store',
      signal: controller.signal,
    })
      .then((session) => {
        if (!controller.signal.aborted) setState({ session });
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        if (error instanceof ApiError && error.status === 404) {
          setState({ notFound: true });
          return;
        }
        setState({
          error:
            error instanceof ApiError
              ? error.message
              : 'Não foi possível carregar o treino.',
        });
      });
    return () => controller.abort();
  }, [sessionId, retry]);

  if (state === null) {
    return (
      <div
        aria-hidden
        className="container mx-auto max-w-3xl space-y-4 px-4 py-8"
      >
        <div className="bg-muted h-10 w-1/2 animate-pulse rounded" />
        <div className="bg-muted h-40 animate-pulse rounded-xl" />
        <div className="bg-muted h-40 animate-pulse rounded-xl" />
      </div>
    );
  }

  if (!state.session) {
    return (
      <div className="container mx-auto max-w-xl px-4 py-16 text-center">
        <p className="text-lg font-semibold">
          {state.notFound ? 'Treino não encontrado' : 'Algo deu errado'}
        </p>
        <p className="text-muted-foreground mt-2 text-sm">
          {state.notFound
            ? 'Ele pode ter sido cancelado ou não pertence à sua conta.'
            : state.error}
        </p>
        <div className="mt-6 flex justify-center gap-2">
          <Button variant="outline" asChild>
            <Link href="/workouts">Meus treinos</Link>
          </Button>
          {state.error && (
            <Button
              onClick={() => {
                setState(null);
                setRetry((value) => value + 1);
              }}
            >
              Tentar novamente
            </Button>
          )}
        </div>
      </div>
    );
  }

  if (state.session.finished_at !== null) {
    return <SessionSummaryView session={state.session} canWrite={canWrite} />;
  }

  return (
    <SessionRunner
      session={state.session}
      onFinished={(session) => {
        setState({ session });
        router.refresh();
        window.scrollTo({ top: 0 });
      }}
      onCancelled={() => {
        router.push('/workouts');
        router.refresh();
      }}
    />
  );
}
