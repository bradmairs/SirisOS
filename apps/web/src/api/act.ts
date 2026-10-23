import { api, json } from "./client";

export interface Act {
  title: string;
  body: string;
  url: string;
  actions: { id: string; title: string }[];
  /** The button already pressed on this notification, if any. */
  done: string | null;
}

/** A notification's buttons (3.8): the token in its link is the permission, no sign-in. */
export const act = {
  get: (token: string) => api<Act>(`/api/v1/push/act?t=${encodeURIComponent(token)}`),
  press: (token: string, action: string) => api<{ done: string; message: string; url: string }>("/api/v1/push/act", json({ token, action })),
};
