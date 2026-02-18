"""Benchling API client wrapper.

Provides a simplified interface over the Benchling SDK for
creating and managing notebook entries.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from benchling_api_client.v2.stable.models.entry import Entry
from benchling_api_client.v2.stable.models.entry_create import EntryCreate
from benchling_api_client.v2.stable.models.entry_update import EntryUpdate
from benchling_sdk.auth.api_key_auth import ApiKeyAuth
from benchling_sdk.benchling import Benchling

from benchling_agent.config import Settings


@dataclass
class EntryResult:
    """Simplified view of a Benchling notebook entry."""

    id: str
    name: str
    folder_id: str
    web_url: str
    created_at: str | None = None


def _entry_to_result(entry: Entry) -> EntryResult:
    return EntryResult(
        id=entry.id,
        name=entry.name,
        folder_id=entry.folder_id,
        web_url=entry.web_url,
        created_at=str(entry.created_at) if entry.created_at else None,
    )


@dataclass
class BenchlingClient:
    """Wrapper around the Benchling SDK focused on notebook entries."""

    settings: Settings
    _client: Benchling = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._client = Benchling(
            url=self.settings.benchling_api_url,
            auth_method=ApiKeyAuth(self.settings.benchling_api_key),
        )

    def create_entry(
        self,
        name: str,
        folder_id: str,
        *,
        entry_template_id: str | None = None,
        schema_id: str | None = None,
    ) -> EntryResult:
        """Create a new notebook entry in the given folder."""
        payload = EntryCreate(folder_id=folder_id, name=name)
        if entry_template_id is not None:
            payload.entry_template_id = entry_template_id
        if schema_id is not None:
            payload.schema_id = schema_id

        entry = self._client.entries.create_entry(payload)
        return _entry_to_result(entry)

    def update_entry(
        self,
        entry_id: str,
        *,
        name: str | None = None,
        folder_id: str | None = None,
    ) -> EntryResult:
        """Update metadata on an existing entry."""
        payload = EntryUpdate()
        if name is not None:
            payload.name = name
        if folder_id is not None:
            payload.folder_id = folder_id

        entry = self._client.entries.update_entry(entry_id, payload)
        return _entry_to_result(entry)

    def get_entry(self, entry_id: str) -> EntryResult:
        """Retrieve an entry by its ID."""
        entry = self._client.entries.get_entry_by_id(entry_id)
        return _entry_to_result(entry)

    def list_entries(
        self,
        *,
        folder_id: str | None = None,
        name: str | None = None,
        max_results: int = 20,
    ) -> list[EntryResult]:
        """List notebook entries with optional filters."""
        kwargs: dict = {"page_size": min(max_results, 50)}
        if folder_id:
            kwargs["project_id"] = folder_id
        if name:
            kwargs["name"] = name

        results: list[EntryResult] = []
        for page in self._client.entries.list_entries(**kwargs):
            for entry in page:
                results.append(_entry_to_result(entry))
                if len(results) >= max_results:
                    return results
        return results

    def list_folders(self, *, name_includes: str | None = None) -> list[dict]:
        """List project folders, optionally filtering by name."""
        kwargs: dict = {}
        if name_includes:
            kwargs["name_includes"] = name_includes

        folders = []
        for page in self._client.folders.list(**kwargs):
            for folder in page:
                folders.append({"id": folder.id, "name": folder.name})
        return folders
