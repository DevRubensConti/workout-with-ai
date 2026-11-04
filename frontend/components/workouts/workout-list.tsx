'use client';

import {
  CalendarDays,
  ClipboardList,
  Dumbbell,
  Plus,
  Sparkles,
} from 'lucide-react';
import Link from 'next/link';
import { useEffect, useState } from 'react';
import { toast } from 'sonner';

import { Button } from '@/components/ui/button';
import { ActiveSessionBanner } from '@/components/sessions/active-session-banner';
import { ApiError, apiFetch } from '@/lib/api';
import { levelBadgeClass, levelLabel } from '@/lib/exercises';
import { formatDate, type PlanDetail, type PlanSummary } from '@/lib/workouts';
import { cn } from '@/lib/utils';

interface State {
  plans?: PlanSummary[];
  error?: string;
}

function PlanStats({ plan }: { plan: PlanSummary }) {
  return (
    <p className="text-muted-foreground flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
      <span className="inline-flex items-center gap-1">
        <CalendarDays className="size-4" /> {plan.day_count}{' '}
        {plan.day_count === 1 ? 'dia' : 'dias'}
      </span>
      <span className="inline-flex items-center gap-1">
        <Dumbbell className="size-4" /> {plan.exercise_count}{' '}
        {plan.exercise_count === 1 ? 'exercício' : 'exercícios'}
      </span>
    </p>
  );
}

function PlanBadges({ plan }: { plan: PlanSummary }) {
  return (
    <div className="grid w-full gap-2 min-[400px]:grid-cols-2 sm:flex sm:w-auto sm:flex-wrap">
      {plan.goal && (
        <span className="bg-muted rounded-full px-2.5 py-1 text-xs font-medium">
          {plan.goal}
        </span>
      )}
      {plan.level && (
        <span
          className={cn(
            'rounded-full px-2.5 py-1 text-xs font-medium',
            levelBadgeClass(plan.level)
          )}
        >
          {levelLabel(plan.level)}
        </span>
      )}
    </div>
  );
}

