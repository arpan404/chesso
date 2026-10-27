export type Mode = "home" | "game" | "puzzle" | "study" | "profile";
export type Tier = "easy" | "medium" | "hard";
export interface Profile {
  id: string;
  nickname: string;
  experience: "unspecified" | "new" | "casual" | "club" | "advanced";
  analytics_consent: boolean;
  research_consent: boolean;
  puzzle_rating: number;
  puzzles_solved: number;
  puzzles_attempted: number;
  points: number;
  calibration_complete?: boolean;
  rating_range?: [number, number];
  activity_counts: Record<string, number>;
  recent: {
    id: string;
    kind: "game" | "puzzle" | "study";
    updated_at: number;
    completed: boolean;
  }[];
}
export interface Position {
  fen: string;
  pieces: Record<string, string>;
  legal_moves: string[];
  turn: "white" | "black";
  check: boolean;
  result: string | null;
}
export interface Activity extends Position {
  id: string;
  version: number;
  completed: boolean;
  moves?: string[];
  history?: { san: string; uci: string }[];
  opponent?: "local" | "computer";
  color?: "white" | "black";
  termination?: string | null;
  tier?: Tier;
  rating?: number;
  points?: number;
  solved?: boolean;
  rating_delta?: number;
  themes?: string[];
  solution?: string[] | null;
  solution_san?: string[] | null;
  hint?: string | null;
  hint_text?: string | null;
  hint_shown?: boolean;
  remaining_seconds?: number;
  time_limit_seconds?: number;
  player_moves_required?: number;
  player_color?: "white" | "black";
  hints_available?: boolean;
  index?: number;
  total?: number;
  phase?: "baseline" | "training" | "transfer";
  trial_id?: string;
  presented_at?: number | null;
  candidate_move?: string | null;
  initial_move?: string | null;
  finished?: boolean;
  status?: string | null;
  reflection?: string | null;
  reflection_prompt?: string | null;
  condition?: "informational" | "reflective";
  task_prompt?: string;
}

export interface LearningSummary {
  id: string;
  kind: "calibration" | "puzzle_session";
  version: number;
  total: number;
  completed: boolean;
  started_at: number;
  finished_at: number | null;
  finished_count: number;
  solved: number;
  hints_available: boolean;
  estimated_rating: number;
  rating_range: [number, number];
  rating_before: number;
  rating_after: number | null;
  outcomes: { solved: boolean; hint_used: boolean; status: string }[];
  feedback: {
    satisfaction: number | null;
    helpfulness: number | null;
    skipped: boolean;
  } | null;
}
export interface LearningSession extends LearningSummary {
  puzzle: Activity;
}
export interface LearningHome {
  profile: Profile;
  onboarding_id: string | null;
  active_session: LearningSummary | null;
  recent: LearningSummary[];
}
export interface LearningHistory {
  items: LearningSummary[];
  page: number;
  total_pages: number;
  total: number;
}
