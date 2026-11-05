'use client';

import {
  ArrowLeft,
  Clock,
  Dumbbell,
  Flame,
  Layers,
  Trash2,
} from 'lucide-react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useState } from 'react';
import { toast } from 'sonner';

import { ConfirmDialog } from '@/components/confirm-dialog';
import { ConsistencyProgress } from '@/components/sessions/consistency-progress';
import { ExerciseProgress } from '@/components/sessions/exercise-progress';
import { ExerciseImageViewer } from '@/components/exercises/exercise-image-viewer';
import { Button } from '@/components/ui/button';
import { ApiError, apiFetch } from '@/lib/api';
import { muscleLabel } from '@/lib/exercises';
import {
  formatDateTime,
  formatDuration,
  formatSetLog,
  formatVolume,
  type SessionDetail,
} from '@/lib/sessions';

function Stat({
  icon: Icon,
  label,
  value,
}: {
  icon: typeof Clock;
  label: string;
  value: string;
}) {
  return (
    <div className="bg-data-surface rounded-xl border p-4">
      <Icon className="text-data mb-2 size-5" />
      <p className="text-data text-lg font-semibold tabular-nums sm:text-xl">
        {value}
      </p>
      <p className="text-muted-foreground text-xs">{label}</p>
    </div>
  );
}

export function SessionSummaryView({
  session,
  canWrite,
}: {
  session: SessionDetail;
  canWrite: boolean;
}) {
  const router = useRouter();
  const [confirming, setConfirming] = useState(false);
  const [deleting, setDeleting] = useState(false);

  async function remove() {
    setDeleting(true);
    try {
      await apiFetch(`/sessions/${session.id}`, { method: 'DELETE' });
      toast.success('Registro excluído.');
      router.push('/history');
      router.refresh();
    } catch (error) {
      toast.error(
        error instanceof ApiError
          ? error.message
          : 'Não foi possível excluir o registro.'
      );
      setDeleting(false);
      setConfirming(false);
    }
  }

  return (
    <div className="container mx-auto max-w-3xl space-y-6 px-4 py-8 md:px-6">
      <Link
        href="/history"
        className="text-muted-foreground hover:text-foreground inline-flex items-center gap-1 text-sm"
      >
        <ArrowLeft className="size-4" /> Histórico
      </Link>

      <header className="space-y-1">
        <h1 className="text-2xl font-bold tracking-tight md:text-3xl">
          {session.day_name ?? 'Treino'}
        </h1>
        <p className="text-muted-foreground text-sm">
          {session.plan_name ? `${session.plan_name} · ` : ''}
          {formatDateTime(session.started_at)}
        </p>
      </header>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat
          icon={Clock}
          label="Duração"
          value={
            session.duration_seconds !== null
              ? formatDuration(session.duration_seconds)
              : '—'
          }
        />
        <Stat
          icon={Layers}
          label="Séries concluídas"
          value={String(session.completed_sets)}
        />
        <Stat
          icon={Dumbbell}
          label="Volume total"
          value={session.volume_kg > 0 ? formatVolume(session.volume_kg) : '—'}
        />
        <Stat
          icon={Flame}
          label="Esforço percebido"
          value={
            session.perceived_effort !== null
              ? `${session.perceived_effort}/10`
              : '—'
          }
        />
      </div>

      {session.notes && (
        <p className="bg-muted/60 rounded-lg border px-4 py-3 text-sm">
          {session.notes}
        </p>
      )}

      <ConsistencyProgress />

      <ol className="space-y-3">
        {session.exercises.map((exercise) => (
          <li
            key={exercise.exercise_id}
            className="bg-card rounded-xl border p-4"
          >
            <div className="flex items-center gap-3">
              <span className="bg-muted relative h-12 w-16 shrink-0 overflow-hidden rounded-md">
                <ExerciseImageViewer
                  images={exercise.images}
                  alt={exercise.name}
                  sizes="64px"
                />
              </span>
              <div className="min-w-0">
                <p className="font-semibold">{exercise.name}</p>
                {exercise.muscle_group && (
                  <p className="text-muted-foreground text-sm">
                    {muscleLabel(exercise.muscle_group)}
                  </p>
                )}
              </div>
            </div>
            <ul className="mt-3 flex flex-wrap gap-2">
              {exercise.sets.map((set) => (
                <li
                  key={set.set_number}
                  className="bg-muted rounded-full px-3 py-1 text-xs font-medium"
                >
                  <span className="text-muted-foreground mr-1.5">
                    {set.set_number}
                  </span>
                  {formatSetLog(set)}
                </li>
              ))}
            </ul>
            <div className="mt-4">
              <ExerciseProgress exerciseId={exercise.exercise_id} collapsible />
            </div>
          </li>
        ))}
      </ol>

      {canWrite && (
        <div className="flex justify-end">
          <Button
            variant="outline"
            className="text-destructive"
            onClick={() => setConfirming(true)}
          >
            <Trash2 /> Excluir registro
          </Button>
        </div>
      )}

      <ConfirmDialog
        open={confirming}
        title="Excluir este registro?"
        description="Esse treino sairá do seu histórico. Essa ação não pode ser desfeita."
        confirmLabel="Excluir"
        destructive
        pending={deleting}
        onCancel={() => setConfirming(false)}
        onConfirm={remove}
      />
    </div>
  );
}
