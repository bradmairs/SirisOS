import { api } from "./client";

/** 10.2: the week's dinners (from Mealie when it's set up) and the shopping for them. */
export interface Dinner { title: string; slug?: string | null; recipe_id?: string | null; source: "mealie" | "local"; url?: string | null; ingredients?: string[] | null; mealie_id?: string | number | null }
export interface MealWeek {
  start: string; days: { date: string; dinner: Dinner | null }[];
  often: { title: string; slug?: string | null; recipe_id?: string | null; times: number }[];
  staples: string[]; list: string | null; mealie: { configured: boolean; error: string | null };
}
export interface Recipe { id: string; slug: string; name: string; time?: string | null; url?: string | null }
export interface ShoppingItem { key: string; name: string; lines: string[]; for: string[]; staple: boolean; on_list: boolean; need: boolean }
export interface Shopping { start: string; items: ShoppingItem[]; no_ingredients: string[]; lists: { entity_id: string; name: string }[]; list: string | null; staples: string[] }

const M = "/api/v1/meals";
export const meals = {
  week: (start?: string) => api<MealWeek>(`${M}${start ? `?start=${start}` : ""}`),
  plan: (date: string, d: { title: string; slug?: string | null; recipe_id?: string | null; ingredients?: string[] }, start?: string) =>
    api<MealWeek>(`${M}/${date}`, { method: "PUT", body: JSON.stringify({ ...d, start }) }),
  unplan: (date: string, start?: string) => api<MealWeek>(`${M}/${date}${start ? `?start=${start}` : ""}`, { method: "DELETE" }),
  recipes: (q: string) => api<{ configured: boolean; recipes: Recipe[] }>(`${M}/recipes?q=${encodeURIComponent(q)}`),
  shopping: (start?: string) => api<Shopping>(`${M}/shopping${start ? `?start=${start}` : ""}`),
  addToList: (items: string[], list: string) => api<{ added: number; list: string }>(`${M}/shopping`, { method: "POST", body: JSON.stringify({ items, list }) }),
  staples: (staples: string[]) => api<{ staples: string[] }>(`${M}/staples`, { method: "PUT", body: JSON.stringify({ staples }) }),
  tonight: () => api<{ dinner: { title: string; slug?: string | null } | null }>(`${M}/tonight`),
};
