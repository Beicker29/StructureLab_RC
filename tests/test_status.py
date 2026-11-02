import random

import pytest
from hypothesis import given
from hypothesis import strategies as st

from structurelab_rc.domain.status import Status, aggregate

PASS, FAIL, INC, BLOCK = Status.PASS, Status.FAIL, Status.INCOMPLETE, Status.BLOCKED


@pytest.mark.parametrize(
    ("statuses", "expected"),
    [
        ([PASS], PASS),
        ([FAIL], FAIL),
        ([INC], INC),
        ([BLOCK], BLOCK),
        ([FAIL, PASS], FAIL),
        ([FAIL, INC], FAIL),
        ([FAIL, BLOCK], FAIL),
        ([INC, PASS], INC),
        ([INC, BLOCK], INC),
        ([BLOCK, PASS], BLOCK),
        ([FAIL, INC, PASS], FAIL),
        ([FAIL, BLOCK, PASS], FAIL),
        ([FAIL, INC, BLOCK], FAIL),
        ([INC, BLOCK, PASS], INC),
        ([FAIL, INC, BLOCK, PASS], FAIL),
    ],
)
def test_every_combination(statuses: list[Status], expected: Status) -> None:
    assert aggregate(statuses) is expected


def test_no_checks_is_incomplete() -> None:
    assert aggregate([]) is INC


def test_accepts_a_generator() -> None:
    assert aggregate(s for s in (PASS, FAIL)) is FAIL


@given(st.lists(st.sampled_from(Status), min_size=1), st.randoms())
def test_order_does_not_matter(statuses: list[Status], rng: random.Random) -> None:
    shuffled = statuses.copy()
    rng.shuffle(shuffled)
    assert aggregate(shuffled) is aggregate(statuses)
