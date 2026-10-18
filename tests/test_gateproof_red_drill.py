"""CI red drill (B1 gate proof): this test MUST fail on CI.

Deliberately planted on a throwaway branch to prove the CI quality job goes
RED when a test fails, and that branch protection / required checks observe
it. This file does not belong on main; the drill branch is deleted after.
"""


def test_gateproof_red_drill():
    assert False, "intentional CI red drill — B1 gate proof (throwaway branch)"
