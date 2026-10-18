"""RMF deliverable generation (skeleton — lands with backlog B4).

Planned public API:
- ``collect_evidence(repo) -> Evidence``: snapshot of CI results, SBOM,
  audits, and skill documents.
- ``render_ssp/render_sap/render_sar/render_poam(evidence) -> str``:
  document rendering.
- ``package(evidence, outdir) -> Path``: assemble the deliverable bundle.
"""
