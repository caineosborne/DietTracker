export type MealItem = {
  name: string;
  calories_low: number;
  calories_mid: number;
  calories_high: number;
  protein_level: "low" | "medium" | "good";
  confidence: "low" | "medium" | "high";
  notes: string;
  tags: string[];
};

export type MealEstimate = {
  items: MealItem[];
  total_calories_low: number;
  total_calories_mid: number;
  total_calories_high: number;
  consumed_at: string;
  time_source: string;
  summary_notes: string;
};

export type Meal = {
  id: string;
  timestamp: string;
  raw_text: string;
  items: MealItem[];
  total_calories_low: number;
  total_calories_mid: number;
  total_calories_high: number;
  user_override: number | null;
  notes: string;
  created_at: string;
  is_small_snack_allowance: boolean;
};

export type DayMetrics = {
  total_calories: number;
  active_calories: number;
  remaining_calories: number;
  total_burn: number;
  calorie_balance: number;
  expected_weight_delta_kg: number;
  weight_direction_label: string;
  anchor_weight_kg: number;
  anchor_day: string;
  actual_weight_kg: number | null;
  actual_weight_delta_kg: number | null;
  expected_weight_kg: number;
  weight_difference_kg: number | null;
  status: string;
};

export type HistoryDay = {
  day: string;
  total_burn: number;
  total_intake: number;
  calorie_balance: number;
  expected_weight_delta_kg: number;
  weight_direction_label: string;
  anchor_weight_kg: number;
  anchor_day: string;
  expected_weight_kg: number;
  actual_weight_kg: number | null;
  actual_weight_delta_kg: number | null;
  weight_difference_kg: number | null;
};

export type HistorySummary = {
  label: string;
  days_count: number;
  total_burn: number;
  total_intake: number;
  calorie_balance: number;
  expected_weight_delta_kg: number;
  weight_direction_label: string;
  expected_weight_kg: number;
  latest_actual_weight_kg: number | null;
};

export type WeekMetrics = {
  window_start: string;
  window_end: string;
  average_calories: number;
  average_active_calories: number;
  tracked_consumed_total: number;
  total_burn: number;
  calorie_balance: number;
  expected_weight_delta_kg: number;
  weight_direction_label: string;
  tracked_days_count: number;
  meals_count: number;
  activity_days_count: number;
};

export type Dashboard = {
  today: string;
  selected_day: string;
  timezone: string;
  supported_timezones: string[];
  daily_goal: number;
  model: string;
  meals: Meal[];
  activity: { active_calories: number } | null;
  weight: { weight_kg: number } | null;
  day_metrics: DayMetrics;
  week_metrics: WeekMetrics;
  history: HistoryDay[];
  history_summaries: HistorySummary[];
};

const API_URL = (import.meta.env.VITE_API_URL || "http://localhost:8000").replace(/\/$/, "");
const TOKEN_KEY = "diettracker_session";
const transientStatuses = new Set([408, 425, 429, 500, 502, 503, 504]);

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}

const wait = (milliseconds: number) => new Promise((resolve) => window.setTimeout(resolve, milliseconds));

export async function request<T>(path: string, init: RequestInit = {}, retries = 2): Promise<T> {
  let lastError: unknown;
  const delays = [650, 1300, 2200];
  for (let attempt = 0; attempt <= retries; attempt += 1) {
    try {
      const response = await fetch(`${API_URL}${path}`, {
        ...init,
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
          ...(localStorage.getItem(TOKEN_KEY) ? { Authorization: `Bearer ${localStorage.getItem(TOKEN_KEY)}` } : {}),
          ...init.headers,
        },
      });
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        const error = new ApiError(body.detail || "The request could not be completed.", response.status);
        if (!transientStatuses.has(response.status) || attempt === retries) throw error;
        lastError = error;
      } else {
        if (response.status === 204) return undefined as T;
        return (await response.json()) as T;
      }
    } catch (error) {
      if (error instanceof ApiError && !transientStatuses.has(error.status)) throw error;
      lastError = error;
      if (attempt === retries) break;
    }
    await wait(delays[attempt]);
  }
  throw lastError instanceof Error ? lastError : new Error("The API is still starting.");
}

export const api = {
  health: () => request<{ status: string }>("/health", {}, 3),
  session: () => request<{ username: string }>("/api/auth/session", {}, 0),
  login: async (username: string, password: string) => {
    const result = await request<{ username: string; token: string }>("/api/auth/login", { method: "POST", body: JSON.stringify({ username, password }) }, 0);
    localStorage.setItem(TOKEN_KEY, result.token);
    return result;
  },
  logout: async () => {
    try { await request<void>("/api/auth/logout", { method: "POST" }, 0); }
    finally { localStorage.removeItem(TOKEN_KEY); }
  },
  dashboard: (day?: string) => request<Dashboard>(`/api/dashboard${day ? `?day=${day}` : ""}`),
  estimate: (rawText: string) =>
    request<MealEstimate>("/api/meals/estimate", { method: "POST", body: JSON.stringify({ raw_text: rawText }) }),
  createMeal: (payload: MealPayload) =>
    request<Meal>("/api/meals", { method: "POST", body: JSON.stringify(payload) }),
  updateMeal: (id: string, payload: MealPayload) =>
    request<Meal>(`/api/meals/${id}`, { method: "PUT", body: JSON.stringify(payload) }),
  deleteMeal: (id: string) => request<void>(`/api/meals/${id}`, { method: "DELETE" }),
  saveActivity: (day: string, activeCalories: number) =>
    request(`/api/activity/${day}`, { method: "PUT", body: JSON.stringify({ active_calories: activeCalories }) }),
  saveWeight: (day: string, weightKg: number) =>
    request(`/api/weight/${day}`, { method: "PUT", body: JSON.stringify({ weight_kg: weightKg }) }),
  saveTimezone: (timezone: string) =>
    request("/api/settings/timezone", { method: "PUT", body: JSON.stringify({ timezone }) }),
};

export type MealPayload = {
  request_id: string;
  raw_text: string;
  items: MealItem[];
  consumed_at: string;
  summary_notes: string;
  user_total_override: number | null;
  user_notes: string;
};
