"""Starting content for the career module (ADR 111): the pathways to
Chartered (CPEng), the National Engineering Register and Victorian
registration, the Stage 2 competency elements, and the CPD requirement.

These were current when written (October 2026), but bodies change their
rules: everything here is a starting point Brad edits in the Career tab, and
each pathway links to the body's own page to check against.
"""

from __future__ import annotations

from typing import Any

# Engineers Australia CPD for Chartered and NER: 150 hours over a rolling
# three years, of which at least 50 in the area of practice, 10 in risk
# management and 15 in business and management.
CPD_REQUIREMENT: dict[str, Any] = {
    "years": 3,
    "total": 150,
    "minimums": {"area": 50, "risk": 10, "business": 15},
}

CPD_CATEGORIES = {
    "area": "Area of practice",
    "risk": "Risk management",
    "business": "Business & management",
    "other": "Other",
}

# Engineers Australia's Stage 2 Competency Standard for Professional
# Engineers: 16 elements in four units. CPEng means showing all 16.
STAGE2_ELEMENTS: list[dict[str, str]] = [
    {"id": "1", "unit": "Personal commitment", "title": "Deal with ethical issues"},
    {"id": "2", "unit": "Personal commitment", "title": "Practise competently"},
    {"id": "3", "unit": "Personal commitment", "title": "Responsibility for engineering activities"},
    {"id": "4", "unit": "Obligation to community", "title": "Develop safe and sustainable solutions"},
    {"id": "5", "unit": "Obligation to community", "title": "Engage with the relevant community and stakeholders"},
    {"id": "6", "unit": "Obligation to community", "title": "Identify, assess and manage risks"},
    {"id": "7", "unit": "Obligation to community", "title": "Meet legal and regulatory requirements"},
    {"id": "8", "unit": "Value in the workplace", "title": "Communication"},
    {"id": "9", "unit": "Value in the workplace", "title": "Performance"},
    {"id": "10", "unit": "Value in the workplace", "title": "Taking action"},
    {"id": "11", "unit": "Value in the workplace", "title": "Judgement"},
    {"id": "12", "unit": "Technical proficiency", "title": "Advanced engineering knowledge"},
    {"id": "13", "unit": "Technical proficiency", "title": "Local engineering knowledge"},
    {"id": "14", "unit": "Technical proficiency", "title": "Problem analysis"},
    {"id": "15", "unit": "Technical proficiency", "title": "Creativity and innovation"},
    {"id": "16", "unit": "Technical proficiency", "title": "Evaluation"},
]


def _steps(*items: tuple[str, str, str]) -> list[dict[str, Any]]:
    return [{"id": sid, "title": title, "detail": detail, "status": "todo", "note": "", "done_on": None}
            for sid, title, detail in items]


PATHWAYS: list[dict[str, Any]] = [
    {
        "id": "ea-member",
        "name": "Engineers Australia membership",
        "body": "Engineers Australia",
        "url": "https://www.engineersaustralia.org.au/membership",
        "summary": "Member grade (MIEAust) is the base for Chartered and the National Engineering Register.",
        "steps": _steps(
            ("qualification", "Qualification recognised",
             "BE (Hons) Civil, University of Canterbury (2019): a Washington Accord degree, so Stage 1 should be recognised without a separate assessment."),
            ("join", "Join as a Member (MIEAust)", "Apply through Engineers Australia's portal; Engineering New Zealand membership history helps."),
            ("cpd-records", "CPD recorded in Engineers Australia", "Log CPD in the Engineers Australia portal; import it here to track the 3-year totals."),
        ),
    },
    {
        "id": "cpeng",
        "name": "Chartered Professional Engineer (CPEng)",
        "body": "Engineers Australia",
        "url": "https://engineersaustralia.org.au/publications/stage-2-competency-standard-professional-engineers",
        "summary": "Show all 16 Stage 2 competency elements, then a professional interview.",
        "steps": _steps(
            ("self-assess", "Self-assess against the 16 elements", "Use the Competencies view: every element needs evidence from your own work."),
            ("evidence", "Collect evidence for every element", "Projects, reports, reviews and decisions you led. Link them in Competencies."),
            ("route", "Choose the application route", "For example the Engineering Competency Claim. Check Engineers Australia's current options."),
            ("referees", "Line up referees and a verifier", "People who supervised or know your work and can confirm your claims."),
            ("write", "Write the competency claim", "One claim per element, in your own words, citing your evidence."),
            ("submit", "Submit the application", ""),
            ("interview", "Professional interview", "Discuss your claims and experience with assessors."),
            ("chartered", "Chartered", "Then keep up 150 hours of CPD every 3 years."),
        ),
    },
    {
        "id": "ner",
        "name": "National Engineering Register (NER)",
        "body": "Engineers Australia",
        "url": "https://www.engineersaustralia.org.au/national-engineering-register",
        "summary": "A public register of competent engineers; usually applied for alongside Chartered.",
        "steps": _steps(
            ("apply", "Apply for NER listing", "Usually alongside the Chartered application."),
            ("listed", "Listed on the NER", "Keep CPD current to stay listed."),
        ),
    },
    {
        "id": "vic-rpe",
        "name": "Registered Professional Engineer, Victoria (civil)",
        "body": "Business Licensing Authority (Victoria)",
        "url": "https://www.consumer.vic.gov.au/licensing-and-registration/engineers",
        "summary": "Registration is a legal requirement for civil engineering services in Victoria unless you work under the direct supervision of a registered engineer.",
        "steps": _steps(
            ("check", "Check what your current work needs", "Work under the direct supervision of a registered engineer, or to a prescriptive standard, doesn't need your own registration."),
            ("assessment", "Assessment", "Chartered members of Engineers Australia (or members on the NER) can apply without further assessment; otherwise an approved assessment entity (Engineers Australia, IPWEA, ...) assesses qualifications and experience. Allow 6 to 8 weeks."),
            ("apply", "Apply to the Business Licensing Authority", "Allow about 28 days for processing."),
            ("registered", "Registered (civil)", "Keep CPD up and renew on time."),
        ),
    },
]

# Second Brain notes that hold the career story (shown and linked in the tab).
BRAIN_NOTES = ["CPEng Chartership", "Brad's Career History"]
