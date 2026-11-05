"""Where the editing folder defaults to, and that saved paths come back absolute."""
from pathlib import Path

from mce import config


def test_unset_and_old_default_use_the_real_desktop(monkeypatch, tmp_path):
    desk = tmp_path / "OneDrive" / "Desktop"
    monkeypatch.setattr(config, "desktop_dir", lambda: desk)
    assert config.editing_root(None) == desk / "editing"
    assert config.editing_root("~/Desktop/editing") == desk / "editing"
    assert config.editing_root("~\\Desktop\\editing") == desk / "editing"


def test_chosen_folder_is_kept_and_absolute(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    chosen = tmp_path / "עריכה שלי" / "projects"
    assert config.editing_root(str(chosen)) == chosen
    assert config.editing_root("rel/dir") == tmp_path / "rel" / "dir"
    assert config.editing_root("rel/dir").is_absolute()


def test_desktop_dir_exists_here():
    # on Windows this asks the shell (OneDrive-redirected desktops included); elsewhere ~/Desktop
    d = config.desktop_dir()
    assert isinstance(d, Path) and d.is_absolute()
