"""SecureTrace — agentic tooling for secure, traceable software development.

SecureTrace manages the artifacts that make agent-performed programming
auditable and compliant with US Department of War (DoW) software lifecycle
requirements: deterministic agentic backlogs, lessons-learned records,
algorithm description documents, CI/CD gate state, architecture documents,
and software RMF package deliverables (SSP/SAP/SAR/POA&M/ATO evidence)
built incrementally as the software is developed.

Subpackages (skeleton — responsibilities land with their backlog items):

- ``securetrace.backlog``     — deterministic backlog parsing/management
- ``securetrace.lessons``     — lessons-learned record management
- ``securetrace.algorithms``  — algorithm document registry management
- ``securetrace.rmf``         — RMF deliverable (package) generation
- ``securetrace.pipeline``    — CI/CD gate orchestration helpers
"""

__version__ = "0.1.1"

__all__ = ["__version__"]
