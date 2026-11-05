'use client';

import {
  Check,
  ChevronLeft,
  ChevronRight,
  Plus,
  Timer,
  Trash2,
  X,
} from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { toast } from 'sonner';

import { ConfirmDialog } from '@/components/confirm-dialog';
import { ExerciseImageViewer } from '@/components/exercises/exercise-image-viewer';
import { ExerciseProgress } from '@/components/sessions/exercise-progress';
import { ExerciseReplacement } from '@/components/workouts/exercise-replacement';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { ApiError, apiFetch } from '@/lib/api';
import { muscleLabel } from '@/lib/exercises';
import {
  formatClock,
  parseApiDate,
  parseReps,
  parseWeight,
  rowsFromSession,
  rowsToPayload,
  type ExerciseRows,
  type SessionDetail,
  type SetRow,
} from '@/lib/sessions';
import { formatReps, formatRest, formatWeight, nextKey } from '@/lib/workouts';
import { cn } from '@/lib/utils';

type SaveState = 'saved' | 'pending' | 'saving' | 'invalid' | 'error';

const SAVE_LABEL: Record<SaveState, string> = {
  saved: 'Salvo',
  pending: 'Alterações pendentes…',
  saving: 'Salvando…',
  invalid: 'Há valores inválidos',
  error: 'Falha ao salvar',
};

const AUTOSAVE_DELAY_MS = 500;

interface SessionRunnerProps {
  session: SessionDetail;
  onFinished: (detail: SessionDetail) => void;
  onCancelled: () => void;
}

function errorMessage(error: unknown, fallback: string) {
  return error instanceof ApiError ? error.message : fallback;
}

function SessionClock({
  startedAt,
  restEnd = null,
  compact = false,
}: {
  startedAt: string;
  restEnd?: number | null;
  compact?: boolean;
}) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const interval = window.setInterval(() => setNow(Date.now()), 1000);
    const sync = () => setNow(Date.now());
    document.addEventListener('visibilitychange', sync);
    return () => {
      window.clearInterval(interval);
      document.removeEventListener('visibilitychange', sync);
    };
  }, []);
  const elapsed = (now - parseApiDate(startedAt).getTime()) / 1000;
  const restLeft = restEnd === null ? null : Math.ceil((restEnd - now) / 1000);
  return (
    <>
      <p
        role={compact ? undefined : 'timer'}
        aria-label={
          restLeft === null ? 'Tempo de treino' : 'Tempo restante de descanso'
        }
        className={
          compact
            ? 'text-data font-mono text-xl font-semibold tabular-nums'
            : 'text-data my-3 font-mono text-5xl font-bold tabular-nums min-[400px]:text-6xl sm:text-7xl'
        }
      >
        {formatClock(restLeft === null ? elapsed : Math.max(0, restLeft))}
      </p>
      {!compact && restLeft !== null && (
        <>
          <p className="text-muted-foreground text-sm">
            Tempo de treino: {formatClock(elapsed)}
          </p>
          <p role="status" className="mt-2 font-medium">
            {restLeft <= 0
              ? 'Descanso concluído. Retome quando estiver pronto.'
              : 'Recupere-se antes da próxima série.'}
          </p>
        </>
      )}
    </>
  );
}

