'use client';

import {
  ArrowDown,
  ArrowLeft,
  ArrowRight,
  ArrowUp,
  Plus,
  Save,
  Trash2,
} from 'lucide-react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useState } from 'react';
import { toast } from 'sonner';

import { ConfirmDialog } from '@/components/confirm-dialog';
import { ExerciseImage } from '@/components/exercises/exercise-image';
import { ExercisePicker } from '@/components/workouts/exercise-picker';
import { ExerciseReplacement } from '@/components/workouts/exercise-replacement';
import { GenerationPanel } from '@/components/workouts/generation-panel';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { ApiError, apiFetch } from '@/lib/api';
import { muscleLabel, type ExerciseSummary } from '@/lib/exercises';
import { aiMetadata, type GenerationInfo } from '@/lib/generator';
import {
  GOAL_SUGGESTIONS,
  LEVEL_OPTIONS,
  dayName,
  draftFromPlan,
  draftToPayload,
  emptyDraft,
  nextKey,
  validateDraft,
  type Draft,
  type DraftDay,
  type DraftExercise,
  type PlanDetail,
} from '@/lib/workouts';
import { cn } from '@/lib/utils';

const MAX_DAYS = 14;

function move<T>(items: T[], index: number, delta: number): T[] {
  const target = index + delta;
  if (target < 0 || target >= items.length) return items;
  const copy = [...items];
  [copy[index], copy[target]] = [copy[target], copy[index]];
  return copy;
}

interface FieldProps {
  label: string;
  value: string;
  onChange: (value: string) => void;
  inputMode?: 'numeric' | 'decimal';
  placeholder?: string;
}

function NumberField({
  label,
  value,
  onChange,
  inputMode = 'numeric',
  placeholder,
}: FieldProps) {
  return (
    <label className="space-y-1">
      <span className="text-muted-foreground text-xs font-medium">{label}</span>
      <Input
        value={value}
        onChange={(event) => onChange(event.target.value)}
        inputMode={inputMode}
        placeholder={placeholder}
        className="h-9"
      />
    </label>
  );
}

interface WorkoutBuilderProps {
  plan?: PlanDetail;
  // Rascunho gerado por regras: o usuário revisa e salva como um treino novo.
  initialDraft?: Draft;
  generation?: GenerationInfo;
  onRestart?: () => void;
}

