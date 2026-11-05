export interface NamedCriterion {
  code: string;
  label: string;
  description: string;
}

export interface ScaleDefinition {
  title: string;
  disclaimer: string;
  reference_conditions: string;
  evaluation_criteria: string;
  consistency_rules: string;
  unassessed_guidance: string;
  regions: NamedCriterion[];
  roles: NamedCriterion[];
  scores: { score: number; label: string; description: string }[];
}

export interface ScaleSummary {
  version: number;
  change_reason: string;
  created_by: string | null;
  created_at: string;
}

export interface ScaleVersion extends ScaleSummary {
  definition: ScaleDefinition;
}

export interface ScaleHistory {
  items: ScaleSummary[];
  page: number;
  total: number;
}
