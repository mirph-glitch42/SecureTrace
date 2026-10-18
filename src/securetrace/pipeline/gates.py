"""Gate set definition (skeleton — lands with backlog B3).

Planned public API:
- ``GATES: tuple[str, ...]``: canonical ordered gate names.
- ``run_gate(name, context) -> GateResult``: dispatch one gate.
- ``run_all(context) -> list[GateResult]``: run the full set, cheapest first.
"""
