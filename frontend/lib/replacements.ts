import type { ExerciseSummary } from '@/lib/exercises';
import type { SessionDetail } from '@/lib/sessions';
import type { draftToPayload, PlanDetail } from '@/lib/workouts';

export type ReplacementContext =
  | {
      mode: 'draft';
      workout: ReturnType<typeof draftToPayload>;
      day_index: number;
      exercise_index: number;
    }
  | { mode: 'plan'; plan_id: string; day_id: string; row_id: string }
  | { mode: 'session'; session_id: string; exercise_id: string };

export interface ReplacementOption {
  exercise: ExerciseSummary;
  pro: string;
  con: string;
}

export interface ReplacementSuggestions {
  options: ReplacementOption[];
  revision: string;
  message: string | null;
}

export interface AppliedReplacement {
  plan: PlanDetail | null;
  session: SessionDetail | null;
}
