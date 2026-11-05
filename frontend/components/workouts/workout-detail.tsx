'use client';

import {
  Archive,
  ArrowLeft,
  Dumbbell,
  Pencil,
  Play,
  Trash2,
} from 'lucide-react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';
import { toast } from 'sonner';

import { ConfirmDialog } from '@/components/confirm-dialog';
import { ExerciseImageViewer } from '@/components/exercises/exercise-image-viewer';
import { ActiveSessionBanner } from '@/components/sessions/active-session-banner';
import { GenerationPanel } from '@/components/workouts/generation-panel';
import { ExerciseReplacement } from '@/components/workouts/exercise-replacement';
import { Button } from '@/components/ui/button';
import { ApiError, apiFetch } from '@/lib/api';
import {
  equipmentLabel,
  levelBadgeClass,
  levelLabel,
  muscleLabel,
} from '@/lib/exercises';
import { extractAiInfo } from '@/lib/generator';
import {
  formatDate,
  formatReps,
  formatRest,
  formatWeight,
  type PlanDetail,
  type PlanExercise,
} from '@/lib/workouts';
import { cn } from '@/lib/utils';

type Action = 'activate' | 'archive' | 'delete';

interface State {
  key: number;
  plan?: PlanDetail;
  error?: string;
  notFound?: boolean;
}

function Chip({ children }: { children: React.ReactNode }) {
  return (
    <span className="bg-muted rounded-full px-2.5 py-1 text-xs font-medium">
      {children}
    </span>
  );
}

function ExerciseRow({
  item,
  index,
  replacement,
}: {
  item: PlanExercise;
  index: number;
  replacement?: React.ReactNode;
}) {
  return (
    <li className="bg-card flex gap-3 rounded-xl border p-3 md:gap-4 md:p-4">
      <div className="bg-muted relative h-16 w-16 shrink-0 overflow-hidden rounded-lg sm:h-20 sm:w-28">
        <ExerciseImageViewer
          images={item.images}
          alt={item.exercise_name}
          sizes="112px"
        />
        <span className="bg-overlay/70 text-overlay-foreground pointer-events-none absolute top-1.5 left-1.5 flex size-6 items-center justify-center rounded-full text-xs font-semibold">
          {index + 1}
        </span>
      </div>
      <div className="min-w-0 flex-1 space-y-2">
        <div>
          <p className="font-semibold">{item.exercise_name}</p>
          <p className="text-muted-foreground text-sm">
            {muscleLabel(item.muscle_group)}
            {item.equipment ? ` · ${equipmentLabel(item.equipment)}` : ''}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Chip>
            {item.sets} {item.sets === 1 ? 'série' : 'séries'}
          </Chip>
          <Chip>{formatReps(item.reps_min, item.reps_max)} reps</Chip>
          {item.target_weight_kg !== null && (
            <Chip>{formatWeight(item.target_weight_kg)}</Chip>
          )}
          {item.rest_seconds !== null && (
            <Chip>Descanso {formatRest(item.rest_seconds)}</Chip>
          )}
        </div>
        {item.notes && (
          <p className="text-muted-foreground text-sm italic">{item.notes}</p>
        )}
        {replacement}
      </div>
    </li>
  );
}

