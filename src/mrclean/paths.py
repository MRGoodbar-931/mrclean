"""Data directory resolution and the leak guard that protects it.

Personal data must never live where git, or a sync client, can pick it up.
:func:`resolve_data_dir` is the single entry point every other module uses;
it refuses to hand back a path that is inside a git work tree or a known
cloud-sync folder.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from mrclean.errors import UnsafeDataDirError

log = logging.getLogger(__name__)

APP_NAME = "mrclean"
ENV_DATA_DIR = "MRCLEAN_DATA_DIR"

# Folder names that indicate a cloud-sync client. Matching is case-insensitive
# and checks each path component's prefix (e.g. "OneDrive - Contoso").
_SYNC_MARKERS = ("onedrive", "dropbox", "google drive", "googledrive", "icloud", "box sync")


def default_data_dir() -> Path:
    """Return the per-user, non-synced default location for MRclean data."""
    if sys.platform == "win32":
        # Not %LOCALAPPDATA%: packaged (MSIX) apps such as the Claude desktop app
        # get AppData writes silently redirected into a per-app container, so
        # the same path would point at different folders depending on which
        # process asks. The profile root isn't virtualised.
        return Path.home() / f".{APP_NAME}"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_NAME
    base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(base) / APP_NAME


def find_git_worktree(path: Path) -> Path | None:
    """Return the root of the git work tree containing ``path``, if any.

    Walks up from ``path`` (or its nearest existing ancestor) looking for a
    ``.git`` entry. ``.git`` may be a directory or, for worktrees and
    submodules, a file; both count.
    """
    current = path
    while not current.exists() and current != current.parent:
        current = current.parent
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def _sync_marker(path: Path) -> str | None:
    for part in path.parts:
        lowered = part.lower()
        for marker in _SYNC_MARKERS:
            if lowered.startswith(marker):
                return part
    return None


def _is_msix_redirect(path: Path) -> bool:
    """True if ``path`` lies in a packaged app's virtualised AppData container.

    Windows redirects AppData writes from MSIX-packaged apps (e.g. the Claude
    desktop app) to ``...\\AppData\\Local\\Packages\\<app>\\LocalCache\\...``.
    Once the folder exists, ``resolve()`` from inside the app returns that path.
    """
    parts = [part.lower() for part in path.parts]
    for i in range(len(parts) - 2):
        if parts[i] == "packages" and parts[i + 2] == "localcache":
            return True
    return False


def check_data_dir_safe(path: Path, *, allow_synced: bool = False) -> Path:
    """Validate ``path`` as a data directory and return it resolved.

    Raises:
        UnsafeDataDirError: if the path is inside a git work tree, or inside a
            cloud-sync folder and ``allow_synced`` is false.
    """
    resolved = path.expanduser().resolve()
    repo = find_git_worktree(resolved)
    if repo is not None:
        raise UnsafeDataDirError(
            f"Data dir {resolved} is inside the git work tree at {repo}. "
            f"Personal data must never live in a repository. Set {ENV_DATA_DIR} "
            "to a location outside any repo."
        )
    if _is_msix_redirect(resolved):
        raise UnsafeDataDirError(
            f"Data dir {resolved} is inside a packaged-app container (MSIX AppData "
            "redirection). Other programs, including git hooks started from a normal "
            f"terminal, would see a different folder. Set {ENV_DATA_DIR} to a folder "
            "outside AppData."
        )
    marker = _sync_marker(resolved)
    if marker and not allow_synced:
        raise UnsafeDataDirError(
            f"Data dir {resolved} is inside what looks like a cloud-sync folder ({marker!r}). "
            "Synced copies of personal data defeat local-only storage. Choose another "
            "location, or pass allow_synced=True if you've confirmed it is not synced."
        )
    return resolved


def resolve_data_dir(*, create: bool = False, allow_synced: bool = False) -> Path:
    """Return the validated data directory, from ``$MRCLEAN_DATA_DIR`` or the default.

    With ``create=True`` the directory is created with owner-only permissions
    (where the OS supports POSIX modes).
    """
    raw = os.environ.get(ENV_DATA_DIR)
    path = Path(raw) if raw else default_data_dir()
    resolved = check_data_dir_safe(path, allow_synced=allow_synced)
    if create:
        resolved.mkdir(mode=0o700, parents=True, exist_ok=True)
        if sys.platform != "win32":
            resolved.chmod(0o700)
        log.info("Data directory ready")
    return resolved
