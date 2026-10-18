# DoW / DoD Software Lifecycle Requirements

> Authoritative requirements reference for SecureTrace (backlog B2).
> **Access date: 2026-10-18.** All sources below were retrieved on that date;
> re-verify before citing externally — policy documents are living documents.

SecureTrace exists so that software *built by programming agents* carries the
same assurance artifacts the Department of War (DoW) / Department of Defense
(DoD) expects of human-built software: RMF deliverables, Software Acquisition
Pathway (SWP) cadence, and continuous (Assess Only / cATO-style) evidence.

## 1. Risk Management Framework (RMF)

### 1.1 DoDI 8510.01 — *Risk Management Framework for DoD Systems* (Jul 19, 2022)

The controlling policy. Key points for SecureTrace:

- Implements **NIST SP 800-37** RMF: **Prepare → Categorize → Select → Implement → Assess → Authorize → Monitor** (7 steps).
- Applies to **all DoD systems regardless of acquisition pathway** — RMF obligations do not disappear under SWP.
- **Software/technologies below the system level require no ATO of their own, but must complete an "Assess Only" RMF assessment.** This is the single most important design input: SecureTrace's core job is to produce the Assess Only evidence bundle as software is built.
- Referenced standards: NIST SP 800-30 (risk assessment), 800-37 (RMF), 800-39 (security categorization), 800-53/53A (controls), 800-137 (cloud), CNSSI 1253/1254, CNSS Policy 12253-series (CNSS Policy 22), DoDD 8000.01, DoDI 8500.01.
- **Deliverables (system level):** Security Assessment Plan (SAP), System Security Plan (SSP), Security Assessment Report (SAR), Plan of Action & Milestones (POA&M), Authorization to Operate (ATO) package.
- **DISA RMF Knowledge Service (KS)** is the guidance/implementation authority for DoD RMF.

### 1.2 Related policy

| Source | Role |
|---|---|
| **DoDI 8500.01** *Cybersecurity* | DoD cybersecurity program: Component CISOs, ATO governance, workforce training (DoDD 8140.01). |
| **32 CFR Part 111** | Security requirements for **National Security Systems** (NSA-issued, more stringent than NIST 800-53). |
| **NIST SP 800-218 (SSDF)** | Secure Software Development Framework — the secure-development practices baseline referenced by SWP guidance. |

## 2. THE SOFTWARE ACQUISITION PATHWAY (SWP)

### 2.1 DoDI 5000.87 — *Operation of the Software Acquisition Pathway* (Oct 2, 2020)

Policy basis (Public Law 116-92 §800). Key points:

- SWP is a distinct acquisition pathway for software, with **two sub-paths**:
  - **Application software** — delivered on commercial hardware/cloud, for end users.
  - **Embedded software** — for weapon systems / mission-critical embedded platforms.
- The **Decision Authority (DA) records the pathway choice in the acquisition decision memorandum**; existing programs may transition into SWP.
- **Semi-annual data reporting** to USD(A&S); **value assessments at least annually after fielding**.
- Intent: faster, iterative, lower-friction software delivery without abandoning governance.

### 2.2 DoD SWP + RMF integration guidance

The operational model that SecureTrace operationalizes:

- **Rapid iterative delivery**: increments **≤ 6 months**, bias to as-frequent-as-possible releases; "field in hours/days" where risk allows.
- **DevSecOps as the delivery discipline**; **cATO (Continuous ATO)** and RMF "at the speed of relevance" — assessment follows the release, not the other way around.
- Two-phase program model:
  1. **Planning Phase** — define capability needs; develop strategies/roadmaps (acquisition, contracts, test, IP, cybersecurity, product support); **identify target ATO and common controls** to inherit.
  2. **Execution Phase** — active user engagement, architecture design, MVP, iterative test & evaluation, release, monitor. Explicit posture: *software is never done*.
- **Assess Only construct** = due-diligence review of the software's **function, environment, quality control, and data usage**; leverage ATO'd/cATO'd development environments; **automate control verification**; rely on **reciprocity** between acquirer and developer.

### 2.3 Current practice confirmation

- DoW CTO *Systems Engineering & SWP* paper (Jan 2026) confirms SWP remains current DoW practice and pairs it with modern systems engineering (SEMOD), MOSA, and Agile/Lean.
- DoD SWP team guidance (DAU portal) notes programs not subject to JCICS until the new software-requirements approach is agreed; viability + effectiveness demonstrated within 1 year of first funds obligated; increments at least every 6 months.

## 3. What SecureTrace must produce (mapping)

| DoW/DoD requirement | SecureTrace artifact | Backlog |
|---|---|---|
| Assess Only evidence (function, environment, QC, data usage) | Deterministic, dated **evidence bundle** assembled from CI state | B4 |
| SSP | SSP scaffold rendered from architecture docs + gate evidence | B4 |
| SAP | SAP scaffold: control selection + assessment method (automated gates) | B4 |
| SAR | SAR with every cited control mapped to ≥ 1 evidence file (asserted in tests) | B4 |
| POA&M | POA&M from failing controls / open backlog items | B4 |
| cATO / speed-of-relevance | Evidence bundle regenerated per release (tag-triggered) | B4/B5 |
| DevSecOps discipline | Local + CI gates (this repo's own gates are the reference implementation) | B1 |
| Deterministic agentic process records | BACKLOG.md, LESSONS_LEARNED.md, algorithms/ (all machine-indexed, staleness-checked) | B1/B3 |
| Supply-chain evidence | Pinned hashed lockfiles + CycloneDX SBOM per CI run and per release | B1/B5 |

## 4. Sources (retrieved 2026-10-18)

| Source | URL |
|---|---|
| DoDI 8510.01 *RMF for DoD Systems* (Jul 19, 2022) | https://www.esd.whs.mil/Portals/54/Documents/DD/issuances/dodi/851001p.pdf |
| DoDI 5000.87 *Operation of the Software Acquisition Pathway* (Oct 2, 2020) | https://www.esd.whs.mil/Portals/54/Documents/DD/issuances/dodi/500087p.pdf |
| DoD SWP + RMF integration guidance | https://dodcio.defense.gov/Portals/0/Documents/Library/SWAPathwayIntegration-RMF.PDF |
| DoW CTO — Systems Engineering & SWP paper (Jan 2026) | https://www.cto.mil/wp-content/uploads/2026/01/SE-SWP-Paper-final-22Dec25-updated20Jan2026.pdf |
| DoD SWP team / guidance portal (DAU) | https://aaf.dau.edu/aaf/software |
| RMF Knowledge Service (KS) | https://rmfks.osd.mil (portal: https://rmfks.osd.mil/rmf/Pages/default.aspx) |
| NIST SP 800-218 (SSDF) | https://csrc.nist.gov/publications/detail/sp/800-218/final |
| 32 CFR Part 111 (NSA) | https://www.acq.osd.mil/ie/ssp/ |
