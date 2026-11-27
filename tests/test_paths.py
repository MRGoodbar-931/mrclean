import pytest

from mrclean.errors import UnsafeDataDirError
from mrclean.paths import check_data_dir_safe, resolve_data_dir


def test_refuses_data_dir_inside_git_repo(tmp_path):
    (tmp_path / "repo" / ".git").mkdir(parents=True)
    with pytest.raises(UnsafeDataDirError, match="git work tree"):
        check_data_dir_safe(tmp_path / "repo" / "data")


def test_refuses_not_yet_existing_dir_nested_in_repo(tmp_path):
    (tmp_path / "repo" / ".git").mkdir(parents=True)
    with pytest.raises(UnsafeDataDirError):
        check_data_dir_safe(tmp_path / "repo" / "a" / "b" / "c")


def test_git_file_marker_counts(tmp_path):
    # worktrees and submodules use a .git *file*
    (tmp_path / "wt").mkdir()
    (tmp_path / "wt" / ".git").write_text("gitdir: elsewhere")
    with pytest.raises(UnsafeDataDirError):
        check_data_dir_safe(tmp_path / "wt" / "data")


@pytest.mark.parametrize("folder", ["OneDrive", "OneDrive - Contoso", "Dropbox", "Google Drive"])
def test_refuses_sync_folders(tmp_path, folder):
    with pytest.raises(UnsafeDataDirError, match="cloud-sync"):
        check_data_dir_safe(tmp_path / folder / "mrclean")


def test_sync_folder_override(tmp_path):
    assert check_data_dir_safe(tmp_path / "Dropbox" / "x", allow_synced=True)


def test_resolve_creates_private_dir(data_dir):
    path = resolve_data_dir(create=True)
    assert path == data_dir.resolve()
    assert path.is_dir()


def test_env_override_is_still_checked(tmp_path, monkeypatch):
    (tmp_path / ".git").mkdir()
    monkeypatch.setenv("MRCLEAN_DATA_DIR", str(tmp_path / "data"))
    with pytest.raises(UnsafeDataDirError):
        resolve_data_dir()


def test_real_checkout_is_refused():
    """The repo this test runs from is a real git checkout; data can't go in it."""
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[1]
    if not (repo_root / ".git").exists():
        pytest.skip("not running from a git checkout")
    with pytest.raises(UnsafeDataDirError):
        check_data_dir_safe(repo_root / "data")


def test_link_into_repo_is_refused(tmp_path):
    (tmp_path / "repo" / ".git").mkdir(parents=True)
    (tmp_path / "repo" / "data").mkdir()
    link = tmp_path / "data-link"
    try:
        link.symlink_to(tmp_path / "repo" / "data", target_is_directory=True)
    except OSError:
        pytest.skip("symlinks not permitted here")
    with pytest.raises(UnsafeDataDirError, match="git work tree"):
        check_data_dir_safe(link)


def test_refuses_msix_redirected_appdata(tmp_path):
    redirected = (
        tmp_path
        / "AppData"
        / "Local"
        / "Packages"
        / "Claude_pzs8sxrjxfjjc"
        / "LocalCache"
        / "Local"
        / "mrclean"
    )
    with pytest.raises(UnsafeDataDirError, match="packaged-app container"):
        check_data_dir_safe(redirected)


def test_ordinary_packages_folder_is_fine(tmp_path):
    assert check_data_dir_safe(tmp_path / "Packages" / "mrclean")


def test_windows_default_avoids_appdata(monkeypatch):
    import mrclean.paths as paths

    monkeypatch.setattr(paths.sys, "platform", "win32")
    assert "AppData" not in str(paths.default_data_dir())
