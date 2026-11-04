'use client';

import { ChevronLeft, ChevronRight } from 'lucide-react';
import { useState } from 'react';

import { ExerciseImage } from '@/components/exercises/exercise-image';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  categoryLabel,
  equipmentLabel,
  forceLabel,
  levelBadgeClass,
  levelLabel,
  mechanicLabel,
  muscleLabel,
  type ExerciseDetail,
  type ExerciseLocale,
  type ExerciseSummary,
} from '@/lib/exercises';
import { cn } from '@/lib/utils';

interface ExerciseDetailDialogProps {
  summary: ExerciseSummary | undefined;
  detail: ExerciseDetail | undefined;
  loading: boolean;
  error: string | undefined;
  locale: ExerciseLocale;
  onRetry: () => void;
  onClose: () => void;
  onPrevious?: () => void;
  onNext?: () => void;
}

export function ExerciseDetailDialog({
  summary,
  detail,
  loading,
  error,
  locale,
  onRetry,
  onClose,
  onPrevious,
  onNext,
}: ExerciseDetailDialogProps) {
  const exercise = detail ?? summary;

  return (
    <Dialog
      open={Boolean(exercise)}
      onOpenChange={(open) => !open && onClose()}
    >
      <DialogContent className="overflow-y-auto">
        {exercise && (
          <DetailBody
            key={exercise.id}
            exercise={exercise}
            detail={detail}
            loading={loading}
            error={error}
            locale={locale}
            onRetry={onRetry}
            onPrevious={onPrevious}
            onNext={onNext}
          />
        )}
      </DialogContent>
    </Dialog>
  );
}

interface DetailBodyProps {
  exercise: ExerciseSummary;
  detail: ExerciseDetail | undefined;
  loading: boolean;
  error: string | undefined;
  locale: ExerciseLocale;
  onRetry: () => void;
  onPrevious?: () => void;
  onNext?: () => void;
}

