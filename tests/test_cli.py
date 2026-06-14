from raven2mqtt.__main__ import EX_CONFIG, main


def test_main_returns_config_exit_code_on_bad_config(tmp_path) -> None:
    path = tmp_path / "bad.toml"
    path.write_text("not = = valid")
    assert main(["--config", str(path), "discovery-json"]) == EX_CONFIG


def test_main_prints_clean_error_not_traceback(tmp_path, capsys) -> None:
    path = tmp_path / "bad.toml"
    path.write_text("not = = valid")
    main(["--config", str(path), "discovery-json"])
    captured = capsys.readouterr()
    assert "error:" in captured.err.lower()
    assert "Traceback" not in captured.err
