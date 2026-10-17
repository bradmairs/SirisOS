"""Stage 2 competency claim drafts (ADR 111): for each of the 16 elements,
a first draft built from the evidence Brad has tagged with it, ready to
finish in Siris.

The draft is always built the same way from the evidence (the structure
Engineers Australia asks for: what the situation was, what you did, what
came of it, and how that shows the element). If a local Ollama model is
configured, it can also write it up as first-person prose; that's only ever
offered as a starting point, and every claim in it still has to be checked.
"""

from __future__ import annotations

from typing import Any

from app.career.store import CareerDocument, Element, Evidence
from app.services.ollama_service import OllamaChatClient

# What evidence for each element usually looks like, for elements with none yet.
PROMPTS: dict[str, str] = {
    "1": "A time you raised or handled an ethical concern: a conflict of interest, a shortcut you refused, a duty of care.",
    "2": "Work where you stayed inside your competence: checking standards, asking for review, or getting up to speed first.",
    "3": "Something you were accountable for: a design you signed off, a package you owned, supervising others' work.",
    "4": "A design choice made for safety or sustainability: whole-of-life cost, energy, safety in design, the environment.",
    "5": "Working with the community or stakeholders: consultation, landowners, councils, customers, other utilities.",
    "6": "A risk assessment, HAZOP or safety-in-design review you contributed to or led, and what changed because of it.",
    "7": "Meeting legal or regulatory requirements: approvals, permits, the Water Act, EPA, WorkSafe, codes and standards.",
    "8": "Communication: a report, a presentation to decision makers, explaining a technical issue to non-engineers.",
    "9": "Delivering to time, cost and quality: a programme you kept, a budget you managed, a quality issue you fixed.",
    "10": "Taking the initiative: a problem you spotted and acted on without being asked.",
    "11": "A judgement call with incomplete information, the options you weighed, and why you chose as you did.",
    "12": "Applying advanced engineering knowledge: hydraulic modelling, structural design, analysis beyond the routine.",
    "13": "Local knowledge: Victorian or Australian standards, local conditions, the authority's own requirements.",
    "14": "Analysing a problem: investigating a failure, defining the real problem, gathering and testing data.",
    "15": "Creativity and innovation: a new approach, a tool you built, a better way of doing a routine task.",
    "16": "Evaluating outcomes: checking whether a solution worked, a post-implementation review, lessons learned.",
}

SYSTEM = (
    "You help a civil engineer in Victoria, Australia draft a Stage 2 competency claim for Chartered (CPEng) "
    "with Engineers Australia. Write in the first person, past tense, in plain Australian English. Use only "
    "the facts given; never invent projects, numbers, dates or outcomes. Where a detail is missing, leave a "
    "bracketed placeholder like [outcome]. Structure: the situation, what I did, the result, and how it shows "
    "the element. 200 to 350 words. No heading."
)


def element(doc: CareerDocument, element_id: str) -> Element | None:
    return next((e for e in doc.elements if e.id == element_id), None)


def evidence_for(doc: CareerDocument, element_id: str) -> list[Evidence]:
    items = [ev for ev in doc.evidence if element_id in ev.elements]
    return sorted(items, key=lambda ev: ev.date or "", reverse=True)


def title(el: Element) -> str:
    return f"CPEng claim draft – E{el.id} {el.title}"


def _evidence_lines(evidence: list[Evidence]) -> list[str]:
    lines = []
    for ev in evidence:
        when = f" ({ev.date})" if ev.date else ""
        lines.append(f"### {ev.title}{when}")
        lines.append(ev.summary.strip() or "_No summary yet: add what happened, your role and the outcome._")
        for link in ev.links:
            lines.append(f"- [{link.label}]({link.url})")
        lines.append("")
    return lines


def draft(doc: CareerDocument, el: Element) -> str:
    """The structured draft, in Markdown."""
    evidence = evidence_for(doc, el.id)
    lines = [
        f"**Element {el.id}: {el.title}** · {el.unit}",
        "",
        f"Draft for my Stage 2 competency claim ({doc.profile.discipline}, {doc.profile.area_of_practice}). "
        "Built by SirisOS from the evidence I tagged; finish it in my own words.",
        "",
    ]
    if not evidence:
        lines += [
            "## No evidence tagged yet",
            "",
            f"Ideas: {PROMPTS.get(el.id, 'Work from your own projects that shows this element.')}",
            "",
            "Add it in SirisOS → Career → Competencies, tag this element, and draft again.",
        ]
        return "\n".join(lines).strip() + "\n"
    lines += ["## Evidence", ""] + _evidence_lines(evidence)
    lines += [
        "## Claim (to finish)",
        "",
        "- **Situation:** [the project, my role and what was at stake]",
        "- **What I did:** [the actions I personally took, and the decisions I made]",
        "- **Result:** [what came of it: measurable where possible]",
        f"- **How this shows {el.title.lower()}:** [link my actions to the element]",
        "",
    ]
    return "\n".join(lines).strip() + "\n"


async def prose(doc: CareerDocument, el: Element, client: OllamaChatClient | None = None) -> str | None:
    """First-person prose from the local model, or None if there's no model or no evidence."""
    evidence = evidence_for(doc, el.id)
    client = client or OllamaChatClient()
    if not evidence or not client.enabled:
        return None
    facts = "\n\n".join(f"{ev.title}{f' ({ev.date})' if ev.date else ''}:\n{ev.summary.strip()}" for ev in evidence)
    prompt = (f"Element {el.id}: {el.title} (unit: {el.unit}).\n"
              f"Discipline: {doc.profile.discipline}; area of practice: {doc.profile.area_of_practice}.\n\n"
              f"My evidence:\n\n{facts}")
    return await client.complete(system=SYSTEM, prompt=prompt)


def listing(doc: CareerDocument) -> list[dict[str, Any]]:
    return [
        {"id": el.id, "unit": el.unit, "title": el.title, "note_title": title(el),
         "evidence": [ev.id for ev in evidence_for(doc, el.id)], "prompt": PROMPTS.get(el.id, "")}
        for el in doc.elements
    ]
