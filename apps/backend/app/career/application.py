"""The Chartered application (4.6): Engineers Australia's three forms for an
Independent Practice Assessment, worked through in SirisOS.

- **CPD questionnaire** (3 ASM TPL v2.0). Applying for Chartered or NER needs
  evidence of active CPD, with no minimum hours: the EA CPD log, or this
  questionnaire. Each question names its CPD type (I to VIII). Holding the
  credential then needs 150 hours over three years (defaults.CPD_REQUIREMENT).
- **Self-reflection on the chartered competencies** (3 ASM TPL v4.1). The
  area of practice sought, Part 1 (19 questions, Yes or Not sure), Part 2
  (four Yes or No), Part 3 (two or three sentences per Stage 2 element, citing
  one recent, specific work episode) and Part 4 (it's your own work, signed).
  "Not sure" isn't held against you: it marks what to prepare for interview.
- **Building Industry Assessment** (VIC, WA, ACT). Only if you provide
  engineering services in the building industry there. For Victoria's
  Building Industry Endorsement: a detailed CV, building-industry CPD, and a
  statement of three years' experience with the Building Act 1993, Building
  Regulations 2018 and the NCC.

Answers live in the career file; a completed copy of each form can be
uploaded and is kept in the data folder next to it.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.career import store
from app.career.store import Application, Bia, CareerDocument, UploadedFile

MAX_FILE_BYTES = 20 * 1024 * 1024
DocId = Literal["cpd", "reflection", "bia"]

DOCUMENTS: list[dict[str, str]] = [
    {"id": "cpd", "title": "CPD questionnaire", "form": "3 ASM TPL CPD Questionnaire v2.0",
     "summary": "Evidence that you do CPD: send your Engineers Australia CPD log, or answer these questions for the last three years with rough hours."},
    {"id": "reflection", "title": "Self-reflection on the chartered competencies", "form": "3 ASM TPL Self-Reflection on Chartered Competencies Questionnaire v4.1",
     "summary": "Your area of practice, a self-check (Parts 1 and 2), a short comment on each of the 16 elements from a recent work episode (Part 3), and a signed statement (Part 4)."},
    {"id": "bia", "title": "Building Industry Assessment", "form": "Building Industry Assessment for VIC, WA, ACT, information sheet v4",
     "summary": "Only if you provide engineering services in the building industry in Victoria, WA or the ACT. Answer Yes or No and return the form."},
]

# The CPD questionnaire: id, question, CPD type(s), words that find matching CPD records.
CPD_QUESTIONS: list[dict[str, str]] = [
    {"id": "tertiary", "q": "Are you, or have you undertaken any tertiary study?", "type": "Type I", "match": r"universit|master|graduate|degree|diploma|tertiary"},
    {"id": "conferences", "q": "What conferences or seminars have you attended?", "type": "Type II (Type VI for presentations)", "match": r"conference|seminar|summit|symposium|ozwater|forum"},
    {"id": "courses", "q": "What short courses or refresher training have you done?", "type": "Type II (Type VI for presentations)", "match": r"course|training|refresher|certificate|workshop"},
    {"id": "events", "q": "What events have you attended in person or remotely?", "type": "Type II (Type VI for presentations)", "match": r"webinar|event|talk|session|lunch and learn|meetup|tour"},
    {"id": "research", "q": "Have you done anything at work recently that involved some form of research? (e.g. a feasibility study, investigating international standards)", "type": "Type III", "match": r"research|feasibility|investigat|study"},
    {"id": "reading", "q": "What self-reading or learning have you done? Which Australian Standards or technical literature have you updated your knowledge in?", "type": "Type IV", "match": r"reading|standard|\bas\s?\d|journal|self.?directed|private study"},
    {"id": "mentoring", "q": "How much time have you spent, formally or informally, mentoring others?", "type": "Type V", "match": r"mentor|coach"},
    {"id": "internal", "q": "How much time have you spent on internal company training, as an attendee or presenter, and what did it cover?", "type": "Type II", "match": r"internal|induction|in.?house|lunch and learn|toolbox"},
    {"id": "committees", "q": "Which engineering committees or similar have you taken part in, and how often (including as a panellist on a Chartered assessment)?", "type": "Type V", "match": r"committee|panel|board|young water|ywp|volunteer"},
    {"id": "publications", "q": "What industry publications or journals do you read?", "type": "", "match": r"journal|magazine|publication|newsletter"},
    {"id": "investigation", "q": "What research or investigation (furthering knowledge) have you undertaken?", "type": "", "match": r"research|investigat"},
    {"id": "other", "q": "What other ways have you learnt or developed?", "type": "", "match": r""},
    {"id": "plan", "q": "Briefly describe any development plan related to your current employment.", "type": "", "match": r""},
    {"id": "academic", "q": "If your principal employment is as an academic, how and to what extent have you engaged with industry?", "type": "", "match": r""},
    {"id": "risk", "q": "What learning have you undertaken in risk and risk management, if not addressed earlier?", "type": "", "match": r"risk|safety|hazard|whs|safe\s*design"},
    {"id": "business", "q": "What learning have you undertaken in business management, if not addressed earlier?", "type": "", "match": r"manage|business|contract|financ|leadership|commercial"},
]

# Part 1 of the self-reflection: Yes or Not sure. Each maps to the Stage 2 element(s) it prepares.
PART1: list[dict[str, Any]] = [
    {"id": "ethics-pillars", "q": "Could you describe how the four pillars of EA's Code of Ethics are applied by you in practice (integrity, competence, leadership, sustainability)?", "elements": ["1"]},
    {"id": "ethics-challenged", "q": "Have you dealt with matters where your values and principles relating to the Code of Ethics have been challenged (bribery, improper influence, conflict of interest, corrupt practice, misconduct)?", "elements": ["1"]},
    {"id": "competence-area", "q": "Could you describe your current area of competence and engineering expertise?", "elements": ["2"]},
    {"id": "competence-maintain", "q": "Could you describe how you maintain, extend and exercise your current competence?", "elements": ["2"]},
    {"id": "independent", "q": "Do you act independently and take responsibility for your work?", "elements": ["3"]},
    {"id": "whs", "q": "Do you apply and implement current workplace health and safety requirements, consistent with your organisation's policies and the law?", "elements": ["4"]},
    {"id": "sustainability", "q": "Do you consider the sustainability pillars (economic, social and environmental), short and long term, in your engineering?", "elements": ["4"]},
    {"id": "stakeholders", "q": "Do you identify, analyse and engage with stakeholders?", "elements": ["5"]},
    {"id": "risk", "q": "Are you familiar with your organisation's risk management framework, and do you identify, analyse and manage project, commercial, environmental, reputational and safety risk (AS ISO 31000:2018)?", "elements": ["6"]},
    {"id": "legal", "q": "Could you describe the laws, regulations, practices, standards and agreements that relate to your work, including state registration of engineers?", "elements": ["7"]},
    {"id": "safety-in-design", "q": "Do you apply Safety in Design or other whole-of-life (construction, operation and maintenance, demolition) safety considerations?", "elements": ["4", "6"]},
    {"id": "communication", "q": "Do you undertake a wide range of effective oral and written two-way communication with teams and stakeholders?", "elements": ["8"]},
    {"id": "lead", "q": "Do you initiate, plan, and lead or manage engineering activities?", "elements": ["10"]},
    {"id": "judgement", "q": "Could you describe a situation where you had to apply engineering judgement, without all the information you'd like and no time for analysis?", "elements": ["11"]},
    {"id": "fundamentals", "q": "Could you describe a situation where you applied engineering fundamentals to make a decision or solve a problem?", "elements": ["12"]},
    {"id": "local", "q": "Do you apply local knowledge and practices (your own or others') in your work?", "elements": ["13"]},
    {"id": "problem", "q": "Could you describe an engineering problem: how you analysed it, found the root cause, weighed options and chose a solution?", "elements": ["14"]},
    {"id": "creative", "q": "Have you developed creative, innovative or advanced solutions within your area of competence?", "elements": ["15"]},
    {"id": "review", "q": "Have you reviewed work outputs and outcomes against expectations, and been involved in continuous improvement from those reviews?", "elements": ["16", "9"]},
]

PART2: list[dict[str, str]] = [
    {"id": "read-standard", "q": "Have you read the EA Stage 2 Competency Standards?"},
    {"id": "read-aop", "q": "Have you read the Area of Practice description for the area(s) you're seeking?"},
    {"id": "relate", "q": "Can you relate the competency elements to your work?"},
    {"id": "ready", "q": "Do you feel ready to proceed to the Chartered interview?"},
]

# Part 3: what each element means in practice (the form's own wording, shortened).
ELEMENT_MEANING: dict[str, str] = {
    "1": "You anticipate the consequences of your action or inaction, and identify ethical issues when they arise and act appropriately.",
    "2": "You assess, acquire and apply the competencies and resources appropriate to engineering activities.",
    "3": "You take personal responsibility for your work, and distinguish your own contribution from others'.",
    "4": "You apply current WHS requirements and anticipate the economic, social and environmental effects, short and long term.",
    "5": "You identify stakeholders and their interests, consult and listen, and negotiate outcomes in the community's best interest.",
    "6": "You develop and work within a hazard and risk framework appropriate to the work.",
    "7": "You understand and apply the laws, regulations, codes and other instruments you're bound by.",
    "8": "You communicate in different ways, listen accurately, and write and speak for your audience.",
    "9": "You apply appropriate tools and processes to meet corporate objectives while meeting your obligations to the profession.",
    "10": "You initiate, plan, lead or manage engineering activities.",
    "11": "You exercise sound judgement in engineering activities.",
    "12": "You apply advanced, theory-based understanding of engineering fundamentals to predict the effect of engineering activities.",
    "13": "You acquire and apply local engineering knowledge, including from suppliers, consultants, contractors and experts.",
    "14": "You define, investigate and analyse engineering problems and opportunities.",
    "15": "You develop creative and innovative solutions to engineering problems.",
    "16": "You evaluate the outcomes and impacts of engineering activities.",
}

BIA_STATES: dict[str, dict[str, Any]] = {
    "VIC": {"name": "Victorian Building Industry Endorsement", "years": 3,
            "laws": "the Building Act 1993, the Building Regulations 2018 and the National Construction Code (NCC) for your area of engineering"},
    "WA": {"name": "WA Building Industry Assessment", "years": 5,
           "laws": "the NCC or Australian Standards in WA, the Building Services (Registration) Act 2011 and WA's NCC variations (such as cyclone-resistant construction)"},
    "ACT": {"name": "ACT Building Industry Assessment", "years": 3,
            "laws": "the operation and use of the NCC for your area of engineering"},
}


class ApplicationEdit(BaseModel):
    """Everything but the uploaded files, which change by upload only."""
    area_of_practice: str = Field(default="", max_length=120)
    additional_area: str = Field(default="", max_length=120)
    additional_reason: str = Field(default="", max_length=2000)
    cpd_evidence: Literal["log", "questionnaire"] | None = None
    cpd_answers: dict[str, str] = Field(default_factory=dict)
    part1: dict[str, Literal["yes", "not_sure"]] = Field(default_factory=dict)
    part2: dict[str, Literal["yes", "no"]] = Field(default_factory=dict)
    part3: dict[str, str] = Field(default_factory=dict)
    signed: bool = False
    bia: Bia = Field(default_factory=Bia)


def _words(text: str) -> int:
    return len(re.findall(r"\w+", text))


def _known(answers: dict[str, str], ids: set[str], limit: int) -> dict[str, str]:
    return {k: v.strip()[:limit] for k, v in answers.items() if k in ids and v.strip()}


def apply_edit(edit: ApplicationEdit) -> CareerDocument:
    doc = store.load()
    app = doc.application
    clean = edit.model_copy(update={
        "cpd_answers": _known(edit.cpd_answers, {q["id"] for q in CPD_QUESTIONS}, 4000),
        "part1": {k: v for k, v in edit.part1.items() if k in {q["id"] for q in PART1}},
        "part2": {k: v for k, v in edit.part2.items() if k in {q["id"] for q in PART2}},
        "part3": _known(edit.part3, {e.id for e in doc.elements}, 2000),
    })
    merged = Application.model_validate({**clean.model_dump(), "files": app.model_dump()["files"]})
    return store.save(doc.model_copy(update={"application": merged}))


# ---- drafts -------------------------------------------------------------

def _recent_records(doc: CareerDocument, today: date) -> list[store.CpdRecord]:
    start = today.replace(year=today.year - 3) if not (today.month == 2 and today.day == 29) else today.replace(year=today.year - 3, day=28)
    return [r for r in doc.cpd.records if r.date and start < date.fromisoformat(r.date) <= today]


def cpd_draft(doc: CareerDocument, question_id: str, today: date | None = None) -> str:
    """A starting answer from the CPD records of the last three years that match the question."""
    q = next((q for q in CPD_QUESTIONS if q["id"] == question_id), None)
    if q is None:
        raise LookupError(question_id)
    if question_id == "academic":
        return "N/A"
    if not q["match"]:
        return ""
    pattern = re.compile(q["match"], re.I)
    hits = [r for r in _recent_records(doc, today or date.today()) if pattern.search(f"{r.title} {r.type} {r.provider} {r.notes}")]
    if not hits:
        return ""
    hits.sort(key=lambda r: r.date or "", reverse=True)
    total = sum(r.hours for r in hits)
    lines = [f"About {total:g} hours over the last three years, including:"]
    for r in hits[:8]:
        who = f" ({r.provider})" if r.provider else ""
        lines.append(f"- {r.title}{who}, {date.fromisoformat(r.date).strftime('%b %Y')}: {r.hours:g} h")
    if len(hits) > 8:
        lines.append(f"- and {len(hits) - 8} more")
    return "\n".join(lines)


def element_draft(doc: CareerDocument, element_id: str) -> str:
    """Two or three sentences from the most recent evidence tagged to the element."""
    el = next((e for e in doc.elements if e.id == element_id), None)
    if el is None:
        raise LookupError(element_id)
    ev = sorted((e for e in doc.evidence if element_id in e.elements), key=lambda e: e.date or "", reverse=True)
    if not ev:
        return ""
    top = ev[0]
    when = f" ({datetime.fromisoformat(top.date).strftime('%B %Y')})" if top.date else ""
    first = re.split(r"(?<=[.!?])\s+", top.summary.strip())
    told = " ".join(first[:2]).strip()
    return (f"On {top.title}{when}, {told[0].lower() + told[1:] if told else '[what I did]'} "
            f"[How this shows: {ELEMENT_MEANING.get(element_id, el.title).rstrip('.').lower()}.]").replace("  ", " ")


# ---- readiness ----------------------------------------------------------

SOLID_WORDS = 60


def element_strength(doc: CareerDocument) -> list[dict[str, Any]]:
    """How well each competency element is evidenced (6.3): **none**, **thin**
    or **solid**. Solid is two pieces of evidence, at least one linked to a
    note or project, and a Part 3 comment of SOLID_WORDS (60) words or more.
    Each comes with the next thing to do, weakest first."""
    app = doc.application
    out = []
    for el in doc.elements:
        ev = [e for e in doc.evidence if el.id in e.elements]
        linked = sum(1 for e in ev if e.links)
        words = _words(app.part3.get(el.id, ""))
        if len(ev) >= 2 and linked and words >= SOLID_WORDS:
            strength, step = "solid", None
        elif ev or words >= 15:
            strength = "thin"
            if len(ev) < 2:
                step = "Add a second piece of evidence: a project or task where you did this"
            elif not linked:
                step = "Link the evidence to its note or project, so it's there at interview"
            else:
                step = f"Write more for Part 3 ({words} of {SOLID_WORDS} words): what you did, and how it shows this"
        else:
            strength, step = "none", "Pick a piece of work where you did this, and add it as evidence"
        out.append({"id": el.id, "unit": el.unit, "title": el.title, "strength": strength, "evidence": [e.title for e in ev],
                    "linked": linked, "words": words, "next": step})
    order = {"none": 0, "thin": 1, "solid": 2}
    return sorted(out, key=lambda x: (order[x["strength"]], len(x["evidence"]), x["id"]))

def readiness(doc: CareerDocument) -> dict[str, Any]:
    """What's left before the interview, as a checklist, and a percentage for goals."""
    app = doc.application
    evidenced = {el for ev in doc.evidence for el in ev.elements}
    elements = [e.id for e in doc.elements]
    part3_done = [e for e in elements if _words(app.part3.get(e, "")) >= 15]
    part1_answered = [q for q in PART1 if q["id"] in app.part1]
    not_sure = [q for q in PART1 if app.part1.get(q["id"]) == "not_sure"]
    cpd_answered = [q for q in CPD_QUESTIONS if app.cpd_answers.get(q["id"], "").strip()]
    if app.cpd_evidence == "log":
        cpd_ok, cpd_detail = bool(doc.cpd.records), ("Your Engineers Australia CPD log" if doc.cpd.records else "Import your CPD log from Engineers Australia (the CPD tab), or answer the questionnaire")
    elif app.cpd_evidence == "questionnaire":
        cpd_ok, cpd_detail = len(cpd_answered) == len(CPD_QUESTIONS), f"{len(cpd_answered)} of {len(CPD_QUESTIONS)} questions answered (N/A counts)"
    else:
        cpd_ok, cpd_detail = False, "Choose: send your EA CPD log, or answer the questionnaire"
    b = app.bia
    if b.required is None:
        bia_ok, bia_detail = False, "Decide whether you need one (only for building-industry work in VIC, WA or the ACT)"
    elif not b.required:
        bia_ok, bia_detail = True, "Not needed"
    else:
        st = BIA_STATES.get(b.state or "")
        missing = [x for x, ok in (("the state", bool(st)), ("a detailed CV", b.cv), ("building-industry CPD", b.building_cpd),
                                   ("the experience statement", _words(b.statement) >= 60)) if not ok]
        bia_ok = not missing
        bia_detail = (st["name"] if st else "Building Industry Assessment") + (f": still needs {', '.join(missing)}" if missing else "")
    part2_yes = [q for q in PART2 if app.part2.get(q["id"]) == "yes"]
    items = [
        {"id": "aop", "label": "Area of practice chosen", "done": bool(app.area_of_practice.strip()),
         "detail": app.area_of_practice or "The form's primary area of practice (your main role)"},
        {"id": "cpd", "label": "CPD evidence", "done": cpd_ok, "detail": cpd_detail},
        {"id": "part1", "label": "Self-reflection Part 1", "done": len(part1_answered) == len(PART1),
         "detail": f"{len(part1_answered)} of {len(PART1)} answered" + (f", {len(not_sure)} to prepare" if not_sure else "")},
        {"id": "part2", "label": "Self-reflection Part 2", "done": len(part2_yes) == len(PART2),
         "detail": f"{len(part2_yes)} of {len(PART2)} Yes"},
        {"id": "part3", "label": "A comment on every element (Part 3)", "done": len(part3_done) == len(elements),
         "detail": f"{len(part3_done)} of {len(elements)} written"},
        {"id": "evidence", "label": "Evidence to show at interview", "done": all(e in evidenced for e in elements),
         "detail": f"{sum(e in evidenced for e in elements)} of {len(elements)} elements have evidence"},
        {"id": "bia", "label": "Building Industry Assessment", "done": bia_ok, "detail": bia_detail},
        {"id": "signed", "label": "Statement signed (Part 4)", "done": app.signed, "detail": "It's your own reflection"},
    ]
    done = sum(i["done"] for i in items)
    strengths = element_strength(doc)
    return {
        "elements": strengths,
        "strength": {k: sum(e["strength"] == k for e in strengths) for k in ("solid", "thin", "none")},
        "percent": round(done / len(items) * 100),
        "done": done,
        "total": len(items),
        "items": items,
        "prepare": [{"id": q["id"], "q": q["q"], "elements": q["elements"]} for q in not_sure],
    }