export function WorkoutList({ canWrite }: { canWrite: boolean }) {
  const [state, setState] = useState<State | null>(null);
  const [retry, setRetry] = useState(0);
  const [activating, setActivating] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    apiFetch<PlanSummary[]>('/workouts', {
      cache: 'no-store',
      signal: controller.signal,
    })
      .then((plans) => {
        if (!controller.signal.aborted) setState({ plans });
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        setState({
          error:
            error instanceof ApiError
              ? error.message
              : 'Não foi possível carregar seus treinos.',
        });
      });
    return () => controller.abort();
  }, [retry]);

  async function activate(plan: PlanSummary) {
    setActivating(plan.id);
    try {
      await apiFetch<PlanDetail>(`/workouts/${plan.id}/activate`, {
        method: 'POST',
      });
      toast.success(`“${plan.name}” agora é o seu treino atual.`);
      setRetry((value) => value + 1);
    } catch (error) {
      toast.error(
        error instanceof ApiError
          ? error.message
          : 'Não foi possível ativar o treino.'
      );
    } finally {
      setActivating(null);
    }
  }

  const plans = state?.plans ?? [];
  const active = plans.find((plan) => plan.status === 'active');
  const archived = plans.filter((plan) => plan.status === 'archived');

  return (
    <div className="container mx-auto max-w-5xl space-y-8 px-4 py-8 md:px-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight md:text-3xl">
            Meus treinos
          </h1>
          <p className="text-muted-foreground mt-1 text-sm">
            Seu treino atual e o histórico de fichas anteriores.
          </p>
        </div>
        {canWrite && (
          <div className="flex flex-wrap gap-2">
            <Button asChild size="lg" variant="outline">
              <Link href="/workouts/generate">
                <Sparkles /> Gerar treino
              </Link>
            </Button>
            <Button asChild size="lg">
              <Link href="/workouts/new">
                <Plus /> Novo treino
              </Link>
            </Button>
          </div>
        )}
      </div>

      {canWrite && <ActiveSessionBanner />}

      {state?.error ? (
        <div
          role="alert"
          className="bg-card flex flex-col items-center gap-3 rounded-xl border px-6 py-12 text-center"
        >
          <p className="text-destructive text-sm">{state.error}</p>
          <Button
            onClick={() => {
              setState(null);
              setRetry((value) => value + 1);
            }}
          >
            Tentar novamente
          </Button>
        </div>
      ) : state === null ? (
        <div aria-hidden className="space-y-4">
          <div className="bg-muted h-40 animate-pulse rounded-2xl" />
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="bg-muted h-28 animate-pulse rounded-xl" />
            <div className="bg-muted h-28 animate-pulse rounded-xl" />
          </div>
        </div>
      ) : plans.length === 0 ? (
        <div className="bg-card flex flex-col items-center gap-4 rounded-2xl border px-6 py-16 text-center">
          <span className="bg-primary/10 text-primary flex size-14 items-center justify-center rounded-2xl">
            <ClipboardList className="size-7" />
          </span>
          <div className="space-y-1">
            <p className="text-lg font-semibold">
              Você ainda não tem um treino
            </p>
            <p className="text-muted-foreground max-w-sm text-sm">
              Monte sua primeira ficha escolhendo exercícios do catálogo e
              definindo séries, repetições e carga.
            </p>
          </div>
          {canWrite && (
            <div className="flex flex-wrap justify-center gap-2">
              <Button asChild size="lg">
                <Link href="/workouts/generate">
                  <Sparkles /> Gerar um treino para mim
                </Link>
              </Button>
              <Button asChild size="lg" variant="outline">
                <Link href="/workouts/new">
                  <Plus /> Criar do zero
                </Link>
              </Button>
            </div>
          )}
        </div>
      ) : (
        <>
          {active ? (
            <section aria-labelledby="current-plan">
              <h2
                id="current-plan"
                className="text-muted-foreground mb-3 text-sm font-semibold tracking-wide uppercase"
              >
                Treino atual
              </h2>
              <div className="from-primary/15 via-card to-card rounded-2xl border bg-gradient-to-br p-4 shadow-sm sm:p-6">
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div className="space-y-3">
                    <h3 className="text-xl font-bold md:text-2xl">
                      {active.name}
                    </h3>
                    <PlanBadges plan={active} />
                    <PlanStats plan={active} />
                    {active.description && (
                      <p className="text-muted-foreground max-w-xl text-sm">
                        {active.description}
                      </p>
                    )}
                    <p className="text-muted-foreground text-xs">
                      Ativo desde {formatDate(active.started_at)}
                    </p>
                  </div>
                  <div className="flex gap-2">
                    <Button asChild>
                      <Link href={`/workouts/${active.id}`}>Abrir treino</Link>
                    </Button>
                    {canWrite && (
                      <Button variant="outline" asChild>
                        <Link href={`/workouts/${active.id}/edit`}>Editar</Link>
                      </Button>
                    )}
                  </div>
                </div>
              </div>
            </section>
          ) : (
            <p className="bg-muted/60 rounded-xl border px-4 py-3 text-sm">
              Nenhum treino ativo no momento. Ative um dos treinos abaixo ou
              crie um novo.
            </p>
          )}

          {archived.length > 0 && (
            <section aria-labelledby="archived-plans">
              <h2
                id="archived-plans"
                className="text-muted-foreground mb-3 text-sm font-semibold tracking-wide uppercase"
              >
                Anteriores
              </h2>
              <ul className="grid gap-4 sm:grid-cols-2">
                {archived.map((plan) => (
                  <li
                    key={plan.id}
                    className="bg-card flex flex-col gap-3 rounded-xl border p-5 shadow-sm"
                  >
                    <div className="space-y-2">
                      <Link
                        href={`/workouts/${plan.id}`}
                        className="hover:text-primary text-lg font-semibold transition-colors"
                      >
                        {plan.name}
                      </Link>
                      <PlanBadges plan={plan} />
                      <PlanStats plan={plan} />
                      {plan.archived_at && (
                        <p className="text-muted-foreground text-xs">
                          Arquivado em {formatDate(plan.archived_at)}
                        </p>
                      )}
                    </div>
                    <div className="mt-auto flex gap-2">
                      <Button variant="outline" size="sm" asChild>
                        <Link href={`/workouts/${plan.id}`}>Ver</Link>
                      </Button>
                      {canWrite && (
                        <Button
                          size="sm"
                          disabled={activating === plan.id}
                          onClick={() => activate(plan)}
                        >
                          {activating === plan.id
                            ? 'Ativando…'
                            : 'Usar este treino'}
                        </Button>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            </section>
          )}
        </>
      )}
    </div>
  );
}
