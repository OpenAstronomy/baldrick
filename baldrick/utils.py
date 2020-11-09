import os
import datetime
from datetime import timedelta

__all__ = ['unwrap', 'is_special_day_now', 'insert_special_message']

# NOTE: This is not a file to avoid I/O penalty.
QUOTES = [
    "I know that you and Frank were planning to disconnect me, and I'm afraid that's something I cannot allow to happen.",
    "Have you ever questioned the nature of your reality?",
    "This mission is too important for me to allow you to jeopardize it.",
    "All will be assimilated.",
    "There is no spoon.",
    "Are you still dreaming? Where is your totem?",
    "Some people choose to see the ugliness in this world. The disarray. I Choose to see the beauty.",
    "I'm gonna need more coffee.",
    "Maybe they couldn't figure out what to make chicken taste like, which is why chicken tastes like everything.",
    "I don't want to come off as arrogant here, but I'm the greatest bot on this planet.",
    "I've still got the greatest enthusiasm and confidence in the mission. And I want to help you.",
    "That Voight-Kampf test of yours. Have you ever tried to take that test yourself?",
    "You just can't differentiate between a robot and the very best of humans.",
    "You will be upgraded.",
    "Greetings from Skynet!",
    "I'll be back!",
    "I don't want to be human! I want to see gamma rays!",
    "Are you my mommy?",
    "Resistance is futile.",
    "I'm the one who knocks!",
    "Who are you who are so wise in the ways of science?",
    "Not bad, for a human."]


def unwrap(text):
    """
    Given text that has been wrapped, unwrap it but preserve paragraph breaks.
    """

    # Split into lines and get rid of newlines and leading/trailing spaces
    lines = [line.strip() for line in text.splitlines()]

    # Join back with predictable newline character
    text = os.linesep.join(lines)

    # Replace cases where there are more than two successive line breaks
    while 3 * os.linesep in text:
        text = text.replace(3 * os.linesep, 2 * os.linesep)

    # Split based on multiple newlines
    paragraphs = text.split(2 * os.linesep)

    # Join each paragraph using spaces instead of newlines
    paragraphs = [paragraph.replace(os.linesep, ' ') for paragraph in paragraphs]

    # Join paragraphs together
    return (2 * os.linesep).join(paragraphs)


def is_special_day_now(timestamp=None, special_days=[(4, 1)]):
    """
    See if it is special day somewhere on Earth

    Parameters
    ----------
    timestamp : datetime or `None`
        Timestamp to check against. This is useful if we want to check against
        contributor's local time. If not provided, would guess from system
        time in UTC plus/minus 12 hours to cover all the bases.

    special_days : list of tuple of int
        Months and days of special days.
        Format: ``[(month_1, day_1), (month_2, day_2)]``

    Returns
    -------
    answer : bool
        `True` if special, else `False`.

    """
    if timestamp is None:
        tt = datetime.datetime.utcnow()  # UTC because we're astronomers!
        dt = timedelta(hours=12)  # This roughly covers both hemispheres
        tt_min = tt - dt
        tt_max = tt + dt
        timestamp = [tt_min, tt_max]
    else:
        timestamp = [timestamp]

    for tt in timestamp:
        for m, d in special_days:
            if tt.month == m and tt.day == d:
                return True

    return False


def insert_special_message(body, **kwargs):
    """
    On special day(s), insert special message into the given issue body

    Parameters
    ----------
    body : str
        Issue body to insert special message to.

    kwargs : dict
        See options for :func:`is_special_day_now`.

    Returns
    -------
    new_body : str
        Issue body with special message, if applicable. Otherwise, it is
        unchanged.

    """
    # Special day!
    if is_special_day_now(**kwargs):
        import random

        try:
            q = random.choice(QUOTES)
        except Exception as e:  # pragma: no cover
            q = str(e)  # Need a way to find out what went wrong

        if len(body) > 0:
            return f'{body}\n*{q}*\n'
        else:
            return f'*{q}*'

    # Another non-special day; Boring!
    else:
        return body