export function WorkoutBuilder({
  plan,
  initialDraft,
  generation,
  onRestart,
}: WorkoutBuilderProps) {
  const router = useRouter();
  const editing = Boolean(plan);
  const [draft, setDraft] = useState<Draft>(() =>
    plan ? draftFromPlan(plan) : (initialDraft ?? emptyDraft())
  );
  const [activeDay, setActiveDay] = useState(0);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [dayToRemove, setDayToRemove] = useState<number | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const dayIndex = Math.min(activeDay, draft.days.length - 1);
  const day = draft.days[dayIndex];
  const totalExercises = draft.days.reduce(
    (sum, item) => sum + item.exercises.length,
    0
  );

  function patchDraft(patch: Partial<Draft>) {
    setDraft((current) => ({ ...current, ...patch }));
  }

  function patchDay(index: number, patch: Partial<DraftDay>) {
    setDraft((current) => ({
      ...current,
      days: current.days.map((item, i) =>
        i === index ? { ...item, ...patch } : item
      ),
    }));
  }

  function patchExercise(
    index: number,
    key: string,
    patch: Partial<DraftExercise>
  ) {
    setDraft((current) => ({
      ...current,
      days: current.days.map((item, i) =>
        i === index
          ? {
              ...item,
              exercises: item.exercises.map((entry) =>
                entry.key === key ? { ...entry, ...patch } : entry
              ),
            }
          : item
      ),
    }));
  }

  function addDay() {
    if (draft.days.length >= MAX_DAYS) return;
    setDraft((current) => ({
      ...current,
      days: [
        ...current.days,
        {
          key: nextKey(),
          name: dayName(current.days.length),
          notes: '',
          exercises: [],
        },
      ],
    }));
    setActiveDay(draft.days.length);
  }

  function removeDay(index: number) {
    setDraft((current) => ({
      ...current,
      days: current.days.filter((_, i) => i !== index),
    }));
    setActiveDay(Math.max(0, Math.min(index, draft.days.length - 2)));
    setDayToRemove(null);
  }

  function moveDay(index: number, delta: number) {
    setDraft((current) => ({
      ...current,
      days: move(current.days, index, delta),
    }));
    setActiveDay(index + delta);
  }

  function addExercise(exercise: ExerciseSummary) {
    const entry: DraftExercise = {
      key: nextKey(),
      exercise: {
        id: exercise.id,
        name: exercise.name,
        muscle_group: exercise.muscle_group,
        equipment: exercise.equipment,
        images: exercise.images,
      },
      sets: '3',
      repsMin: '8',
      repsMax: '12',
      weight: '',
      rest: '60',
      tempo: null,
      notes: '',
    };
    setDraft((current) => ({
      ...current,
      days: current.days.map((item, i) =>
        i === dayIndex
          ? { ...item, exercises: [...item.exercises, entry] }
          : item
      ),
    }));
  }

  function removeExercise(key: string) {
    patchDay(dayIndex, {
      exercises: day.exercises.filter((entry) => entry.key !== key),
    });
  }

  async function save() {
    const problem = validateDraft(draft);
    setError(problem);
    if (problem) {
      toast.error(problem);
      return;
    }

    setSaving(true);
    try {
      const body = {
        ...draftToPayload(draft),
        ...(generation && !plan
          ? { source: 'ai', ai_metadata: aiMetadata(generation) }
          : {}),
      };
      const saved = plan
        ? await apiFetch<PlanDetail>(`/workouts/${plan.id}`, {
            method: 'PUT',
            body,
          })
        : await apiFetch<PlanDetail>('/workouts', { method: 'POST', body });
      toast.success(
        editing ? 'Treino atualizado.' : 'Treino criado e ativado.'
      );
      router.push(`/workouts/${saved.id}`);
      router.refresh();
    } catch (caught) {
      const message =
        caught instanceof ApiError
          ? caught.message
          : 'Não foi possível salvar o treino.';
      setError(message);
      toast.error(message);
      setSaving(false);
    }
  }

  return (
    <div className="container mx-auto max-w-4xl min-w-0 space-y-6 px-4 py-6 md:px-6 md:py-8">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          {onRestart ? (
            <button
              type="button"
              onClick={onRestart}
              className="text-muted-foreground hover:text-foreground inline-flex items-center gap-1 text-sm"
            >
              <ArrowLeft className="size-4" /> Refazer questionário
            </button>
          ) : (
            <Link
              href={plan ? `/workouts/${plan.id}` : '/workouts'}
              className="text-muted-foreground hover:text-foreground inline-flex items-center gap-1 text-sm"
            >
              <ArrowLeft className="size-4" /> Voltar
            </Link>
          )}
          <h1 className="mt-1 text-2xl font-bold tracking-tight">
            {editing
              ? 'Editar treino'
              : generation
                ? 'Revisar treino sugerido'
                : 'Novo treino'}
          </h1>
        </div>
        <Button
          className="w-full sm:w-auto"
          onClick={save}
          disabled={saving}
          size="lg"
        >
          <Save /> {saving ? 'Salvando…' : 'Salvar treino'}
        </Button>
      </div>

      {error && (
        <p
          role="alert"
          className="bg-destructive/10 text-destructive border-destructive/30 rounded-lg border px-4 py-3 text-sm"
        >
          {error}
        </p>
      )}

      {generation && <GenerationPanel info={generation.info} mode="draft" />}

      <Card>
        <CardHeader>
          <CardTitle>Informações</CardTitle>
          <CardDescription>
            {editing
              ? 'Ajuste os dados gerais do treino.'
              : 'Ao salvar, este treino passa a ser o seu treino atual.'}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="plan-name">Nome do treino</Label>
            <Input
              id="plan-name"
              value={draft.name}
              maxLength={160}
              placeholder="Ex.: Hipertrofia ABC"
              onChange={(event) => patchDraft({ name: event.target.value })}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="plan-goal">Objetivo</Label>
            <Input
              id="plan-goal"
              value={draft.goal}
              maxLength={80}
              placeholder="Ex.: Hipertrofia"
              onChange={(event) => patchDraft({ goal: event.target.value })}
            />
            <div className="flex flex-wrap gap-2">
              {GOAL_SUGGESTIONS.map((goal) => (
                <button
                  type="button"
                  key={goal}
                  onClick={() => patchDraft({ goal })}
                  className={cn(
                    'rounded-full border px-3 py-1 text-xs transition-colors',
                    draft.goal === goal
                      ? 'bg-primary text-primary-foreground border-primary'
                      : 'text-muted-foreground hover:text-foreground'
                  )}
                >
                  {goal}
                </button>
              ))}
            </div>
          </div>

          <div className="space-y-2">
            <Label>Nível</Label>
            <div
              role="group"
              aria-label="Nível"
              className="flex flex-wrap gap-2"
            >
              {[
                { value: '' as const, label: 'Não definido' },
                ...LEVEL_OPTIONS,
              ].map((option) => (
                <button
                  type="button"
                  key={option.value || 'none'}
                  aria-pressed={draft.level === option.value}
                  onClick={() => patchDraft({ level: option.value })}
                  className={cn(
                    'rounded-full border px-3.5 py-1.5 text-sm transition-colors',
                    draft.level === option.value
                      ? 'bg-primary text-primary-foreground border-primary'
                      : 'text-muted-foreground hover:text-foreground'
                  )}
                >
                  {option.label}
                </button>
              ))}
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="plan-description">Descrição (opcional)</Label>
            <textarea
              id="plan-description"
              value={draft.description}
              maxLength={2000}
              rows={3}
              onChange={(event) =>
                patchDraft({ description: event.target.value })
              }
              placeholder="Anotações sobre o foco, frequência semanal, etc."
              className="border-input bg-elevated placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-ring/50 w-full rounded-md border px-3 py-2 text-sm shadow-xs outline-none focus-visible:ring-[3px]"
            />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Dias de treino</CardTitle>
          <CardDescription>
            {draft.days.length} {draft.days.length === 1 ? 'dia' : 'dias'} ·{' '}
            {totalExercises} {totalExercises === 1 ? 'exercício' : 'exercícios'}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-5">
          <div
            role="tablist"
            aria-label="Dias do treino"
            className="flex gap-2 overflow-x-auto pb-1 [&::-webkit-scrollbar]:hidden"
          >
            {draft.days.map((item, index) => (
              <button
                type="button"
                role="tab"
                key={item.key}
                aria-selected={index === dayIndex}
                onClick={() => setActiveDay(index)}
                className={cn(
                  'shrink-0 rounded-lg border px-4 py-2 text-sm font-medium whitespace-nowrap transition-colors',
                  index === dayIndex
                    ? 'bg-primary text-primary-foreground border-primary'
                    : 'text-muted-foreground hover:text-foreground'
                )}
              >
                {item.name.trim() || `Dia ${index + 1}`}
              </button>
            ))}
            {draft.days.length < MAX_DAYS && (
              <button
                type="button"
                onClick={addDay}
                className="text-primary hover:bg-accent inline-flex shrink-0 items-center gap-1 rounded-lg border border-dashed px-3 py-2 text-sm font-medium"
              >
                <Plus className="size-4" /> Dia
              </button>
            )}
          </div>

          <div className="space-y-4" role="tabpanel">
            <div className="flex flex-wrap items-end gap-3">
              <div className="w-full min-w-0 flex-1 basis-48 space-y-2">
                <Label htmlFor="day-name">Nome do dia</Label>
                <Input
                  id="day-name"
                  value={day.name}
                  maxLength={80}
                  onChange={(event) =>
                    patchDay(dayIndex, { name: event.target.value })
                  }
                />
              </div>
              <div className="flex gap-1">
                <Button
                  variant="outline"
                  size="icon"
                  aria-label="Mover dia para a esquerda"
                  disabled={dayIndex === 0}
                  onClick={() => moveDay(dayIndex, -1)}
                >
                  <ArrowLeft />
                </Button>
                <Button
                  variant="outline"
                  size="icon"
                  aria-label="Mover dia para a direita"
                  disabled={dayIndex === draft.days.length - 1}
                  onClick={() => moveDay(dayIndex, 1)}
                >
                  <ArrowRight />
                </Button>
                <Button
                  variant="outline"
                  size="icon"
                  aria-label="Remover dia"
                  disabled={draft.days.length === 1}
                  onClick={() => setDayToRemove(dayIndex)}
                  className="text-destructive"
                >
                  <Trash2 />
                </Button>
              </div>
            </div>

            <Input
              value={day.notes}
              maxLength={1000}
              placeholder="Observações do dia (opcional)"
              aria-label="Observações do dia"
              onChange={(event) =>
                patchDay(dayIndex, { notes: event.target.value })
              }
            />

            {day.exercises.length === 0 ? (
              <div className="text-muted-foreground flex flex-col items-center gap-3 rounded-xl border border-dashed px-6 py-10 text-center text-sm">
                Nenhum exercício neste dia ainda.
                <Button onClick={() => setPickerOpen(true)}>
                  <Plus /> Adicionar exercícios
                </Button>
              </div>
            ) : (
              <>
                <ol className="space-y-3">
                  {day.exercises.map((entry, index) => (
                    <li
                      key={entry.key}
                      className="bg-card rounded-xl border p-3 md:p-4"
                    >
                      <div className="flex flex-wrap items-start gap-2 sm:gap-3">
                        <span className="bg-accent text-accent-foreground mt-1 flex size-6 shrink-0 items-center justify-center rounded-full text-xs font-semibold">
                          {index + 1}
                        </span>
                        <span className="bg-muted relative h-12 w-14 shrink-0 overflow-hidden rounded-md sm:w-16">
                          <ExerciseImage
                            key={entry.exercise.images[0] ?? 'empty'}
                            path={entry.exercise.images[0]}
                            alt=""
                            sizes="64px"
                          />
                        </span>
                        <div className="min-w-0 flex-1 basis-24">
                          <p className="text-sm font-medium sm:text-base">
                            {entry.exercise.name}
                          </p>
                          <p className="text-muted-foreground text-sm">
                            {muscleLabel(entry.exercise.muscle_group)}
                          </p>
                        </div>
                        <div className="flex w-full shrink-0 flex-wrap justify-end gap-1 border-t pt-1 sm:w-auto sm:border-0 sm:pt-0">
                          <ExerciseReplacement
                            mode="draft"
                            name={entry.exercise.name}
                            disabled={saving}
                            getContext={() => {
                              const problem = validateDraft(draft);
                              if (problem) throw new Error(problem);
                              return {
                                mode: 'draft',
                                workout: draftToPayload(draft),
                                day_index: dayIndex,
                                exercise_index: index,
                              };
                            }}
                            onApplied={(option) => {
                              patchExercise(dayIndex, entry.key, {
                                exercise: option.exercise,
                                weight: '',
                                tempo: null,
                                notes: '',
                              });
                              toast.success(
                                'Exercício trocado no rascunho. Salve para confirmar.'
                              );
                            }}
                          />
                          <Button
                            variant="ghost"
                            size="icon"
                            aria-label="Mover exercício para cima"
                            disabled={index === 0}
                            onClick={() =>
                              patchDay(dayIndex, {
                                exercises: move(day.exercises, index, -1),
                              })
                            }
                          >
                            <ArrowUp />
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            aria-label="Mover exercício para baixo"
                            disabled={index === day.exercises.length - 1}
                            onClick={() =>
                              patchDay(dayIndex, {
                                exercises: move(day.exercises, index, 1),
                              })
                            }
                          >
                            <ArrowDown />
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            aria-label={`Remover ${entry.exercise.name}`}
                            className="text-destructive"
                            onClick={() => removeExercise(entry.key)}
                          >
                            <Trash2 />
                          </Button>
                        </div>
                      </div>

                      <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-5">
                        <NumberField
                          label="Séries"
                          value={entry.sets}
                          onChange={(value) =>
                            patchExercise(dayIndex, entry.key, { sets: value })
                          }
                        />
                        <NumberField
                          label="Reps mín."
                          value={entry.repsMin}
                          onChange={(value) =>
                            patchExercise(dayIndex, entry.key, {
                              repsMin: value,
                            })
                          }
                        />
                        <NumberField
                          label="Reps máx."
                          value={entry.repsMax}
                          placeholder="opcional"
                          onChange={(value) =>
                            patchExercise(dayIndex, entry.key, {
                              repsMax: value,
                            })
                          }
                        />
                        <NumberField
                          label="Carga (kg)"
                          value={entry.weight}
                          inputMode="decimal"
                          placeholder="opcional"
                          onChange={(value) =>
                            patchExercise(dayIndex, entry.key, {
                              weight: value,
                            })
                          }
                        />
                        <NumberField
                          label="Descanso (s)"
                          value={entry.rest}
                          placeholder="opcional"
                          onChange={(value) =>
                            patchExercise(dayIndex, entry.key, { rest: value })
                          }
                        />
                      </div>

                      <Input
                        value={entry.notes}
                        maxLength={1000}
                        placeholder="Observações (opcional)"
                        aria-label={`Observações de ${entry.exercise.name}`}
                        className="mt-3 h-9"
                        onChange={(event) =>
                          patchExercise(dayIndex, entry.key, {
                            notes: event.target.value,
                          })
                        }
                      />
                    </li>
                  ))}
                </ol>
                <Button variant="outline" onClick={() => setPickerOpen(true)}>
                  <Plus /> Adicionar exercícios
                </Button>
              </>
            )}
          </div>
        </CardContent>
      </Card>

      <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
        <Button variant="outline" asChild>
          <Link href={plan ? `/workouts/${plan.id}` : '/workouts'}>
            Cancelar
          </Link>
        </Button>
        <Button onClick={save} disabled={saving}>
          <Save /> {saving ? 'Salvando…' : 'Salvar treino'}
        </Button>
      </div>

      <ExercisePicker
        open={pickerOpen}
        onOpenChange={setPickerOpen}
        onAdd={addExercise}
      />

      <ConfirmDialog
        open={dayToRemove !== null}
        title="Remover este dia?"
        description={
          dayToRemove !== null && draft.days[dayToRemove]?.exercises.length
            ? 'Os exercícios deste dia também serão removidos do treino.'
            : 'O dia será removido do treino.'
        }
        confirmLabel="Remover dia"
        destructive
        onCancel={() => setDayToRemove(null)}
        onConfirm={() => dayToRemove !== null && removeDay(dayToRemove)}
      />
    </div>
  );
}