export function WorkoutDetail({
  planId,
  canWrite,
}: {
  planId: string;
  canWrite: boolean;
}) {
  const router = useRouter();
  const [state, setState] = useState<State | null>(null);
  const [activeDay, setActiveDay] = useState(0);
  const [pending, setPending] = useState<Action | null>(null);
  const [confirming, setConfirming] = useState<Action | null>(null);
  const [retry, setRetry] = useState(0);
  const [starting, setStarting] = useState(false);

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
        if (!controller.signal.aborted) setState({ key: retry, plan });
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        if (error instanceof ApiError && error.status === 404) {
          setState({ key: retry, notFound: true });
          return;
        }
        setState({
          key: retry,
          error:
            error instanceof ApiError
              ? error.message
              : 'Não foi possível carregar o treino.',
        });
      });
    return () => controller.abort();
  }, [planId, retry]);

  async function startDay(dayId: string) {
    setStarting(true);
    try {
      const started = await apiFetch<{ id: string }>('/sessions', {
        method: 'POST',
        body: { day_id: dayId },
      });
      router.push(`/sessions/${started.id}`);
    } catch (error) {
      toast.error(
        error instanceof ApiError
          ? error.message
          : 'Não foi possível iniciar o treino.'
      );
      setStarting(false);
    }
  }

  async function run(action: Action) {
    setPending(action);
    try {
      if (action === 'delete') {
        await apiFetch(`/workouts/${planId}`, { method: 'DELETE' });
        toast.success('Treino excluído.');
        router.push('/workouts');
        router.refresh();
        return;
      }
      const plan = await apiFetch<PlanDetail>(
        `/workouts/${planId}/${action}?locale=pt-BR`,
        { method: 'POST' }
      );
      setState({ key: retry, plan });
      toast.success(
        action === 'activate'
          ? 'Este é agora o seu treino atual.'
          : 'Treino arquivado.'
      );
      router.refresh();
    } catch (error) {
      toast.error(
        error instanceof ApiError
          ? error.message
          : 'Não foi possível concluir a ação.'
      );
    } finally {
      setPending(null);
      setConfirming(null);
    }
  }

  if (state === null) {
    return (
      <div
        aria-hidden
        className="container mx-auto max-w-4xl space-y-4 px-4 py-8"
      >
        <div className="bg-muted h-10 w-1/2 animate-pulse rounded" />
        <div className="bg-muted h-24 animate-pulse rounded-xl" />
        <div className="bg-muted h-24 animate-pulse rounded-xl" />
      </div>
    );
  }

  if (state.notFound || state.error || !state.plan) {
    return (
      <div className="container mx-auto max-w-xl px-4 py-16 text-center">
        <p className="text-lg font-semibold">
          {state.notFound ? 'Treino não encontrado' : 'Algo deu errado'}
        </p>
        <p className="text-muted-foreground mt-2 text-sm">
          {state.notFound
            ? 'Ele pode ter sido excluído ou não pertence à sua conta.'
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

  const { plan } = state;
  const dayIndex = Math.min(activeDay, plan.days.length - 1);
  const day = plan.days[dayIndex];
  const isActive = plan.status === 'active';
  const aiInfo = plan.source === 'ai' ? extractAiInfo(plan.ai_metadata) : null;

  return (
    <div className="container mx-auto max-w-4xl space-y-6 px-4 py-8 md:px-6">
      <Link
        href="/workouts"
        className="text-muted-foreground hover:text-foreground inline-flex items-center gap-1 text-sm"
      >
        <ArrowLeft className="size-4" /> Meus treinos
      </Link>

      {canWrite && <ActiveSessionBanner />}

      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0 flex-1 basis-64 space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="min-w-0 text-2xl font-bold tracking-tight md:text-3xl">
              {plan.name}
            </h1>
            <span
              className={cn(
                'rounded-full px-2.5 py-1 text-xs font-medium',
                isActive
                  ? 'bg-accent text-accent-foreground'
                  : 'bg-muted text-muted-foreground'
              )}
            >
              {isActive ? 'Treino atual' : 'Arquivado'}
            </span>
          </div>
          <div className="flex w-full flex-wrap gap-2 sm:w-auto">
            {plan.goal && <Chip>{plan.goal}</Chip>}
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
          {plan.description && (
            <p className="text-muted-foreground max-w-2xl text-sm">
              {plan.description}
            </p>
          )}
          <p className="text-muted-foreground text-xs">
            {plan.day_count} {plan.day_count === 1 ? 'dia' : 'dias'} ·{' '}
            {plan.exercise_count}{' '}
            {plan.exercise_count === 1 ? 'exercício' : 'exercícios'} · desde{' '}
            {formatDate(plan.started_at)}
          </p>
        </div>

        {canWrite && (
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" asChild>
              <Link href={`/workouts/${plan.id}/edit`}>
                <Pencil /> Editar
              </Link>
            </Button>
            {isActive ? (
              <Button
                variant="outline"
                onClick={() => setConfirming('archive')}
              >
                <Archive /> Arquivar
              </Button>
            ) : (
              <Button
                onClick={() => run('activate')}
                disabled={pending !== null}
              >
                <Play />{' '}
                {pending === 'activate' ? 'Ativando…' : 'Usar este treino'}
              </Button>
            )}
            <Button
              variant="outline"
              className="text-destructive"
              onClick={() => setConfirming('delete')}
            >
              <Trash2 /> Excluir
            </Button>
          </div>
        )}
      </header>

      {aiInfo && <GenerationPanel info={aiInfo} mode="saved" />}

      <div
        role="tablist"
        aria-label="Dias do treino"
        className="flex gap-2 overflow-x-auto pb-1 [&::-webkit-scrollbar]:hidden"
      >
        {plan.days.map((item, index) => (
          <button
            type="button"
            role="tab"
            key={item.id}
            aria-selected={index === dayIndex}
            onClick={() => setActiveDay(index)}
            className={cn(
              'shrink-0 rounded-lg border px-4 py-2 text-sm font-medium whitespace-nowrap transition-colors',
              index === dayIndex
                ? 'bg-primary text-primary-foreground border-primary'
                : 'text-muted-foreground hover:text-foreground'
            )}
          >
            {item.name}
          </button>
        ))}
      </div>

      <section role="tabpanel" aria-label={day.name} className="space-y-4">
        {canWrite && day.exercises.length > 0 && (
          <Button
            size="lg"
            className="h-auto min-h-11 w-full whitespace-normal sm:w-auto"
            onClick={() => startDay(day.id)}
            disabled={starting}
          >
            <Dumbbell /> {starting ? 'Iniciando…' : `Iniciar ${day.name}`}
          </Button>
        )}
        {day.notes && (
          <p className="bg-muted/60 rounded-lg border px-4 py-3 text-sm">
            {day.notes}
          </p>
        )}
        {day.exercises.length === 0 ? (
          <p className="text-muted-foreground rounded-xl border border-dashed px-6 py-10 text-center text-sm">
            Este dia ainda não tem exercícios.
          </p>
        ) : (
          <ol className="space-y-3">
            {day.exercises.map((item, index) => (
              <ExerciseRow
                key={item.id}
                item={item}
                index={index}
                replacement={
                  canWrite && (
                    <ExerciseReplacement
                      mode="plan"
                      name={item.exercise_name}
                      disabled={starting || pending !== null}
                      getContext={() => ({
                        mode: 'plan',
                        plan_id: plan.id,
                        day_id: day.id,
                        row_id: item.id,
                      })}
                      onApplied={(_, result) => {
                        if (result?.plan)
                          setState({ key: retry, plan: result.plan });
                        toast.success('Exercício trocado neste dia do plano.');
                      }}
                    />
                  )
                }
              />
            ))}
          </ol>
        )}
      </section>

      <ConfirmDialog
        open={confirming === 'archive'}
        title="Arquivar este treino?"
        description="Ele deixa de ser o seu treino atual, mas continua guardado e pode ser reativado quando quiser."
        confirmLabel="Arquivar"
        pending={pending === 'archive'}
        onCancel={() => setConfirming(null)}
        onConfirm={() => run('archive')}
      />
      <ConfirmDialog
        open={confirming === 'delete'}
        title="Excluir este treino?"
        description="Essa ação não pode ser desfeita. O histórico de treinos já realizados é mantido."
        confirmLabel="Excluir"
        destructive
        pending={pending === 'delete'}
        onCancel={() => setConfirming(null)}
        onConfirm={() => run('delete')}
      />
    </div>
  );
}
