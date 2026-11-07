import { describe, expect, it } from "vitest";
import { buildDay } from "./TodayTimeline";

describe("buildDay", () => {
  it("puts today in time order, then any-time things, then what's coming", () => {
    const now = new Date(2026, 10, 7, 9, 0);
    const day = buildDay(now, {
      events: [{ summary: "Standup", start: "2026-11-07T09:30:00" }, { summary: "Dentist", start: "2026-11-07T08:00:00" },
        { summary: "Tomorrow thing", start: "2026-11-08T08:00:00" }, { summary: "Market day", start: "2026-11-07" }],
      tasks: [{ id: "1", title: "Call plumber", due: "2026-11-07", time: "11:00", group: "today" }, { id: "2", title: "Bins", due: "2026-11-06", time: null, group: "overdue" },
        { id: "3", title: "Later", due: "2026-11-20", time: null, group: "later" }],
      bills: [{ id: 5, label: "Netflix renews Mon 9 Nov for $22.99", due_date: "2026-11-09" }, { id: 6, label: "Far off", due_date: "2026-12-01" }],
      people: [{ id: 2, name: "Sam", days_to_birthday: 5, turning: 36 }, { id: 3, name: "Kim", days_to_birthday: 40 }],
      trips: [{ key: "k", destination: "Sydney", start: "2026-11-10T07:00:00+11:00", nights: 3 }],
    });
    expect(day.timed.map((e) => `${e.time} ${e.text}`)).toEqual(["08:00 Dentist", "09:30 Standup", "11:00 Call plumber"]);
    expect(day.anytime.map((e) => e.text)).toEqual(["Market day", "Bins"]);
    expect(day.anytime[1].sub).toBe("overdue");
    expect(day.soon.map((e) => e.text)).toEqual(["Netflix renews Mon 9 Nov for $22.99", "Sam's birthday in 5 days (36)", "Sydney in 3 days"]);
  });
});
