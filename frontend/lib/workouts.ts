import type { ExerciseSummary } from '@/lib/exercises';

export type PlanLevel = 'beginner' | 'intermediate' | 'expert';
export type PlanStatus = 'active' | 'archived';

export interface PlanSummary {
  id: string;
  name: string;
  description: string | null;
  goal: string | null;
  level: PlanLevel | null;
  source: string;
  status: PlanStatus;
  started_at: string;
  archived_at: string | null;
  day_count: number;
  exercise_count: number;
}

export interface PlanExercise {
  id: string;
  exercise_id: string;
  exercise_name: string;
  muscle_group: string;
  equipment: string | null;
  images: string[];
  position: number;
  sets: number;
  reps_min: number;
  reps_max: number | null;
  target_weight_kg: number | null;
  rest_seconds: number | null;
  tempo: string | null;
  notes: string | null;
}

export interface PlanDay {
  id: string;
  name: string;
  position: number;
  notes: string | null;
  exercises: PlanExercise[];
}

export interface PlanDetail extends PlanSummary {
  ai_metadata?: Record<string, unknown> | null;
  days: PlanDay[];
}

export const GOAL_SUGGESTIONS = [
  'Hipertrofia',
  'Emagrecimento',
  'Força',
  'Resistência',
  'Condicionamento',
  'Saúde e bem-estar',
];

export const LEVEL_OPTIONS: { value: PlanLevel; label: string }[] = [
  { value: 'beginner', label: 'Iniciante' },
  { value: 'intermediate', label: 'Intermediário' },
  { value: 'expert', label: 'Avançado' },
];

export function formatReps(min: number, max: number | null) {
  return max !== null && max !== min ? `${min}–${max}` : `${min}`;
}

export function formatRest(seconds: number) {
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  const rest = seconds % 60;
  return rest ? `${minutes}min ${rest}s` : `${minutes}min`;
}

export function formatWeight(kg: number) {
  return `${kg.toLocaleString('pt-BR', { maximumFractionDigits: 2 })} kg`;
}

export function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString('pt-BR');
}

// Rascunho do formulário: números como texto para permitir campos vazios.
export interface DraftExercise {
  key: string;
  id?: string;
  exercise: Pick<
    ExerciseSummary,
    'id' | 'name' | 'muscle_group' | 'equipment' | 'images'
  >;
  sets: string;
  repsMin: string;
  repsMax: string;
  weight: string;
  rest: string;
  tempo: string | null;
  notes: string;
}

export interface DraftDay {
  key: string;
  id?: string;
  name: string;
  notes: string;
  exercises: DraftExercise[];
}

export interface Draft {
  name: string;
  description: string;
  goal: string;
  level: PlanLevel | '';
  days: DraftDay[];
}

let keyCounter = 0;
export const nextKey = () => `draft-${++keyCounter}`;

export function dayName(index: number) {
  const letter = String.fromCharCode(65 + (index % 26));
  return `Treino ${letter}`;
}

export function emptyDraft(): Draft {
  return {
    name: '',
    description: '',
    goal: '',
    level: '',
    days: [{ key: nextKey(), name: dayName(0), notes: '', exercises: [] }],
  };
}

export function draftFromPlan(plan: PlanDetail): Draft {
  return {
    name: plan.name,
    description: plan.description ?? '',
    goal: plan.goal ?? '',
    level: plan.level ?? '',
    days: plan.days.map((day) => ({
      key: nextKey(),
      id: day.id,
      name: day.name,
      notes: day.notes ?? '',
      exercises: day.exercises.map((item) => ({
        key: nextKey(),
        id: item.id,
        exercise: {
          id: item.exercise_id,
          name: item.exercise_name,
          muscle_group: item.muscle_group,
          equipment: item.equipment,
          images: item.images,
        },
        sets: String(item.sets),
        repsMin: String(item.reps_min),
        repsMax: item.reps_max !== null ? String(item.reps_max) : '',
        weight:
          item.target_weight_kg !== null ? String(item.target_weight_kg) : '',
        rest: item.rest_seconds !== null ? String(item.rest_seconds) : '',
        tempo: item.tempo,
        notes: item.notes ?? '',
      })),
    })),
  };
}

function parseInteger(value: string) {
  const text = value.trim();
  if (!/^\d+$/.test(text)) return null;
  return Number(text);
}

function parseDecimal(value: string) {
  const text = value.trim().replace(',', '.');
  if (!/^\d+(\.\d{1,2})?$/.test(text)) return null;
  return Number(text);
}

// Retorna a primeira mensagem de erro encontrada, ou null se o rascunho é válido.
export function validateDraft(draft: Draft): string | null {
  if (!draft.name.trim()) return 'Dê um nome ao treino.';

  for (const day of draft.days) {
    const label = day.name.trim() || 'Um dos dias';
    if (!day.name.trim()) return 'Todos os dias precisam de um nome.';
    if (day.exercises.length === 0) {
      return `Adicione ao menos um exercício em "${label}".`;
    }
    for (const item of day.exercises) {
      const where = `"${item.exercise.name}" (${label})`;
      const sets = parseInteger(item.sets);
      if (sets === null || sets < 1 || sets > 50) {
        return `Séries inválidas em ${where}: use de 1 a 50.`;
      }
      const repsMin = parseInteger(item.repsMin);
      if (repsMin === null || repsMin > 1000) {
        return `Repetições inválidas em ${where}.`;
      }
      if (item.repsMax.trim()) {
        const repsMax = parseInteger(item.repsMax);
        if (repsMax === null || repsMax < repsMin) {
          return `As repetições máximas devem ser maiores ou iguais às mínimas em ${where}.`;
        }
      }
      if (item.weight.trim()) {
        const weight = parseDecimal(item.weight);
        if (weight === null || weight > 9999.99) {
          return `Carga inválida em ${where}: use um número em kg.`;
        }
      }
      if (item.rest.trim()) {
        const rest = parseInteger(item.rest);
        if (rest === null || rest > 3600) {
          return `Descanso inválido em ${where}: use segundos, até 3600.`;
        }
      }
    }
  }
  return null;
}

export function draftToPayload(draft: Draft) {
  return {
    name: draft.name.trim(),
    description: draft.description.trim() || null,
    goal: draft.goal.trim() || null,
    level: draft.level || null,
    days: draft.days.map((day) => ({
      id: day.id,
      name: day.name.trim(),
      notes: day.notes.trim() || null,
      exercises: day.exercises.map((item) => ({
        id: item.id,
        exercise_id: item.exercise.id,
        sets: Number(item.sets),
        reps_min: Number(item.repsMin),
        reps_max: item.repsMax.trim() ? Number(item.repsMax) : null,
        target_weight_kg: item.weight.trim()
          ? Number(item.weight.trim().replace(',', '.'))
          : null,
        rest_seconds: item.rest.trim() ? Number(item.rest) : null,
        tempo: item.tempo,
        notes: item.notes.trim() || null,
      })),
    })),
  };
}
