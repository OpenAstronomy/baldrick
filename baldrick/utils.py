import os

__all__ = ['unwrap']


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
