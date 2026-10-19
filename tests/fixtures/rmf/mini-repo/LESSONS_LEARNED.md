# Lessons Learned

Authoritative record of lessons learned during the development of this system:
the situation, the pitfall, and the correct solution for each lesson.
Managed by the `learned-lesson-tracker` skill — do not edit the index block or
the entry markers by hand; use `scripts/manage_lessons.py` (init / add / sync /
check / next-id). The index below is machine-readable (TSV between
`LLT:INDEX:BEGIN`/`LLT:INDEX:END` markers) and lists every entry with its
line range.

<!-- LLT:INDEX:BEGIN -->
id	title	category	severity	status	recorded	start_line	end_line
LLT_INDEX_BLOCK	—	—	—	—	—	11	15
LLT-0001	Fixture lesson	testing	high	active	2026-10-18	17	30
<!-- LLT:INDEX:END -->

<!-- LLT:ENTRY:LLT-0001 -->
## LLT-0001 — Fixture lesson

- **Recorded:** 2026-10-18
- **Category:** testing
- **Severity:** high
- **Status:** active
- **Context:** Deterministic fixture data for the SecureTrace RMF bundle tests.
- **Pitfall:** Hand-written index line numbers drift as soon as entries change.
- **Solution:** Generate the index block with the record core instead of editing it by hand.
- **Supersedes:** —
- **Prevention:** —
- **References:** —
