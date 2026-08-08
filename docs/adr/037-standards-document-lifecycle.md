# ADR 037 — Engineering standards document lifecycle

## Status
Accepted

## Context
The private Engineering Standards Library is now a citation-bearing evidence source for SirisHydro. Physically overwriting or deleting a PDF would make historical citations ambiguous or incorrect.

## Decision
- A standards document ID is immutable and refers to one exact uploaded PDF/revision.
- Replacing a standard creates a new document ID and increments a local library revision number.
- The previous revision is archived and linked using `superseded_by_id`; the new revision records `supersedes_id`.
- Normal search returns active revisions only. Archived/superseded revisions can be included explicitly for historical review.
- Archive is a soft-delete operation. The original PDF, index and metadata remain available so historical citations continue to resolve.
- A manually archived document may be restored only when it has not been superseded by a newer revision.
- Library revision numbers are included in citations after revision 1 to disambiguate locally replaced copies even when publisher metadata is unchanged.
- Existing pre-lifecycle documents are treated as active revision 1 for backward compatibility.

## Consequences
SirisHydro can safely preserve old evidence packets and citations while the private library evolves. Storage usage grows with retained revisions; a future retention/export workflow may manage old revisions, but destructive deletion must remain an explicit administrative operation rather than the default lifecycle action.
