import type { ScaleVersion } from '@/lib/biomechanical-scales';

export type ReviewStatus = 'pending' | 'reviewed' | 'rejected';

export const REVIEW_LABELS: Record<ReviewStatus, string> = {
  pending: 'Pendente',
  reviewed: 'Revisada',
  rejected: 'Rejeitada',
};

export interface AssessmentSummary {
  id: string;
  exercise_id: string;
  exercise_name: string;
  images: string[];
  scale_version: number;
  uses_current_scale: boolean;
  assessment_method: 'manual' | 'ai' | 'rule';
  assessment_source: string;
  review_status: ReviewStatus;
  created_at: string;
}

export interface AssessmentList {
  filters: { muscle_groups: string[]; categories: string[] };
  items: (AssessmentSummary & {
    region_scores: {
      region_code: string;
      label: string;
      assessment_status: 'assessed' | 'unassessed' | null;
      demand_score: number | null;
    }[];
  })[];
  counts: {
    total_exercises: number;
    validated_exercises: number;
    unvalidated_exercises: number;
  };
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
}

export interface AssessmentDetail extends AssessmentSummary {
  content_hash: string;
  supersedes_id: string | null;
  execution_context: string;
  created_by: string | null;
  regions: {
    region_code: string;
    assessment_status: 'assessed' | 'unassessed';
    demand_score: number | null;
    demand_role: string | null;
    justification: string;
  }[];
  review: {
    decision: Exclude<ReviewStatus, 'pending'>;
    notes: string;
    reviewed_by: string | null;
    reviewed_at: string;
  } | null;
  scale: ScaleVersion;
  validation_errors: string[];
}
