"""Exception hierarchy for MRclean."""


class MRcleanError(Exception):
    """Base class for all MRclean errors."""


class UnsafeDataDirError(MRcleanError):
    """The configured data directory could leak personal data (e.g. it is inside a git repo)."""


class PIIGuardError(MRcleanError):
    """The PII guard cannot run safely (e.g. no identifiers registered)."""
