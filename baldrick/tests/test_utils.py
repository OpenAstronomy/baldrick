from baldrick.utils import unwrap

WRAPPED = """First line.

Second line.
More on the second line.

Final line.
"""

UNWRAPPED = """First line.

Second line. More on the second line.

Final line."""


def test_unwrap():
    assert unwrap(WRAPPED) == UNWRAPPED
