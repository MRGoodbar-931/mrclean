import logging

from mrclean.logging_setup import REDACTED, RedactingFilter


def _emit(filt, msg, *args, exc=None):
    logger = logging.getLogger("test.redact")
    record = logger.makeRecord("test.redact", logging.INFO, __file__, 1, msg, args, exc)
    filt.filter(record)
    return record


def test_redacts_email_and_phone_in_args():
    rec = _emit(RedactingFilter(), "contact %s / %s", "someone@example.com", "(206) 555-0142")
    assert rec.getMessage() == f"contact {REDACTED} / {REDACTED}"


def test_redacts_registered_literals_case_insensitive_longest_first():
    filt = RedactingFilter()
    filt.add_literals(["Jane", "Jane Q Public"])
    rec = _emit(filt, "found JANE Q PUBLIC and jane")
    assert rec.getMessage() == f"found {REDACTED} and {REDACTED}"


def test_redacts_exception_text():
    filt = RedactingFilter()
    filt.add_literals(["Jane Q Public"])
    try:
        raise ValueError("lookup failed for Jane Q Public")
    except ValueError:
        import sys

        rec = _emit(filt, "boom", exc=sys.exc_info())
    assert "Jane Q Public" not in rec.exc_text
    assert REDACTED in rec.exc_text
