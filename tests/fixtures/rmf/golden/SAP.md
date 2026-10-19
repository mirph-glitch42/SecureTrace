# System and Security Assessment Plan (SAP)

Defines how the control baseline in `SSP.md` §3 is assessed: fully local and
offline, from the evidence corpus below (no network access, no wall clock).

## 1. Purpose and scope

Assess the repository at git HEAD `no-git` against the 11-control baseline using only the corpus files listed in §4.

## 2. Control selection

| Control | Title | Method |
|---|---|---|
| ST-01 | Deterministic work records (backlog) | backlog index check |
| ST-02 | Quality-control / lessons history | lessons record check |
| ST-03 | Algorithm / design records | per-doc index check |
| ST-04 | Architecture & requirements traceability | presence |
| SC-01 | Pinned, hashed dependency manifests | presence |
| SC-02 | Secret-scanning policy & hooks | presence |
| CI-01 | Gate definitions (local + CI) | presence |
| QA-01 | Code quality configuration | presence |
| REL-01 | License & packaging metadata | presence |
| REL-02 | Release pipeline with provenance | presence |
| SB-01 | Software bill of materials | presence |

## 3. Assessment method

- Collect: hash (SHA-256) and line-count every corpus file; parse the process
  state (backlog, lessons, algorithm records) with the SecureTrace B3 cores.
- Evaluate: a control is SATISFIED iff every evidence file it cites is present
  and any live checker (backlog index, lessons record, per-doc index) passes.
- Render: the SSP/SAP/SAR/POA&M are pure renderings of the snapshot;
  `manifest.json` binds every corpus file and document to its SHA-256.

## 4. Evidence corpus

| Path | Lines | SHA-256 |
|---|---|---|
| `.github/workflows/ci.yml` | 8 | b6f2095af1b23ca1c0037a334f85cddfe6133998b9da20fbf92a9fdbf1e67a3c |
| `.github/workflows/release.yml` | 10 | 8988b46868100970ab2abbad6b4a4840e7d533e38ea7433ce5672fb7176a3cda |
| `.gitleaks.toml` | 4 | 15f533c7a592cebc0c1355988a044e50df70fa0169a8d29ce4cfc00fc6cfaa29 |
| `ARCHITECTURE.md` | 3 | f406715c09d938caa8854a0cd5264d9ca761d5022e2a42e0750e56dd5efba05a |
| `BACKLOG.md` | 37 | 49453f5a7006a0ec81eb8f790871faa99665e24862c44498b20fd3d0eeacf8dd |
| `LESSONS_LEARNED.md` | 29 | 89688e8df6e2952c5b17cccb88402978cfba6ac1f546f49142fa1556bca70105 |
| `LICENSE` | 21 | b942f996a47440b3f9e2ef70206e8f5ca58e28ad633cfdaaaf0113fc0ff0bcbb |
| `Makefile` | 4 | 2c6c86af8325313a9856d33530c9a3b10a5587b9380a93406fd7cb9be5ba41ac |
| `README.md` | 3 | e66d6d197eda6e209308e46c379bb79b63d8eb7484ce8503c47f049c70be44f2 |
| `algorithms/INDEX.md` | 5 | 0cf1062761484390f726eb7219054c8da11440d5cf4cad50dba75987ac0c4d31 |
| `algorithms/fixture.md` | 18 | 46e0650acd2c3988e8eb5571e341026792a7ad614f0fbffc3728addea51d1968 |
| `dist/sbom.json` | 6 | ef1aad3fd85b54261ea4a2dac17512f0deca5a1ea71e56de1c16e65898c189ac |
| `docs/dow-requirements.md` | 3 | a6ce29ee889b66144079101c08c11f39fa0cde3ecb21ecc3eda68ea604413d94 |
| `hooks/pre-commit` | 3 | d03171e1259a99147a8b6ad260caaea51c31897da5f02274ef95dc294908b1d4 |
| `hooks/pre-push` | 3 | d03171e1259a99147a8b6ad260caaea51c31897da5f02274ef95dc294908b1d4 |
| `pyproject.toml` | 4 | 731bd52c0789f3d854ef4cfc9e8dcaf40dce846909e29bb9308077b177ee54a6 |
| `requirements-dev.in` | 1 | 56fdf2dab12cce8330b2c121571c953799725e98c6185993a4b7761cdea9f227 |
| `requirements-dev.txt` | 2 | 71ddb6315d482c75b765a7f108d24ac0c7d0ae4f0709e021701ed6445968aed1 |
| `requirements.in` | 1 | 56fdf2dab12cce8330b2c121571c953799725e98c6185993a4b7761cdea9f227 |
| `requirements.txt` | 2 | 71ddb6315d482c75b765a7f108d24ac0c7d0ae4f0709e021701ed6445968aed1 |
| `sonar-project.properties` | 2 | cb64dc1c0bc0526bdba7eb433bef5ffa69e4ebb236beac8b5e720137e98cf8b7 |
