import pytest

from raven2mqtt.config import AppConfig, ConfigError, load_config


def test_missing_file_uses_defaults(tmp_path) -> None:
    # A missing config is intentionally allowed: fall back to defaults.
    config = load_config(tmp_path / "does-not-exist.toml")
    assert isinstance(config, AppConfig)
    assert config.mqtt.host == "localhost"


def test_malformed_toml_raises_config_error(tmp_path) -> None:
    path = tmp_path / "bad.toml"
    path.write_text("this is = = not valid toml")
    with pytest.raises(ConfigError):
        load_config(path)


def test_unknown_key_raises_config_error(tmp_path) -> None:
    path = tmp_path / "unknown.toml"
    path.write_text("[mqtt]\nbogus_key = 1\n")
    with pytest.raises(ConfigError):
        load_config(path)


def test_non_table_section_raises_config_error(tmp_path) -> None:
    path = tmp_path / "section.toml"
    path.write_text("mqtt = 5\n")
    with pytest.raises(ConfigError):
        load_config(path)


def test_unreadable_file_raises_config_error(tmp_path, monkeypatch) -> None:
    path = tmp_path / "perms.toml"
    path.write_text("[mqtt]\n")

    def boom(*_a, **_k):
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr("pathlib.Path.read_text", boom)
    with pytest.raises(ConfigError):
        load_config(path)
