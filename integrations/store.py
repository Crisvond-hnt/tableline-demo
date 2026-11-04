"""Request ledger for one working directory.

The file keeps request ids, threads, approvals, and notice ids. Confirmed
rows are rebuilt from the snapshot and the notice feed. Another checkout
has its own file, which is why only the coordinator runs these commands.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from integrations.config import ROOT


def store_path(root: Path | None = None) -> Path:
    override = os.environ.get("TABLELINE_STORE")
    if override:
        return Path(override)
    return (root or ROOT) / "var" / "store.json"


class Store:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.data = {
            "seen_message_ids": {},
            "notices": [],
            "review": [],
            "requests": [],
        }
        if path.is_file():
            self.data = json.loads(path.read_text())

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self.data, indent=2, sort_keys=True))
        temporary.replace(self.path)

    def request_by_id(self, request_id: str) -> dict | None:
        for item in self.data["requests"]:
            if item["id"] == request_id:
                return item
        return None

    def request_by_thread(self, channel: str, thread_id: str) -> dict | None:
        for item in self.data["requests"]:
            if item["channel"] == channel and item["thread_id"] == thread_id:
                return item
        return None

    def request_for_message(self, message_id: str) -> dict | None:
        request_id = self.data["seen_message_ids"].get(message_id)
        if not request_id:
            return None
        return self.request_by_id(request_id)