function DetailBody({
  exercise,
  detail,
  loading,
  error,
  locale,
  onRetry,
  onPrevious,
  onNext,
}: DetailBodyProps) {
  const [activeImage, setActiveImage] = useState(0);
  const images = exercise.images;
  const infoRows = detail
    ? [
        detail.category && ['Categoria', categoryLabel(detail.category)],
        detail.force && ['Movimento', forceLabel(detail.force)],
        detail.mechanic && ['Mecânica', mechanicLabel(detail.mechanic)],
      ].filter((row): row is [string, string] => Boolean(row))
    : [];

  return (
    <div className="grid md:grid-cols-[minmax(0,1.05fr)_minmax(0,1fr)]">
      <div className="bg-muted/50 flex flex-col gap-3 p-4 md:p-6">
        <div className="bg-muted relative aspect-[3/2] overflow-hidden rounded-xl border">
          <ExerciseImage
            key={images[activeImage] ?? 'empty'}
            path={images[activeImage]}
            alt={exercise.name}
            sizes="(min-width: 768px) 480px, 90vw"
            priority
          />
        </div>

        {images.length > 1 && (
          <div className="grid grid-cols-2 gap-3">
            {images.map((path, index) => (
              <button
                type="button"
                key={path}
                onClick={() => setActiveImage(index)}
                aria-label={`Ver posição ${index + 1}`}
                aria-pressed={activeImage === index}
                className={cn(
                  'focus-visible:ring-ring/60 bg-muted relative aspect-[3/2] overflow-hidden rounded-lg border-2 transition outline-none focus-visible:ring-[3px]',
                  activeImage === index
                    ? 'border-primary'
                    : 'border-transparent opacity-70 hover:opacity-100'
                )}
              >
                <ExerciseImage path={path} alt="" sizes="240px" />
                <span className="bg-overlay/70 text-overlay-foreground absolute bottom-1.5 left-1.5 rounded px-1.5 py-0.5 text-[11px] font-medium">
                  {index === 0 ? 'Início' : 'Final'}
                </span>
              </button>
            ))}
          </div>
        )}
      </div>

      <div className="flex flex-col gap-5 p-5 md:p-7">
        <header className="space-y-3 pr-10">
          <DialogTitle>{exercise.name}</DialogTitle>
          <DialogDescription asChild>
            <div className="flex flex-wrap gap-2">
              {exercise.level && (
                <span
                  className={cn(
                    'rounded-full px-2.5 py-1 text-xs font-medium',
                    levelBadgeClass(exercise.level)
                  )}
                >
                  {levelLabel(exercise.level)}
                </span>
              )}
              {exercise.equipment && (
                <span className="bg-muted text-foreground rounded-full px-2.5 py-1 text-xs font-medium">
                  {equipmentLabel(exercise.equipment)}
                </span>
              )}
              {detail?.locale === 'en' && locale === 'pt-BR' && (
                <span className="bg-muted text-muted-foreground rounded-full px-2.5 py-1 text-xs">
                  Conteúdo em inglês
                </span>
              )}
            </div>
          </DialogDescription>
        </header>

        {error ? (
          <div role="alert" className="space-y-2 text-sm">
            <p className="text-destructive">{error}</p>
            <button
              type="button"
              onClick={onRetry}
              className="text-primary font-medium hover:underline"
            >
              Tentar novamente
            </button>
          </div>
        ) : (
          <>
            {detail?.description && (
              <p className="text-muted-foreground text-sm leading-relaxed">
                {detail.description}
              </p>
            )}

            <section aria-labelledby="exercise-instructions">
              <h4
                id="exercise-instructions"
                className="mb-3 text-sm font-semibold tracking-wide uppercase"
              >
                Como executar
              </h4>
              {loading && !detail ? (
                <div aria-hidden className="animate-pulse space-y-3">
                  {[0, 1, 2].map((line) => (
                    <div key={line} className="bg-muted h-4 w-full rounded" />
                  ))}
                </div>
              ) : detail && detail.instructions.length > 0 ? (
                <ol className="space-y-3">
                  {detail.instructions.map((step, index) => (
                    <li
                      key={`${index}-${step}`}
                      className="flex gap-3 text-sm leading-relaxed"
                    >
                      <span className="bg-accent text-accent-foreground flex size-6 shrink-0 items-center justify-center rounded-full text-xs font-semibold">
                        {index + 1}
                      </span>
                      <span>{step}</span>
                    </li>
                  ))}
                </ol>
              ) : (
                <p className="text-muted-foreground text-sm">
                  Este exercício ainda não tem instruções cadastradas.
                </p>
              )}
            </section>

            {detail && (
              <section aria-labelledby="exercise-muscles" className="space-y-3">
                <h4
                  id="exercise-muscles"
                  className="text-sm font-semibold tracking-wide uppercase"
                >
                  Músculos
                </h4>
                <div className="flex flex-wrap gap-2">
                  {detail.primary_muscles.map((muscle) => (
                    <span
                      key={`primary-${muscle}`}
                      className="bg-primary text-primary-foreground rounded-full px-2.5 py-1 text-xs font-medium"
                    >
                      {muscleLabel(muscle)}
                    </span>
                  ))}
                  {detail.secondary_muscles.map((muscle) => (
                    <span
                      key={`secondary-${muscle}`}
                      className="bg-muted rounded-full px-2.5 py-1 text-xs"
                    >
                      {muscleLabel(muscle)}
                    </span>
                  ))}
                </div>
                {detail.secondary_muscles.length > 0 && (
                  <p className="text-muted-foreground text-xs">
                    Destaque: músculo principal. Cinza: apoio.
                  </p>
                )}
              </section>
            )}

            {infoRows.length > 0 && (
              <dl className="grid grid-cols-3 gap-3 border-t pt-4 text-sm">
                {infoRows.map(([term, value]) => (
                  <div key={term}>
                    <dt className="text-muted-foreground text-xs">{term}</dt>
                    <dd className="font-medium">{value}</dd>
                  </div>
                ))}
              </dl>
            )}
          </>
        )}

        {(onPrevious || onNext) && (
          <footer className="mt-auto flex items-center justify-between gap-3 border-t pt-4">
            <button
              type="button"
              onClick={onPrevious}
              disabled={!onPrevious}
              className="hover:bg-accent inline-flex h-9 items-center gap-1 rounded-md border px-3 text-sm transition-colors disabled:pointer-events-none disabled:opacity-40"
            >
              <ChevronLeft className="size-4" /> Anterior
            </button>
            <button
              type="button"
              onClick={onNext}
              disabled={!onNext}
              className="hover:bg-accent inline-flex h-9 items-center gap-1 rounded-md border px-3 text-sm transition-colors disabled:pointer-events-none disabled:opacity-40"
            >
              Próximo <ChevronRight className="size-4" />
            </button>
          </footer>
        )}
      </div>
    </div>
  );
}
