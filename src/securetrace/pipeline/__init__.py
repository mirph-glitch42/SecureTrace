"""CI/CD gate orchestration helpers.

Intended responsibilities (implemented with backlog B3):
the single source of truth for the ordered gate set (format -> lint ->
docs-check -> build -> test -> secret scan -> dependency audit), shared by
the Makefile, git hooks, and CI workflows, so the three can never drift
apart.
"""

__all__: list[str] = []
