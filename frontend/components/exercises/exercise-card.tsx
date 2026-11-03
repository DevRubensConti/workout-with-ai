import { ExerciseImage } from '@/components/exercises/exercise-image';
import {
  equipmentLabel,
  levelBadgeClass,
  levelLabel,
  muscleLabel,
  type ExerciseSummary,
} from '@/lib/exercises';
import { cn } from '@/lib/utils';

interface ExerciseCardProps {
  exercise: ExerciseSummary;
  onSelect: (id: string) => void;
}

const CARD_SIZES = '(min-width: 1280px) 22vw, (min-width: 768px) 30vw, 90vw';

export function ExerciseCard({ exercise, onSelect }: ExerciseCardProps) {
  const [first, second] = exercise.images;

  return (
    <button
      type="button"
      onClick={() => onSelect(exercise.id)}
      className="group focus-visible:ring-ring/60 bg-card flex h-full flex-col overflow-hidden rounded-xl border text-left shadow-sm transition duration-200 outline-none hover:-translate-y-0.5 hover:shadow-lg focus-visible:ring-[3px]"
    >
      <div className="bg-muted relative aspect-[3/2] overflow-hidden">
        <ExerciseImage
          key={first ?? 'empty'}
          path={first}
          alt={exercise.name}
          sizes={CARD_SIZES}
          className="transition-opacity duration-300"
        />
        {second && (
          // A segunda imagem mostra a outra fase do movimento ao passar o mouse.
          <ExerciseImage
            key={second}
            path={second}
            alt=""
            sizes={CARD_SIZES}
            className="opacity-0 transition-opacity duration-300 group-hover:opacity-100 group-focus-visible:opacity-100"
          />
        )}
        {exercise.level && (
          <span
            className={cn(
              'absolute top-2 left-2 rounded-full px-2.5 py-1 text-xs font-medium backdrop-blur',
              levelBadgeClass(exercise.level)
            )}
          >
            {levelLabel(exercise.level)}
          </span>
        )}
      </div>

      <div className="flex flex-1 flex-col gap-2 p-4">
        <h3 className="group-hover:text-primary line-clamp-2 leading-snug font-semibold transition-colors">
          {exercise.name}
        </h3>
        <p className="text-muted-foreground mt-auto flex flex-wrap gap-x-2 text-sm">
          <span>{muscleLabel(exercise.muscle_group)}</span>
          {exercise.equipment && (
            <>
              <span aria-hidden>·</span>
              <span>{equipmentLabel(exercise.equipment)}</span>
            </>
          )}
        </p>
      </div>
    </button>
  );
}

export function ExerciseCardSkeleton() {
  return (
    <div
      aria-hidden
      className="bg-card animate-pulse overflow-hidden rounded-xl border"
    >
      <div className="bg-muted aspect-[3/2]" />
      <div className="space-y-3 p-4">
        <div className="bg-muted h-4 w-3/4 rounded" />
        <div className="bg-muted h-3 w-1/2 rounded" />
      </div>
    </div>
  );
}
