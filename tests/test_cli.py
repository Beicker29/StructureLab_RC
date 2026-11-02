import pytest

from structurelab_rc import __version__
from structurelab_rc.cli import main


def test_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["--version"])
    assert exit_info.value.code == 0
    assert capsys.readouterr().out.strip() == f"structurelab-rc {__version__}"


def test_catalog_lists_the_bars(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["catalog"]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 12
    assert lines[1].split() == ["#3", "9.5", "71", "0.560"]
    assert lines[-1].split() == ["#18", "57.3", "2581", "20.240"]


def test_requires_a_command() -> None:
    with pytest.raises(SystemExit) as exit_info:
        main([])
    assert exit_info.value.code == 2
