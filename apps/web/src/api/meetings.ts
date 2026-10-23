import { api, json } from "./client";
import type { TaskItem } from "./tasks";

export interface Meeting {
  title: string;
  start: string | null;
  end: string | null;
  location: string | null;
  attendees: string[];
}

export interface MeetingPrep {
  title: string;
  start: string | null;
  end: string | null;
  location: string | null;
  found: boolean;
  people: { email: string; name: string }[];
  notes: { title: string; excerpt: string; type: string | null }[];
  emails: { uid: string; sender: string; subject: string; date: string | null; snippet: string }[] | null;
  tasks: TaskItem[];
}

export const meetings = {
  list: () => api<{ meetings: Meeting[] }>("/api/v1/meetings"),
  prep: (title: string, start?: string | null) =>
    api<MeetingPrep>(`/api/v1/meetings/prep?title=${encodeURIComponent(title)}${start ? `&start=${encodeURIComponent(start)}` : ""}`),
  saveNotes: (title: string, start: string | null, text: string) => api<{ saved_as: string; tasks: string[] }>("/api/v1/meetings/notes", json({ title, start, text })),
};

export const prepLink = (title: string, start?: string | null) => `/meeting?title=${encodeURIComponent(title)}${start ? `&start=${encodeURIComponent(start)}` : ""}`;
