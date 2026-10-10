# ADR 111: Career development module

## Status

Accepted (2026-10-10).

## Context

Brad wants help with his civil engineering career: general progression,
meeting his goals, knowing the next steps, and getting chartered and
registered in Australia. He moved from New Zealand to Melbourne in
November 2024. His Second Brain already holds the story: *CPEng
Chartership* and *Brad's Career History*.

He already logs CPD in Engineers Australia's portal and doesn't want to log
it twice.

Two places were considered for this: a new app in the Siris suite, or a
module inside SirisOS. We chose the module:

- Nothing else in the suite owns this domain. That's the same reason the
  engineering tools stay in SirisOS (ADR 106).
- The evidence for chartership comes from what SirisOS already reaches:
  SirisOS projects, APD PM, the Archive, the Reviewer and the Second Brain.
- A separate app would add a container, a login, a backup and connectors,
  all for one user. It would be the better choice if mentors, referees or
  colleagues needed their own logins.

## Decision

### A Career tab in SirisOS (`/career`)

The tab has five views:

- **Overview:** next steps (pathway steps, goals, CPD shortfalls and
  competency gaps), CPD against the requirement, progress on each pathway,
  a 16-cell map of the competency elements, goals, and links to the career
  notes in the Second Brain.
- **CPD:** imported from Engineers Australia (see below). It shows the
  rolling three-year totals against 150 hours and the three minimums, hours
  by year, hours that leave the window in the next 90 days, and every
  activity.
- **Pathways:** step checklists, each step with a status (to do, in
  progress, done, not needed), a done date and a note. The seeded pathways
  are:
  - Engineers Australia membership (MIEAust)
  - Chartered (CPEng)
  - National Engineering Register (NER)
  - Registered Professional Engineer in Victoria (civil), with the Business
    Licensing Authority

  CPEng, or Engineers Australia membership plus an NER listing, lets him
  register in Victoria without a separate assessment.
- **Competencies:** Engineers Australia's Stage 2 standard, 16 elements in
  four units. Evidence items (a project, a decision, a report) are tagged
  with the elements they show and link to Second Brain notes, SirisOS
  routes or other apps (APD PM, the Archive and so on).
- **Goals:** each with a target date and a next step.

The tab also feeds the rest of SirisOS:

- A Home widget showing CPD hours and the next step.
- A Career card in the daily brief.
- Career results in search: goals, evidence, steps and CPD activities.
- A sixth dock item. On narrow phones the Engineering label shortens to
  "Eng" so all six fit.

### CPD comes from Engineers Australia

Engineers Australia has no API. Its CPD recording platform exports the
record: filter by date, then pick a file format. SirisOS imports that file:

- **Formats.** CSV and Excel are accepted. Columns are matched by name,
  loosely, because the export's exact headings aren't documented. A title
  row above the table, day-first dates, Excel serial dates and `1:30` /
  `2h 30m` durations are all handled. PDF reports are refused with a pointer
  to the CSV and Excel exports.
- **Safe to re-import.** Each activity is identified by its date, title and
  hours. Importing the full history again, or an overlapping range, updates
  activities instead of duplicating them. The last 20 imports are listed.
- **Categories.** If the export has its own columns for area of practice,
  risk management, and business and management hours, those split the
  hours. Otherwise each activity is placed by keywords and marked as a
  guess. Brad can change a guessed category, and his choice survives
  re-imports.
- **No manual entry.** CPD is never typed into SirisOS, and the tab's save
  can't touch it.

### Data and seeds

Everything is stored in one file, `data/app/career.json`
(`SIRISOS_CAREER_PATH`), written atomically. Nothing is written until the
first change.

The pathways, steps, competency elements and CPD requirement (150 hours
over 3 years, with at least 50 in the area of practice, 10 in risk
management and 15 in business and management) are a starting point from
October 2026. Each pathway links to its body's page so it can be checked.

## Consequences

- Keeping CPD up to date means exporting from Engineers Australia now and
  then. There's no live sync, because there's no API to sync with.
- The export's real column names are unverified. The importer is
  deliberately loose, and its error message says which columns it expected.
- Planned next: drafting competency claims from tagged evidence into
  Second Brain notes.

## Amendment (2026-10-10)

### SirisAI reads the career record

SirisAI's `career_cpd_status` and `career_chartership_status` tools call
`GET /api/v1/career` with SirisOS's service key (`SIRISOS_SERVICE_KEY`,
the same value as SirisAI's `SIRISAI_SIRISOS_SERVICE_KEY`).

`app/service_key.py` is taken unchanged from SirisAI's SirisOS integration
patch, plus the two career reads. It opens only the allowlisted read and
compute routes, never anything that changes data.

### Dock

The phone dock holds five items: Home, Siris, Brain, Links and Career.
Engineering stays in the menu and search. On phones (640 px wide and
under), the dock spans the screen and its items share the width evenly,
so it can't run off the edge. A 430 px Pro Max showed that it could.
