"""Tests for the Benchling client wrapper."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from benchling_agent.clients.benchling import BenchlingClient, EntryResult, _entry_to_result
from benchling_agent.config import Settings


def _make_settings(**overrides) -> Settings:
    defaults = {
        "_env_file": None,
        "anthropic_api_key": "",
        "benchling_api_url": "https://test.benchling.com",
        "benchling_api_key": "sk_test",
    }
    defaults.update(overrides)
    return Settings(**defaults)


def _mock_entry(
    id: str = "etr_abc123",
    name: str = "Test Entry",
    folder_id: str = "lib_folder1",
    web_url: str = "https://test.benchling.com/entry/etr_abc123",
    created_at: str | None = "2026-01-01T00:00:00Z",
):
    entry = MagicMock()
    entry.id = id
    entry.name = name
    entry.folder_id = folder_id
    entry.web_url = web_url
    entry.created_at = created_at
    return entry


class TestEntryResult:
    def test_fields(self):
        result = EntryResult(
            id="etr_1", name="E1", folder_id="f1", web_url="http://x", created_at="2026-01-01"
        )
        assert result.id == "etr_1"
        assert result.name == "E1"

    def test_entry_to_result(self):
        mock = _mock_entry()
        result = _entry_to_result(mock)
        assert result.id == "etr_abc123"
        assert result.name == "Test Entry"
        assert result.web_url == "https://test.benchling.com/entry/etr_abc123"


class TestBenchlingClient:
    @patch("benchling_agent.clients.benchling.Benchling")
    def test_create_entry(self, mock_benchling_cls):
        mock_sdk = MagicMock()
        mock_benchling_cls.return_value = mock_sdk
        mock_sdk.entries.create_entry.return_value = _mock_entry()

        client = BenchlingClient(settings=_make_settings())
        result = client.create_entry(name="PCR Results", folder_id="lib_f1")

        mock_sdk.entries.create_entry.assert_called_once()
        payload = mock_sdk.entries.create_entry.call_args.args[0]
        assert payload.name == "PCR Results"
        assert payload.folder_id == "lib_f1"
        assert result.id == "etr_abc123"

    @patch("benchling_agent.clients.benchling.Benchling")
    def test_create_entry_with_template(self, mock_benchling_cls):
        mock_sdk = MagicMock()
        mock_benchling_cls.return_value = mock_sdk
        mock_sdk.entries.create_entry.return_value = _mock_entry()

        client = BenchlingClient(settings=_make_settings())
        client.create_entry(
            name="From Template",
            folder_id="lib_f1",
            entry_template_id="tmpl_abc",
        )

        payload = mock_sdk.entries.create_entry.call_args.args[0]
        assert payload.entry_template_id == "tmpl_abc"

    @patch("benchling_agent.clients.benchling.Benchling")
    def test_update_entry(self, mock_benchling_cls):
        mock_sdk = MagicMock()
        mock_benchling_cls.return_value = mock_sdk
        mock_sdk.entries.update_entry.return_value = _mock_entry(name="Updated")

        client = BenchlingClient(settings=_make_settings())
        result = client.update_entry("etr_abc123", name="Updated")

        mock_sdk.entries.update_entry.assert_called_once()
        assert result.name == "Updated"

    @patch("benchling_agent.clients.benchling.Benchling")
    def test_get_entry(self, mock_benchling_cls):
        mock_sdk = MagicMock()
        mock_benchling_cls.return_value = mock_sdk
        mock_sdk.entries.get_entry_by_id.return_value = _mock_entry()

        client = BenchlingClient(settings=_make_settings())
        result = client.get_entry("etr_abc123")

        mock_sdk.entries.get_entry_by_id.assert_called_once_with("etr_abc123")
        assert result.id == "etr_abc123"

    @patch("benchling_agent.clients.benchling.Benchling")
    def test_list_entries(self, mock_benchling_cls):
        mock_sdk = MagicMock()
        mock_benchling_cls.return_value = mock_sdk
        page = [_mock_entry(id="etr_1"), _mock_entry(id="etr_2")]
        mock_sdk.entries.list_entries.return_value = iter([page])

        client = BenchlingClient(settings=_make_settings())
        results = client.list_entries(max_results=5)

        assert len(results) == 2
        assert results[0].id == "etr_1"
        assert results[1].id == "etr_2"

    @patch("benchling_agent.clients.benchling.Benchling")
    def test_list_entries_respects_max(self, mock_benchling_cls):
        mock_sdk = MagicMock()
        mock_benchling_cls.return_value = mock_sdk
        page = [_mock_entry(id=f"etr_{i}") for i in range(10)]
        mock_sdk.entries.list_entries.return_value = iter([page])

        client = BenchlingClient(settings=_make_settings())
        results = client.list_entries(max_results=3)

        assert len(results) == 3

    @patch("benchling_agent.clients.benchling.Benchling")
    def test_list_entries_multiple_pages(self, mock_benchling_cls):
        mock_sdk = MagicMock()
        mock_benchling_cls.return_value = mock_sdk
        page1 = [_mock_entry(id="etr_1"), _mock_entry(id="etr_2")]
        page2 = [_mock_entry(id="etr_3")]
        mock_sdk.entries.list_entries.return_value = iter([page1, page2])

        client = BenchlingClient(settings=_make_settings())
        results = client.list_entries(max_results=10)

        assert len(results) == 3
        assert [r.id for r in results] == ["etr_1", "etr_2", "etr_3"]

    @patch("benchling_agent.clients.benchling.Benchling")
    def test_list_folders(self, mock_benchling_cls):
        mock_sdk = MagicMock()
        mock_benchling_cls.return_value = mock_sdk

        folder1 = MagicMock()
        folder1.id = "lib_f1"
        folder1.name = "My Project"
        mock_sdk.folders.list.return_value = iter([[folder1]])

        client = BenchlingClient(settings=_make_settings())
        results = client.list_folders(name_includes="My")

        assert len(results) == 1
        assert results[0]["id"] == "lib_f1"
        assert results[0]["name"] == "My Project"
        mock_sdk.folders.list.assert_called_once_with(name_includes="My")
