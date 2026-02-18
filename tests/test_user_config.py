"""Tests for persistent user configuration."""

from __future__ import annotations

from benchling_agent.user_config import UserConfig


class TestUserConfig:
    def test_defaults(self):
        config = UserConfig()
        assert config.default_folder_id is None
        assert config.default_folder_name is None

    def test_save_and_load(self, tmp_path):
        path = tmp_path / "config.json"
        config = UserConfig(default_folder_id="lib_abc", default_folder_name="My Folder")
        config.save(path=path)

        loaded = UserConfig.load(path=path)
        assert loaded.default_folder_id == "lib_abc"
        assert loaded.default_folder_name == "My Folder"

    def test_load_missing_file(self, tmp_path):
        path = tmp_path / "nonexistent.json"
        config = UserConfig.load(path=path)
        assert config.default_folder_id is None

    def test_load_corrupt_file(self, tmp_path):
        path = tmp_path / "config.json"
        path.write_text("not json!!!")
        config = UserConfig.load(path=path)
        assert config.default_folder_id is None

    def test_save_creates_parent_dirs(self, tmp_path):
        path = tmp_path / "nested" / "dir" / "config.json"
        config = UserConfig(default_folder_id="lib_x")
        config.save(path=path)
        assert path.exists()

    def test_overwrite_existing(self, tmp_path):
        path = tmp_path / "config.json"
        UserConfig(default_folder_id="lib_old").save(path=path)
        UserConfig(default_folder_id="lib_new").save(path=path)

        loaded = UserConfig.load(path=path)
        assert loaded.default_folder_id == "lib_new"
