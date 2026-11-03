import { nextKey, type Draft, type PlanLevel } from '@/lib/workouts';

export type Goal = 'hypertrophy' | 'strength' | 'fat_loss' | 'general_health';
export type SplitStyle =
  | 'auto'
  | 'full_body'
  | 'upper_lower'
  | 'push_pull_legs'
  | 'hybrid'
  | 'body_part';

export interface GenerateInput {
  goal: Goal;
  level: PlanLevel;
  days_per_week: number;
  session_minutes: number;
  split_style: SplitStyle;
  focus_muscles: string[];
  avoid_muscles: string[];
}

export interface GeneratedExercise {
  exercise_id: string;
  name: string;
  muscle_group: string;
  equipment: string | null;
  images: string[];
  role: 'compound' | 'isolation';
  sets: number;
  reps_min: number;
  reps_max: number;
  rest_seconds: number;
}

export interface GeneratedDay {
  name: string;
  notes: string;
  estimated_minutes: number;
  exercises: GeneratedExercise[];
}

export interface WeeklyVolume {
  muscle: string;
  label: string;
  sets: number;
  target: number;
}

export interface Reference {
  id: string;
  text: string;
}

// Parte do resultado que é guardada junto do treino (ai_metadata).
export interface AiInfo {
  rules_version: string;
  review_status: string;
  split: string;
  rationale: string[];
  warnings: string[];
  references: Reference[];
  weekly_volume: WeeklyVolume[];
}

export interface GeneratedPlan extends AiInfo {
  name: string;
  description: string;
  goal: string;
  level: PlanLevel;
  days: GeneratedDay[];
}

export interface GenerationInfo {
  info: AiInfo;
  input: GenerateInput;
}

export const GOAL_OPTIONS: {
  value: Goal;
  title: string;
  description: string;
}[] = [
  {
    value: 'hypertrophy',
    title: 'Ganhar massa muscular',
    description: 'Aumentar o tamanho dos músculos (hipertrofia).',
  },
  {
    value: 'strength',
    title: 'Ficar mais forte',
    description: 'Levantar cargas maiores nos movimentos principais.',
  },
  {
    value: 'fat_loss',
    title: 'Emagrecer',
    description: 'Preservar massa magra com treino eficiente em tempo.',
  },
  {
    value: 'general_health',
    title: 'Saúde e bem-estar',
    description: 'Corpo todo, esforço confortável e sustentável.',
  },
];

export const LEVEL_CHOICES: {
  value: PlanLevel;
  title: string;
  description: string;
}[] = [
  {
    value: 'beginner',
    title: 'Iniciante',
    description: 'Começando, ou treinando há menos de 6 meses.',
  },
  {
    value: 'intermediate',
    title: 'Intermediário',
    description: 'Treina com regularidade há 6 meses a 2 anos.',
  },
  {
    value: 'expert',
    title: 'Avançado',
    description: 'Treina com consistência há mais de 2 anos.',
  },
];

export const DAYS_OPTIONS: number[] = [2, 3, 4, 5, 6];

// Espelha backend/src/workouts/generator/splits.py (o backend valida de qualquer forma).
export const SPLIT_STYLES: {
  value: Exclude<SplitStyle, 'auto'>;
  title: string;
  description: string;
  days: number[];
}[] = [
  {
    value: 'full_body',
    title: 'Corpo inteiro',
    description:
      'Todos os grupos musculares em cada sessão. Cada músculo treina mais de uma vez por semana.',
    days: [2, 3],
  },
  {
    value: 'upper_lower',
    title: 'Superior / Inferior',
    description:
      'Alterna parte de cima e de baixo do corpo. Cada músculo treina 2x (4 dias) ou 3x (6 dias).',
    days: [4, 6],
  },
  {
    value: 'push_pull_legs',
    title: 'Empurrar / Puxar / Pernas',
    description:
      'Agrupa por movimento: empurrar (peito, ombros, tríceps), puxar (costas, bíceps) e pernas. 1x por semana com 3 dias, 2x com 6.',
    days: [3, 6],
  },
  {
    value: 'hybrid',
    title: 'Misto (5 dias)',
    description:
      'Superior, inferior, empurrar, puxar e pernas. A maioria dos músculos treina 2x por semana.',
    days: [5],
  },
  {
    value: 'body_part',
    title: 'Por grupos musculares',
    description:
      'Um ou dois grupos por dia (ex.: peito e tríceps, costas e bíceps, pernas). Cada músculo treina 1x por semana, com as séries concentradas na sessão.',
    days: [3, 4, 5, 6],
  },
];

export const AUTO_STYLE_BY_DAYS: Record<number, string> = {
  2: 'Corpo inteiro',
  3: 'Corpo inteiro',
  4: 'Superior / Inferior',
  5: 'Misto',
  6: 'Empurrar / Puxar / Pernas',
};

export const MINUTES_OPTIONS = [30, 45, 60, 75, 90, 120];

export const FOCUS_MUSCLES = [
  'chest',
  'lats',
  'middle back',
  'shoulders',
  'quadriceps',
  'hamstrings',
  'glutes',
  'biceps',
  'triceps',
  'calves',
  'abdominals',
];

export const AVOID_MUSCLES = [
  'neck',
  'shoulders',
  'chest',
  'biceps',
  'triceps',
  'forearms',
  'lats',
  'middle back',
  'lower back',
  'traps',
  'abdominals',
  'glutes',
  'quadriceps',
  'hamstrings',
  'adductors',
  'abductors',
  'calves',
];

export const MAX_FOCUS = 3;
export const MAX_AVOID = 6;

export const DEFAULT_INPUT: GenerateInput = {
  goal: 'hypertrophy',
  level: 'beginner',
  days_per_week: 3,
  session_minutes: 60,
  split_style: 'auto',
  focus_muscles: [],
  avoid_muscles: [],
};

export function draftFromGenerated(plan: GeneratedPlan): Draft {
  return {
    name: plan.name,
    description: plan.description,
    goal: plan.goal,
    level: plan.level,
    days: plan.days.map((day) => ({
      key: nextKey(),
      name: day.name,
      notes: day.notes,
      exercises: day.exercises.map((exercise) => ({
        key: nextKey(),
        exercise: {
          id: exercise.exercise_id,
          name: exercise.name,
          muscle_group: exercise.muscle_group,
          equipment: exercise.equipment,
          images: exercise.images,
        },
        sets: String(exercise.sets),
        repsMin: String(exercise.reps_min),
        repsMax: String(exercise.reps_max),
        weight: '',
        rest: String(exercise.rest_seconds),
        tempo: null,
        notes: '',
      })),
    })),
  };
}

export function aiMetadata({ info, input }: GenerationInfo) {
  return { generator: 'rules', inputs: input, ...info };
}

// Lê o que foi guardado em ai_metadata, tolerando dados antigos ou incompletos.
export function extractAiInfo(metadata: unknown): AiInfo | null {
  if (!metadata || typeof metadata !== 'object') return null;
  const data = metadata as Record<string, unknown>;
  if (!Array.isArray(data.rationale)) return null;
  return {
    rules_version: String(data.rules_version ?? ''),
    review_status: String(data.review_status ?? ''),
    split: String(data.split ?? ''),
    rationale: data.rationale.map(String),
    warnings: Array.isArray(data.warnings) ? data.warnings.map(String) : [],
    references: Array.isArray(data.references)
      ? (data.references as Reference[])
      : [],
    weekly_volume: Array.isArray(data.weekly_volume)
      ? (data.weekly_volume as WeeklyVolume[])
      : [],
  };
}
