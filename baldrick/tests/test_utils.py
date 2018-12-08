import datetime
import random
import sys

import pytest

from baldrick.utils import unwrap, is_special_day_now, insert_special_message

WRAPPED = """First line.

Second line.
More on the second line.

Final line.
"""

UNWRAPPED = """First line.

Second line. More on the second line.

Final line."""


@pytest.mark.xfail(sys.platform.startswith('win'),
                   reason='Endline comparison fails on Windows')
def test_unwrap():
    assert unwrap(WRAPPED) == UNWRAPPED


@pytest.mark.parametrize(
    ('month', 'day', 'hour', 'answer'),
    [(4, 3, 0, False),
     (4, 1, 0, True),
     (3, 31, 22, False)])
def test_is_special_day_1(month, day, hour, answer):
    """User defined timestamps with default special day."""
    timestamp = datetime.datetime(2018, month, day, hour=hour)
    assert is_special_day_now(timestamp=timestamp) is answer


def test_is_special_day_2():
    """System timestamp with default special day."""
    tt = datetime.datetime.utcnow()
    undeterministic = [(3, 31), (4, 1), (4, 2)]

    if (tt.month, tt.day) in undeterministic:
        pytest.skip('Test may either pass or fail')

    assert not is_special_day_now()


def test_is_special_day_3():
    """Special messages with custom settings."""
    random.seed(1234)
    special_days = [(4, 1), (1, 1)]
    t_special = datetime.datetime(2019, 1, 1)
    t_boring = datetime.datetime(2018, 12, 1)
    body = 'Some boring comment.'

    assert insert_special_message(
        body, timestamp=t_boring, special_days=special_days) == body

    # NOTE: Update when QUOTES is modified.
    assert '\n*Greetings from Skynet!*\n' in insert_special_message(
        body, timestamp=t_special, special_days=special_days)
    assert '\n*All will be assimilated.*\n' in insert_special_message(
        body, timestamp=t_special, special_days=special_days)
