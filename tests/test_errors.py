from collections.abc import Callable

import pytest

from structurelab_rc.errors import StructuredError, blocked, incomplete, invalid_input


@pytest.mark.parametrize(
    ("factory", "code"),
    [(blocked, "blocked"), (incomplete, "incomplete"), (invalid_input, "invalid_input")],
)
def test_factories_have_stable_codes(factory: Callable[..., StructuredError], code: str) -> None:
    error = factory("mensaje", field="fc")
    assert error.code == code
    assert error.message == "mensaje"
    assert error.details == {"field": "fc"}
