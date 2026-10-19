# System Security Plan (SSP)

SecureTrace "Assess Only" RMF deliverable — SSP scaffold. Generated offline
from repository state by `securetrace rmf build`; `manifest.json` binds this
document to the exact evidence bytes.

## 1. System overview

SecureTrace is agentic tooling for secure, traceable software development:
deterministic backlogs, lessons learned, algorithm records, CI/CD gates, and
DoW RMF package deliverables (see `docs/dow-requirements.md`).

Assessed at git HEAD `no-git`; control catalog v1; evidence corpus: 21 file(s).

## 2. Work and quality records

- Backlog: 2 item(s); DONE 1, OPEN 1; open: B2
- Lessons learned: 1 entry(ies); high 1
- Algorithm / design records: 1 document(s) — `algorithms/fixture.md`

## 3. Control baseline

| Control | Title | Method | Evidence |
|---|---|---|---|
| ST-01 | Deterministic work records (backlog) | backlog index check | `BACKLOG.md` |
| ST-02 | Quality-control / lessons history | lessons record check | `LESSONS_LEARNED.md` |
| ST-03 | Algorithm / design records | per-doc index check | `algorithms/INDEX.md`, `algorithms/fixture.md` |
| ST-04 | Architecture & requirements traceability | presence | `ARCHITECTURE.md`, `docs/dow-requirements.md` |
| SC-01 | Pinned, hashed dependency manifests | presence | `requirements.in`, `requirements-dev.in`, `requirements.txt`, `requirements-dev.txt` |
| SC-02 | Secret-scanning policy & hooks | presence | `.gitleaks.toml`, `hooks/pre-commit`, `hooks/pre-push` |
| CI-01 | Gate definitions (local + CI) | presence | `Makefile`, `.github/workflows/ci.yml` |
| QA-01 | Code quality configuration | presence | `pyproject.toml`, `sonar-project.properties` |
| REL-01 | License & packaging metadata | presence | `LICENSE`, `pyproject.toml` |
| REL-02 | Release pipeline with provenance | presence | `.github/workflows/release.yml` |
| SB-01 | Software bill of materials | presence | `dist/sbom.json` |

## 4. Supply chain

- Pinned, hashed dependency manifests: satisfied (`requirements.in`, `requirements-dev.in`, `requirements.txt`, `requirements-dev.txt`)
- Secret-scanning policy & hooks: satisfied (`.gitleaks.toml`, `hooks/pre-commit`, `hooks/pre-push`)
- Software bill of materials: satisfied (`dist/sbom.json`)

## 5. Related documents

- `docs/dow-requirements.md` — DoD software RMF / Software Acquisition Pathway reference
- `ARCHITECTURE.md` — module map
- `LESSONS_LEARNED.md` — quality-control history
- `algorithms/` — algorithm / design records
