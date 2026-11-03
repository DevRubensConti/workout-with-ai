import { nextKey } from '@/lib/workouts';

export interface SetLog {
  exercise_id: string;
  set_number: number;
  reps: number;
  weight_kg: number | null;
  completed: boolean;
}

export interface SessionTarget {
  sets: number;
  reps_min: number;
  reps_max: number | null;
  target_weight_kg: number | null;
  rest_seconds: number | null;
  notes: string | null;
}

export interface SessionExercise {
  exercise_id: string;
  name: string;
  muscle_group: string | null;
  images: string[];
  target: SessionTarget | null;
  sets: SetLog[];
}

export interface SessionSummary {
  id: string;
  plan_id: string | null;
  plan_name: string | null;
  day_id: string | null;
  day_name: string | null;
  started_at: string;
  finished_at: string | null;
  notes: string | null;
  perceived_effort: number | null;
  total_sets: number;
  completed_sets: number;
  volume_kg: number;
  duration_seconds: number | null;
}

export interface SessionDetail extends SessionSummary {
  exercises: SessionExercise[];
}

export interface SessionListResponse {
  items: SessionSummary[];
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
}

export function formatDuration(seconds: number) {
  const minutes = Math.round(seconds / 60);
  if (seconds < 60) return `${seconds}s`;
  if (minutes < 60) return `${minutes}min`;
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  return rest ? `${hours}h ${String(rest).padStart(2, '0')}min` : `${hours}h`;
}

// Cronômetro: mm:ss, ou h:mm:ss a partir de uma hora.
export function formatClock(seconds: number) {
  const safe = Math.max(0, Math.floor(seconds));
  const hours = Math.floor(safe / 3600);
  const minutes = Math.floor((safe % 3600) / 60);
  const rest = String(safe % 60).padStart(2, '0');
  return hours > 0
    ? `${hours}:${String(minutes).padStart(2, '0')}:${rest}`
    : `${minutes}:${rest}`;
}

export function formatVolume(kg: number) {
  return `${kg.toLocaleString('pt-BR', { maximumFractionDigits: 0 })} kg`;
}

// Datas sem fuso (ex.: SQLite) são tratadas como UTC; o Postgres já envia o fuso.
export function parseApiDate(iso: string) {
  return new Date(/(Z|[+-]\d{2}:?\d{2})$/.test(iso) ? iso : `${iso}Z`);
}

export function formatDateTime(iso: string) {
  const date = parseApiDate(iso);
  const day = date.toLocaleDateString('pt-BR', {
    weekday: 'short',
    day: '2-digit',
    month: '2-digit',
  });
  const time = date.toLocaleTimeString('pt-BR', {
    hour: '2-digit',
    minute: '2-digit',
  });
  return `${day} · ${time}`;
}

export function formatSetLog(set: Pick<SetLog, 'reps' | 'weight_kg'>) {
  const weight =
    set.weight_kg !== null
      ? `${set.weight_kg.toLocaleString('pt-BR', { maximumFractionDigits: 2 })} kg`
      : 'Peso do corpo';
  return `${weight} × ${set.reps}`;
}

// Estado editável de uma série: números como texto para permitir campos vazios.
export interface SetRow {
  key: string;
  reps: string;
  weight: string;
  completed: boolean;
}

export interface ExerciseRows {
  exerciseId: string;
  name: string;
  muscleGroup: string | null;
  images: string[];
  target: SessionTarget | null;
  sets: SetRow[];
}

export function rowsFromSession(detail: SessionDetail): ExerciseRows[] {
  return detail.exercises.map((exercise) => ({
    exerciseId: exercise.exercise_id,
    name: exercise.name,
    muscleGroup: exercise.muscle_group,
    images: exercise.images,
    target: exercise.target,
    sets: exercise.sets.map((set) => ({
      key: nextKey(),
      reps: String(set.reps),
      weight: set.weight_kg !== null ? String(set.weight_kg) : '',
      completed: set.completed,
    })),
  }));
}

export function parseReps(value: string) {
  const text = value.trim();
  if (!/^\d+$/.test(text)) return null;
  const reps = Number(text);
  return reps <= 1000 ? reps : null;
}

export function parseWeight(value: string) {
  const text = value.trim().replace(',', '.');
  if (text === '') return null;
  if (!/^\d+(\.\d{1,2})?$/.test(text)) return undefined;
  const weight = Number(text);
  return weight <= 9999.99 ? weight : undefined;
}

export type SetPayload = {
  exercise_id: string;
  set_number: number;
  reps: number;
  weight_kg: number | null;
  completed: boolean;
};

// Só envia ao servidor quando todos os campos são válidos; senão devolve null.
export function rowsToPayload(rows: ExerciseRows[]): SetPayload[] | null {
  const payload: SetPayload[] = [];
  for (const exercise of rows) {
    for (const [index, set] of exercise.sets.entries()) {
      const reps = parseReps(set.reps);
      const weight = parseWeight(set.weight);
      if (reps === null || weight === undefined) return null;
      payload.push({
        exercise_id: exercise.exerciseId,
        set_number: index + 1,
        reps,
        weight_kg: weight,
        completed: set.completed,
      });
    }
  }
  return payload;
}
