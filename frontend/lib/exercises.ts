export type ExerciseLocale = 'en' | 'pt-BR';

export interface ExerciseSummary {
  id: string;
  source_id: string | null;
  name: string;
  muscle_group: string;
  equipment: string | null;
  level: string | null;
  locale: ExerciseLocale | null;
  images: string[];
  enabled_for_ai: boolean;
}

export interface ExerciseDetail extends ExerciseSummary {
  description: string | null;
  force: string | null;
  mechanic: string | null;
  category: string | null;
  primary_muscles: string[];
  secondary_muscles: string[];
  instructions: string[];
}

export interface ExerciseFilters {
  muscle_groups: string[];
  equipment: string[];
  levels: string[];
  categories: string[];
  mechanics: string[];
  forces: string[];
}

export interface ExerciseCatalogResponse {
  items: ExerciseSummary[];
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
  filters: ExerciseFilters;
}

// O banco guarda códigos canônicos em inglês; a tradução acontece só na tela.
const MUSCLES: Record<string, string> = {
  abdominals: 'Abdômen',
  abductors: 'Abdutores',
  adductors: 'Adutores',
  biceps: 'Bíceps',
  calves: 'Panturrilhas',
  chest: 'Peito',
  forearms: 'Antebraços',
  glutes: 'Glúteos',
  hamstrings: 'Posteriores de coxa',
  lats: 'Dorsais',
  'lower back': 'Lombar',
  'middle back': 'Meio das costas',
  neck: 'Pescoço',
  quadriceps: 'Quadríceps',
  shoulders: 'Ombros',
  traps: 'Trapézio',
  triceps: 'Tríceps',
};

const EQUIPMENT: Record<string, string> = {
  bands: 'Elásticos',
  barbell: 'Barra',
  'body only': 'Peso do corpo',
  cable: 'Cabo',
  dumbbell: 'Halteres',
  'e-z curl bar': 'Barra W',
  'exercise ball': 'Bola suíça',
  'foam roll': 'Rolo de espuma',
  kettlebells: 'Kettlebell',
  machine: 'Máquina',
  'medicine ball': 'Medicine ball',
  other: 'Outros',
};

const LEVELS: Record<string, string> = {
  beginner: 'Iniciante',
  intermediate: 'Intermediário',
  expert: 'Avançado',
};

const CATEGORIES: Record<string, string> = {
  strength: 'Força',
  stretching: 'Alongamento',
  plyometrics: 'Pliometria',
  strongman: 'Strongman',
  powerlifting: 'Powerlifting',
  cardio: 'Cardio',
  'olympic weightlifting': 'Levantamento olímpico',
};

const FORCES: Record<string, string> = {
  push: 'Empurrar',
  pull: 'Puxar',
  static: 'Estático',
};

const MECHANICS: Record<string, string> = {
  compound: 'Composto',
  isolation: 'Isolado',
};

function label(value: string, dictionary: Record<string, string>) {
  return dictionary[value] ?? value.charAt(0).toUpperCase() + value.slice(1);
}

export const muscleLabel = (value: string) => label(value, MUSCLES);
export const equipmentLabel = (value: string) => label(value, EQUIPMENT);
export const levelLabel = (value: string) => label(value, LEVELS);
export const categoryLabel = (value: string) => label(value, CATEGORIES);
export const forceLabel = (value: string) => label(value, FORCES);
export const mechanicLabel = (value: string) => label(value, MECHANICS);

// Cor por nível, para o iniciante ser identificado de relance.
export function levelBadgeClass(level: string | null) {
  switch (level) {
    case 'beginner':
      return 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-300';
    case 'intermediate':
      return 'bg-amber-500/15 text-amber-700 dark:text-amber-300';
    case 'expert':
      return 'bg-rose-500/15 text-rose-700 dark:text-rose-300';
    default:
      return 'bg-muted text-muted-foreground';
  }
}