export function SessionRunner({
  session,
  onFinished,
  onCancelled,
}: SessionRunnerProps) {
  const [initialRows] = useState(() => rowsFromSession(session));
  const [rows, setRows] = useState<ExerciseRows[]>(initialRows);
  const rowsRef = useRef<ExerciseRows[]>(initialRows);
  const editCount = useRef(0);
  const timer = useRef<number | null>(null);
  const chain = useRef<Promise<boolean>>(Promise.resolve(true));

  const [saveState, setSaveState] = useState<SaveState>('saved');
  const [restEnd, setRestEnd] = useState<number | null>(null);
  const [finishOpen, setFinishOpen] = useState(false);
  const [cancelOpen, setCancelOpen] = useState(false);
  const [effort, setEffort] = useState<number | null>(null);
  const [notes, setNotes] = useState('');
  const [busy, setBusy] = useState<'finish' | 'cancel' | 'replace' | null>(
    null
  );
  const [exerciseIndex, setExerciseIndex] = useState(() => {
    const first = initialRows.findIndex((exercise) =>
      exercise.sets.some((set) => !set.completed)
    );
    return Math.max(0, first);
  });
  const [restEnabled, setRestEnabled] = useState<boolean | null>(null);
  const [preferenceError, setPreferenceError] = useState('');
  const [preferenceRetry, setPreferenceRetry] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    apiFetch<{ rest_timer_enabled: boolean }>('/auth/workout-preferences', {
      signal: controller.signal,
      cache: 'no-store',
    })
      .then((data) => {
        if (!controller.signal.aborted) {
          setRestEnabled(data.rest_timer_enabled);
          setPreferenceError('');
        }
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted)
          setPreferenceError(
            errorMessage(
              error,
              'Não foi possível carregar a preferência de timer.'
            )
          );
      });
    return () => controller.abort();
  }, [preferenceRetry]);

  function persist(): Promise<boolean> {
    chain.current = chain.current.then(async () => {
      const payload = rowsToPayload(rowsRef.current);
      if (payload === null) {
        setSaveState('invalid');
        return false;
      }
      const seen = editCount.current;
      setSaveState('saving');
      try {
        await apiFetch(`/sessions/${session.id}/sets`, {
          method: 'PUT',
          body: { sets: payload },
        });
        setSaveState(editCount.current === seen ? 'saved' : 'pending');
        return true;
      } catch (error) {
        setSaveState('error');
        toast.error(errorMessage(error, 'Não foi possível salvar as séries.'));
        return false;
      }
    });
    return chain.current;
  }

  function update(change: (current: ExerciseRows[]) => ExerciseRows[]) {
    const next = change(rowsRef.current);
    rowsRef.current = next;
    editCount.current += 1;
    setRows(next);
    setSaveState('pending');
    if (timer.current !== null) window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => {
      timer.current = null;
      void persist();
    }, AUTOSAVE_DELAY_MS);
  }

  function patchSet(exerciseId: string, key: string, patch: Partial<SetRow>) {
    update((current) =>
      current.map((exercise) =>
        exercise.exerciseId === exerciseId
          ? {
              ...exercise,
              sets: exercise.sets.map((set) =>
                set.key === key ? { ...set, ...patch } : set
              ),
            }
          : exercise
      )
    );
  }

  function toggleSet(exercise: ExerciseRows, set: SetRow, completedAt: number) {
    const completed = !set.completed;
    if (
      completed &&
      (parseWeight(set.weight) === undefined ||
        parseReps(set.reps) === null ||
        parseReps(set.reps) === 0)
    ) {
      toast.error(
        'Informe uma carga válida e ao menos uma repetição antes de concluir a série.'
      );
      return;
    }
    patchSet(exercise.exerciseId, set.key, { completed });
    const rest = exercise.target?.rest_seconds;
    if (completed && rest && restEnabled) setRestEnd(completedAt + rest * 1000);
    if (!completed) setRestEnd(null);
  }

  function addSet(exerciseId: string) {
    update((current) =>
      current.map((exercise) => {
        if (exercise.exerciseId !== exerciseId) return exercise;
        const last = exercise.sets[exercise.sets.length - 1];
        return {
          ...exercise,
          sets: [
            ...exercise.sets,
            {
              key: nextKey(),
              reps: last?.reps ?? '10',
              weight: last?.weight ?? '',
              completed: false,
            },
          ],
        };
      })
    );
  }

  function removeSet(exerciseId: string, key: string) {
    update((current) =>
      current.map((exercise) =>
        exercise.exerciseId === exerciseId
          ? {
              ...exercise,
              sets: exercise.sets.filter((set) => set.key !== key),
            }
          : exercise
      )
    );
  }

  async function finish() {
    setBusy('finish');
    if (timer.current !== null) {
      window.clearTimeout(timer.current);
      timer.current = null;
    }
    if (!(await persist())) {
      toast.error(
        'Não foi possível salvar as séries. Verifique os valores e tente novamente.'
      );
      setBusy(null);
      return;
    }
    try {
      const detail = await apiFetch<SessionDetail>(
        `/sessions/${session.id}/finish`,
        {
          method: 'POST',
          body: { notes: notes.trim() || null, perceived_effort: effort },
        }
      );
      toast.success('Treino finalizado. Bom trabalho!');
      onFinished(detail);
    } catch (error) {
      toast.error(errorMessage(error, 'Não foi possível finalizar o treino.'));
      setBusy(null);
    }
  }

  async function cancel() {
    setBusy('cancel');
    if (timer.current !== null) {
      window.clearTimeout(timer.current);
      timer.current = null;
    }
    try {
      await chain.current;
      await apiFetch(`/sessions/${session.id}`, { method: 'DELETE' });
      toast.success('Treino cancelado.');
      onCancelled();
    } catch (error) {
      toast.error(errorMessage(error, 'Não foi possível cancelar o treino.'));
      setBusy(null);
    }
  }

  const total = rows.reduce((sum, exercise) => sum + exercise.sets.length, 0);
  const done = rows.reduce(
    (sum, exercise) =>
      sum + exercise.sets.filter((set) => set.completed).length,
    0
  );
  const activeExercise = rows[exerciseIndex];
  const currentWeights =
    activeExercise?.sets
      .filter((set) => set.completed && (parseReps(set.reps) ?? 0) > 0)
      .map((set) => parseWeight(set.weight))
      .filter((weight): weight is number => typeof weight === 'number') ?? [];

  async function navigateExercise(next: number) {
    if (timer.current !== null) {
      window.clearTimeout(timer.current);
      timer.current = null;
    }
    if (!(await persist())) return;
    setExerciseIndex(next);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  return (
    <div className="pb-24 md:pb-8">
      <div className="bg-background md:bg-background/90 sticky top-[var(--app-header-height)] z-30 border-b md:backdrop-blur">
        <div className="container mx-auto max-w-3xl space-y-2 px-4 py-3 md:px-6">
          <div className="flex items-center justify-between gap-3">
            <div className="min-w-0">
              <p className="truncate font-semibold">
                {session.day_name ?? 'Treino'}
              </p>
              <p className="text-muted-foreground truncate text-xs">
                {session.plan_name}
              </p>
            </div>
            <div className="shrink-0 text-right">
              <SessionClock startedAt={session.started_at} compact />
              <p
                className={cn(
                  'text-xs',
                  saveState === 'invalid' || saveState === 'error'
                    ? 'text-destructive'
                    : 'text-muted-foreground'
                )}
                aria-live="polite"
              >
                {SAVE_LABEL[saveState]}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <div
              role="progressbar"
              aria-valuemin={0}
              aria-valuemax={total}
              aria-valuenow={done}
              aria-label="Séries concluídas"
              className="bg-muted h-2 flex-1 overflow-hidden rounded-full"
            >
              <div
                className="bg-primary h-full transition-all"
                style={{ width: `${total ? (done / total) * 100 : 0}%` }}
              />
            </div>
            <span className="text-muted-foreground text-xs tabular-nums">
              {done}/{total} séries
            </span>
          </div>
        </div>
      </div>

      <div className="container mx-auto max-w-3xl space-y-4 px-4 py-6 md:px-6">
        <section
          aria-label="Temporizador"
          className="from-primary/10 to-card rounded-2xl border bg-gradient-to-br p-4 text-center shadow-sm sm:rounded-3xl sm:p-6"
        >
          <p className="text-muted-foreground flex items-center justify-center gap-2 text-sm">
            <Timer className="size-4" />{' '}
            {restEnabled && restEnd !== null
              ? 'Descanso entre séries'
              : 'Tempo de treino'}
          </p>
          <SessionClock
            startedAt={session.started_at}
            restEnd={restEnabled ? restEnd : null}
          />
          {restEnabled && restEnd !== null && (
            <>
              <Button
                variant="outline"
                className="mt-3"
                onClick={() => setRestEnd(null)}
              >
                Encerrar descanso
              </Button>
            </>
          )}
          {preferenceError ? (
            <div role="alert">
              <p className="text-destructive text-sm">{preferenceError}</p>
              <Button
                variant="outline"
                onClick={() => setPreferenceRetry((value) => value + 1)}
              >
                Recarregar preferência
              </Button>
            </div>
          ) : restEnabled === null ? (
            <p role="status" className="text-muted-foreground text-xs">
              Carregando preferência de descanso…
            </p>
          ) : (
            <p className="text-muted-foreground text-xs">
              {restEnabled
                ? 'Descanso inicia ao concluir cada série, conforme a prescrição.'
                : 'Timer de descanso desativado em Minha conta.'}
            </p>
          )}
        </section>
        <div className="grid grid-cols-[auto_minmax(0,1fr)_auto] items-end gap-2 sm:gap-3">
          <Button
            variant="outline"
            disabled={exerciseIndex <= 0 || busy !== null}
            onClick={() => void navigateExercise(exerciseIndex - 1)}
          >
            <ChevronLeft />{' '}
            <span className="sr-only sm:not-sr-only">Exercício anterior</span>
          </Button>
          <label className="min-w-0 flex-1 text-center text-xs">
            <span className="text-muted-foreground">
              Exercício {rows.length ? exerciseIndex + 1 : 0} de {rows.length}
            </span>
            <select
              aria-label="Exercício em execução"
              className="bg-elevated mt-1 h-9 w-full truncate rounded-lg border px-2 text-sm"
              value={exerciseIndex}
              disabled={busy !== null}
              onChange={(event) =>
                void navigateExercise(Number(event.target.value))
              }
            >
              {rows.map((exercise, index) => (
                <option key={exercise.exerciseId} value={index}>
                  {exercise.name}
                </option>
              ))}
            </select>
          </label>
          <Button
            variant="outline"
            disabled={exerciseIndex >= rows.length - 1 || busy !== null}
            onClick={() => void navigateExercise(exerciseIndex + 1)}
          >
            <span className="sr-only sm:not-sr-only">Próximo exercício</span>{' '}
            <ChevronRight />
          </Button>
        </div>
        <fieldset disabled={busy !== null}>
          {rows.slice(exerciseIndex, exerciseIndex + 1).map((exercise) => (
            <section
              key={exercise.exerciseId}
              aria-label={exercise.name}
              className="bg-card rounded-xl border p-4 shadow-sm"
            >
              <div className="flex items-start gap-3">
                <span className="bg-muted relative h-14 w-20 shrink-0 overflow-hidden rounded-lg">
                  <ExerciseImageViewer
                    images={exercise.images}
                    alt={exercise.name}
                    sizes="80px"
                  />
                </span>
                <div className="min-w-0 flex-1">
                  <h2 className="text-xl leading-snug font-semibold">
                    {exercise.name}
                  </h2>
                  <p className="text-muted-foreground text-sm">
                    {exercise.muscleGroup
                      ? muscleLabel(exercise.muscleGroup)
                      : ''}
                  </p>
                  {exercise.target && (
                    <p className="text-muted-foreground mt-1 text-xs">
                      Meta: {exercise.target.sets} ×{' '}
                      {formatReps(
                        exercise.target.reps_min,
                        exercise.target.reps_max
                      )}
                      {exercise.target.target_weight_kg !== null &&
                        ` · ${formatWeight(exercise.target.target_weight_kg)}`}
                      {exercise.target.rest_seconds !== null &&
                        ` · descanso ${formatRest(exercise.target.rest_seconds)}`}
                    </p>
                  )}
                </div>
              </div>

              <div className="mt-3">
                <ExerciseReplacement
                  mode="session"
                  name={exercise.name}
                  disabled={
                    busy !== null ||
                    !exercise.sets.some((set) => !set.completed)
                  }
                  onOpenChange={(open) => setBusy(open ? 'replace' : null)}
                  getContext={async () => {
                    if (timer.current !== null) {
                      window.clearTimeout(timer.current);
                      timer.current = null;
                    }
                    if (!(await persist())) {
                      throw new Error(
                        'Salve valores válidos nas séries antes de trocar o exercício.'
                      );
                    }
                    return {
                      mode: 'session',
                      session_id: session.id,
                      exercise_id: exercise.exerciseId,
                    };
                  }}
                  onApplied={(option, result) => {
                    if (!result?.session) {
                      throw new Error(
                        'A sessão atualizada não foi recebida. Recarregue o treino.'
                      );
                    }
                    const updated = rowsFromSession(result.session);
                    rowsRef.current = updated;
                    setRows(updated);
                    setSaveState('saved');
                    setRestEnd(null);
                    setExerciseIndex(
                      Math.max(
                        0,
                        updated.findIndex(
                          (item) => item.exerciseId === option.exercise.id
                        )
                      )
                    );
                    toast.success(
                      'Séries restantes e plano atualizados. Revise a carga do novo exercício.'
                    );
                  }}
                />
              </div>

              {exercise.target?.notes && (
                <p className="text-muted-foreground mt-2 text-xs italic">
                  {exercise.target.notes}
                </p>
              )}

              <div className="mt-4 space-y-2">
                <div className="text-muted-foreground grid grid-cols-[1.5rem_minmax(0,1fr)_minmax(0,1fr)_2.75rem_2.75rem] items-center gap-1 px-1 text-xs font-medium sm:gap-2">
                  <span>Série</span>
                  <span>Carga (kg)</span>
                  <span>Reps</span>
                  <span className="sr-only">Concluir</span>
                  <span className="sr-only">Remover</span>
                </div>
                {exercise.sets.map((set, index) => {
                  const weightInvalid = parseWeight(set.weight) === undefined;
                  const repsInvalid = parseReps(set.reps) === null;
                  return (
                    <div
                      key={set.key}
                      className={cn(
                        'grid grid-cols-[1.5rem_minmax(0,1fr)_minmax(0,1fr)_2.75rem_2.75rem] items-center gap-1 rounded-lg p-1 transition-colors sm:gap-2',
                        set.completed && 'bg-primary/10'
                      )}
                    >
                      <span className="text-muted-foreground text-center text-sm font-medium tabular-nums">
                        {index + 1}
                      </span>
                      <Input
                        value={set.weight}
                        inputMode="decimal"
                        placeholder="—"
                        aria-label={`Carga da série ${index + 1} de ${exercise.name}`}
                        aria-invalid={weightInvalid}
                        onChange={(event) =>
                          patchSet(exercise.exerciseId, set.key, {
                            weight: event.target.value,
                          })
                        }
                        className="h-12 text-center text-lg"
                      />
                      <Input
                        value={set.reps}
                        inputMode="numeric"
                        aria-label={`Repetições da série ${index + 1} de ${exercise.name}`}
                        aria-invalid={repsInvalid}
                        onChange={(event) =>
                          patchSet(exercise.exerciseId, set.key, {
                            reps: event.target.value,
                          })
                        }
                        className="h-12 text-center text-lg"
                      />
                      <button
                        type="button"
                        aria-pressed={set.completed}
                        aria-label={`${set.completed ? 'Desmarcar' : 'Concluir'} série ${index + 1} de ${exercise.name}`}
                        onClick={() => toggleSet(exercise, set, Date.now())}
                        disabled={restEnabled === null}
                        className={cn(
                          'flex size-11 items-center justify-center rounded-lg border transition-colors',
                          set.completed
                            ? 'bg-primary text-primary-foreground border-primary'
                            : 'text-muted-foreground hover:border-primary hover:text-primary'
                        )}
                      >
                        <Check className="size-5" />
                      </button>
                      <button
                        type="button"
                        aria-label={`Remover série ${index + 1} de ${exercise.name}`}
                        onClick={() => removeSet(exercise.exerciseId, set.key)}
                        className="text-muted-foreground hover:text-destructive flex size-11 items-center justify-center rounded-md"
                      >
                        <X className="size-4" />
                      </button>
                    </div>
                  );
                })}
              </div>

              <Button
                variant="ghost"
                size="sm"
                className="mt-2"
                onClick={() => addSet(exercise.exerciseId)}
                disabled={exercise.sets.length >= 100 || total >= 500}
              >
                <Plus /> Adicionar série
              </Button>
            </section>
          ))}
        </fieldset>
        {activeExercise && (
          <ExerciseProgress
            key={activeExercise.exerciseId}
            exerciseId={activeExercise.exerciseId}
            currentWeightKg={
              currentWeights.length ? Math.max(...currentWeights) : null
            }
          />
        )}
        {saveState === 'error' && (
          <Button variant="outline" onClick={() => void persist()}>
            Tentar salvar novamente
          </Button>
        )}

        <div className="bg-background fixed inset-x-0 bottom-[var(--mobile-nav-height)] z-30 grid grid-cols-2 gap-2 border-t py-3 pr-[max(1rem,env(safe-area-inset-right))] pl-[max(1rem,env(safe-area-inset-left))] md:static md:flex md:flex-wrap md:justify-between md:gap-3 md:border-0 md:px-0 md:pt-2">
          <Button
            variant="outline"
            className="text-destructive"
            onClick={() => setCancelOpen(true)}
            disabled={busy !== null}
          >
            <Trash2 /> <span className="md:hidden">Cancelar</span>
            <span className="hidden md:inline">Cancelar treino</span>
          </Button>
          <Button
            size="lg"
            onClick={() => setFinishOpen(true)}
            disabled={done === 0 || busy !== null}
          >
            <Check /> <span className="md:hidden">Finalizar</span>
            <span className="hidden md:inline">Finalizar treino</span>
          </Button>
        </div>
      </div>

      <Dialog
        open={finishOpen}
        onOpenChange={(open) => !busy && setFinishOpen(open)}
      >
        <DialogContent className="max-w-md">
          <div className="space-y-5 p-6">
            <div className="space-y-1 pr-8">
              <DialogTitle>Finalizar treino</DialogTitle>
              <DialogDescription>
                {done} {done === 1 ? 'série concluída' : 'séries concluídas'}.
                As séries não marcadas não entram no histórico.
              </DialogDescription>
            </div>

            <div className="space-y-2">
              <p className="text-sm font-medium">
                Como foi o esforço?{' '}
                <span className="text-muted-foreground font-normal">
                  (1 leve · 10 máximo)
                </span>
              </p>
              <div
                role="group"
                aria-label="Esforço percebido"
                className="grid grid-cols-5 gap-2"
              >
                {Array.from({ length: 10 }, (_, index) => index + 1).map(
                  (value) => (
                    <button
                      type="button"
                      key={value}
                      aria-pressed={effort === value}
                      onClick={() => setEffort(effort === value ? null : value)}
                      className={cn(
                        'h-10 rounded-lg border text-sm font-medium transition-colors',
                        effort === value
                          ? 'bg-primary text-primary-foreground border-primary'
                          : 'text-muted-foreground hover:text-foreground'
                      )}
                    >
                      {value}
                    </button>
                  )
                )}
              </div>
            </div>

            <textarea
              value={notes}
              onChange={(event) => setNotes(event.target.value)}
              rows={3}
              maxLength={2000}
              aria-label="Observações do treino"
              placeholder="Observações (opcional): como se sentiu, dores, ajustes…"
              className="border-input bg-elevated placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-ring/50 w-full rounded-md border px-3 py-2 text-sm shadow-xs outline-none focus-visible:ring-[3px]"
            />

            <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
              <Button
                variant="outline"
                onClick={() => setFinishOpen(false)}
                disabled={busy !== null}
              >
                Voltar
              </Button>
              <Button onClick={finish} disabled={busy !== null}>
                {busy === 'finish' ? 'Finalizando…' : 'Finalizar'}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      <ConfirmDialog
        open={cancelOpen}
        title="Cancelar este treino?"
        description="O que você registrou nesta sessão será descartado e não aparecerá no histórico."
        confirmLabel="Cancelar treino"
        destructive
        pending={busy === 'cancel'}
        onCancel={() => setCancelOpen(false)}
        onConfirm={cancel}
      />
    </div>
  );
}