def view(doc: CareerDocument) -> dict[str, Any]:
    return {
        "application": doc.application.model_dump(),
        "documents": DOCUMENTS,
        "cpd_questions": CPD_QUESTIONS,
        "part1": PART1,
        "part2": PART2,
        "elements": [{**e.model_dump(), "meaning": ELEMENT_MEANING.get(e.id, "")} for e in doc.elements],
        "bia_states": BIA_STATES,
        "readiness": readiness(doc),
    }


# ---- files --------------------------------------------------------------

def files_dir() -> Path:
    return store.career_path().parent / "career-documents"


def save_file(doc_id: str, filename: str, raw: bytes) -> CareerDocument:
    if doc_id not in {d["id"] for d in DOCUMENTS}:
        raise LookupError(doc_id)
    suffix = Path(filename).suffix.lower()
    if suffix not in (".pdf", ".docx", ".doc"):
        raise ValueError("Upload the form as a PDF or Word document.")
    if len(raw) > MAX_FILE_BYTES:
        raise ValueError("That file is over 20 MB.")
    folder = files_dir()
    folder.mkdir(parents=True, exist_ok=True)
    doc = store.load()
    old = doc.application.files.get(doc_id)
    stored = f"{doc_id}{suffix}"
    (folder / stored).write_bytes(raw)
    if old and old.stored != stored:
        (folder / old.stored).unlink(missing_ok=True)
    files = {**doc.application.files, doc_id: UploadedFile(filename=Path(filename).name[:200], stored=stored, size=len(raw),
                                                           at=datetime.now(timezone.utc).isoformat(timespec="seconds"))}
    return store.save(doc.model_copy(update={"application": doc.application.model_copy(update={"files": files})}))


def file_path(doc_id: str) -> tuple[Path, UploadedFile] | None:
    f = store.load().application.files.get(doc_id)
    if not f:
        return None
    path = files_dir() / f.stored
    return (path, f) if path.is_file() else None


def remove_file(doc_id: str) -> CareerDocument:
    doc = store.load()
    f = doc.application.files.get(doc_id)
    if f:
        (files_dir() / f.stored).unlink(missing_ok=True)
    files = {k: v for k, v in doc.application.files.items() if k != doc_id}
    return store.save(doc.model_copy(update={"application": doc.application.model_copy(update={"files": files})}))

