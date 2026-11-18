r"""Record the answers of a Lekto instance as the snapshot the tests replay.

    uv run python script/record_snapshot.py --url http://127.0.0.1:18000 [NAME ...]

The token comes from the environment variable ``PYLEKTO_SNAPSHOT_TOKEN``: an admin's API token
with the scope ``read_write``. Without names, every recording is made again, in their order.

Never point it at an instance with real documents: the snapshot is public. Use a throwaway Lekto
of the release ``LEKTO_VERSION`` names, filled with the synthetic documents of Lekto's
repository::

    docker network create lekto-snapshot
    docker run -d --name meili-snapshot --network lekto-snapshot \
      -e MEILI_MASTER_KEY=... -e MEILI_ENV=development getmeili/meilisearch:v1.54.3
    docker run -d --name lekto-snapshot --network lekto-snapshot -p 127.0.0.1:18000:8000 \
      -e LEKTO_SECRET_KEY=... -e LEKTO_ADMIN_USERNAME=admin -e LEKTO_ADMIN_PASSWORD=... \
      -e LEKTO_COOKIE_SECURE=false -e LEKTO_MEILISEARCH_URL=http://meili-snapshot:7700 \
      -e LEKTO_MEILISEARCH_API_KEY=... ghcr.io/lektohq/lekto:0.15.5
    # an API token: sign in at http://127.0.0.1:18000/ui, Settings, API tokens (read_write)
    python <lekto>/examples/mcp-eval/seed.py --url http://127.0.0.1:18000 --token ... \
      --documents 40
    # wait until the inbox shows nothing in processing; then read the facts of the documents
    # taken over (POST /api/v1/pipeline/read-facts) and wait again

Each recording becomes ``tests/snapshot/<name>.json``: the request (method, path, query, body)
and the answer (status, body). The address of the instance is replaced by the one the tests use.
Many recordings change the instance (they create, change or delete), so the order matters and
the instance is a throwaway one. Uploads send a small PDF the script makes itself.
"""

import argparse
import json
import os
import re
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx2

from pylekto import LEKTO_VERSION

ROOT = Path(__file__).resolve().parent.parent
SNAPSHOT = ROOT / "tests" / "snapshot"
TESTS_URL = "https://lekto.example.com"
PLACEHOLDER = re.compile(r"\{(\w+)\}")

type Lookup = Callable[["Recorder"], str]


@dataclass
class Recording:
    """One request to record; ``{name}`` in path, query or body is filled by that lookup.

    ``operation`` is the path of the operation in the OpenAPI description below ``/api/v1``.
    ``upload`` sends a one-page PDF with that text as the form field ``file``; ``settle`` waits
    until the document of that lookup is processed before the request is sent.
    """

    name: str
    method: str
    path: str
    operation: str
    params: dict[str, Any] = field(default_factory=dict)
    json: Any = None
    data: dict[str, str] = field(default_factory=dict)
    upload: str | None = None
    settle: str | None = None


class Recorder:
    """Sends the recordings to an instance and writes their answers."""

    def __init__(self, url: str, token: str) -> None:
        """Connect to the instance with the token."""
        self.url = url.rstrip("/")
        self.client = httpx2.Client(
            base_url=self.url + "/api/v1",
            headers={"Authorization": f"Bearer {token}"},
            timeout=120.0,
        )
        self.found: dict[str, str] = {}
        self.answers: dict[str, Any] = {}

    def call(self, method: str, path: str, **send: Any) -> Any:
        """Send a request for a lookup; an error stops the recording."""
        response = self.client.request(method, path, **send)
        response.raise_for_status()
        return response.json() if response.content else None

    def value(self, name: str) -> str:
        """Return the value of a placeholder, looked up once."""
        if name not in self.found:
            self.found[name] = LOOKUPS[name](self)
        return self.found[name]

    def fill(self, value: Any) -> Any:
        """Put the values of the lookups in place of the placeholders in a string, list or dict."""
        if isinstance(value, str):
            return PLACEHOLDER.sub(lambda match: self.value(match[1]), value)
        if isinstance(value, list):
            return [self.fill(item) for item in value]
        if isinstance(value, dict):
            return {key: self.fill(item) for key, item in value.items()}
        return value

    def settle(self, document_id: str) -> None:
        """Wait until Lekto has processed a document (at most five minutes)."""
        for _ in range(300):
            processing = self.call("GET", f"/documents/{document_id}")["processing"]
            if processing is None or processing["status"] != "processing":
                return
            time.sleep(1)
        message = f"document {document_id} is still in processing"
        raise SystemExit(message)

    def record(self, recording: Recording) -> int:
        """Send one recording and write its file; return the status."""
        if recording.settle is not None:
            self.settle(self.value(recording.settle))
        path = self.fill(recording.path)
        params = self.fill(recording.params)
        body = self.fill(recording.json)
        data = self.fill(recording.data)
        # Form fields go as parts of a multipart body, as Lekto reads them.
        files: list[tuple[str, Any]] = [(name, (None, text)) for name, text in data.items()]
        if recording.upload is not None:
            files.append(
                ("file", (f"{recording.name}.pdf", pdf(recording.upload), "application/pdf"))
            )
        response = self.client.request(
            recording.method, path, params=params, json=body, files=files or None
        )
        answer = response.json() if response.content else None
        self.answers[recording.name] = answer
        snapshot = {
            "lekto_version": LEKTO_VERSION,
            "method": recording.method,
            "operation": recording.operation,
            "path": path,
            "params": params,
            "json": body,
            "data": data,
            "status": response.status_code,
            "body": answer,
        }
        text = json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n"
        (SNAPSHOT / f"{recording.name}.json").write_text(
            text.replace(self.url, TESTS_URL), encoding="utf-8"
        )
        return response.status_code


def pdf(text: str) -> bytes:
    """Make a one-page PDF that shows ``text`` (Helvetica, A4)."""
    content = f"BT /F1 14 Tf 72 760 Td ({text}) Tj ET".encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>"
        ),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length %d >>\nstream\n%s\nendstream" % (len(content), content),
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, obj in enumerate(objects, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n%s\nendobj\n" % (number, obj)
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    out += b"".join(b"%010d 00000 n \n" % offset for offset in offsets)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objects) + 1,
        xref,
    )
    return bytes(out)


def _document(recorder: Recorder) -> str:
    """Look up the oldest document that shows identifiers (facts to record)."""
    page = recorder.call("GET", "/documents", params={"sort": "created_at", "limit": 40})
    for item in page["items"]:
        if recorder.call("GET", f"/documents/{item['id']}/facts")["identifiers"]:
            return str(item["id"])
    message = "no document shows identifiers"
    raise SystemExit(message)


def _other_document(recorder: Recorder) -> str:
    """Look up the oldest document but the one of ``document``."""
    page = recorder.call("GET", "/documents", params={"sort": "created_at", "limit": 2})
    ids = [str(item["id"]) for item in page["items"]]
    return ids[1] if ids[0] == recorder.value("document") else ids[0]


def _identifier(part: str) -> Lookup:
    """Look up a part (``kind`` or ``value``) of the first identifier of the first document."""

    def lookup(recorder: Recorder) -> str:
        facts = recorder.call("GET", f"/documents/{recorder.value('document')}/facts")
        kept = [item for item in facts["identifiers"] if item["rejected_at"] is None]
        return str(kept[0][part])

    return lookup


def _ref(recorder: Recorder) -> str:
    """Look up the reference to the value of the first identifier of the first document."""
    kind, value = recorder.value("kind"), recorder.value("value")
    answer = recorder.call("POST", "/identifiers/refs", json={"kind": kind, "value": value})
    return str(answer["ref"])


def _space(recorder: Recorder) -> str:
    """Look up the space to move a document to, made on the first run."""
    for space in recorder.call("GET", "/spaces"):
        if space["name"] == "Muster Archive":
            return str(space["id"])
    return str(recorder.call("POST", "/spaces", json={"name": "Muster Archive"})["id"])


def _of_document(name: str) -> Lookup:
    """Look up a value of the first document, such as its contact."""

    def lookup(recorder: Recorder) -> str:
        return str(recorder.call("GET", f"/documents/{recorder.value('document')}")[name])

    return lookup


def _answer(name: str) -> Lookup:
    """Look up the id in the answer of an earlier recording."""

    def lookup(recorder: Recorder) -> str:
        return str(recorder.answers[name]["id"])

    return lookup


LOOKUPS: dict[str, Lookup] = {
    "document": _document,
    "other_document": _other_document,
    "kind": _identifier("kind"),
    "value": _identifier("value"),
    "ref": _ref,
    "space": _space,
    "contact": _of_document("contact_id"),
    "document_type": _of_document("document_type_id"),
    "uploaded": _answer("documents_upload"),
    "bulk": _answer("documents_bulk"),
}

DOCUMENT = "/documents/{document}"
UPLOADED = "/documents/{uploaded}"

RECORDINGS: list[Recording] = [
    Recording("auth_me", "GET", "/auth/me", "/auth/me"),
    Recording("health", "GET", "/health", "/health"),
    # Documents: reading.
    Recording("documents_page", "GET", "/documents", "/documents", params={"limit": 5}),
    Recording("documents_count", "GET", "/documents/count", "/documents/count"),
    Recording("documents_facets", "GET", "/documents/facets", "/documents/facets"),
    Recording("documents_stream", "GET", "/documents/stream", "/documents/stream"),
    Recording("documents_get", "GET", DOCUMENT, "/documents/{id}"),
    Recording(
        "documents_text", "GET", DOCUMENT + "/text", "/documents/{id}/text", params={"limit": 400}
    ),
    Recording("documents_structure", "GET", DOCUMENT + "/structure", "/documents/{id}/structure"),
    Recording("documents_log", "GET", DOCUMENT + "/log", "/documents/{id}/log"),
    Recording("documents_facts", "GET", DOCUMENT + "/facts", "/documents/{id}/facts"),
    Recording(
        "documents_place",
        "GET",
        DOCUMENT + "/places/{kind}/{ref}",
        "/documents/{id}/places/{kind}/{ref}",
    ),
    Recording("documents_files", "GET", DOCUMENT + "/files", "/documents/{id}/files"),
    Recording("documents_reading", "GET", DOCUMENT + "/reading", "/documents/{id}/reading"),
    Recording("documents_review", "GET", DOCUMENT + "/review", "/documents/{id}/review"),
    Recording("documents_origin", "GET", DOCUMENT + "/origin", "/documents/{id}/origin"),
    Recording(
        "documents_exchanges",
        "GET",
        DOCUMENT + "/exchanges/fields",
        "/documents/{id}/exchanges/{node}",
    ),
    Recording(
        "documents_dry_run",
        "POST",
        DOCUMENT + "/dry-run",
        "/documents/{id}/dry-run",
        json={"title": "Stromabrechnung 2023/2024"},
    ),
    # Search.
    Recording(
        "search_page",
        "POST",
        "/documents/search",
        "/documents/search",
        params={"limit": 5},
        json={"q": "Strom"},
    ),
    Recording(
        "search_places",
        "POST",
        DOCUMENT + "/search-places",
        "/documents/{id}/search-places",
        json={"q": "Strom"},
    ),
    Recording("search_status", "GET", "/search/status", "/search/status"),
    Recording("search_check", "POST", "/search/check", "/search/check"),
    Recording("search_warm", "POST", "/documents/search/warm", "/documents/search/warm"),
    # Relations.
    Recording("relations_get", "GET", DOCUMENT + "/relations", "/documents/{id}/relations"),
    Recording(
        "relations_add",
        "POST",
        DOCUMENT + "/relations",
        "/documents/{id}/relations",
        json={"document_id": "{other_document}"},
    ),
    Recording(
        "relations_remove",
        "DELETE",
        DOCUMENT + "/relations/{other_document}",
        "/documents/{id}/relations/{other_id}",
    ),
    # Documents: changing.
    Recording(
        "documents_update",
        "PATCH",
        DOCUMENT,
        "/documents/{id}",
        json={"title": "Stromabrechnung 2023/2024"},
    ),
    Recording("documents_mark_seen", "PUT", DOCUMENT + "/seen", "/documents/{id}/seen"),
    Recording("documents_mark_new", "DELETE", DOCUMENT + "/seen", "/documents/{id}/seen"),
    Recording(
        "documents_confirm_refused",
        "POST",
        DOCUMENT + "/confirm",
        "/documents/{id}/confirm",
        json={},
    ),
    Recording("documents_retry", "POST", DOCUMENT + "/retry", "/documents/{id}/retry"),
    Recording("documents_vision", "POST", DOCUMENT + "/vision", "/documents/{id}/vision"),
    Recording(
        "documents_decide_fact",
        "POST",
        DOCUMENT + "/facts/decisions",
        "/documents/{id}/facts/decisions",
        json={"action": "reject", "kind": "{kind}", "value": "{value}"},
    ),
    Recording(
        "documents_withdraw_fact",
        "POST",
        DOCUMENT + "/facts/decisions",
        "/documents/{id}/facts/decisions",
        json={"action": "withdraw", "kind": "{kind}", "value": "{value}"},
    ),
    Recording(
        "documents_reprocess",
        "POST",
        DOCUMENT + "/reprocess",
        "/documents/{id}/reprocess",
        json={"from_node": "relate"},
    ),
    Recording(
        "documents_upload", "POST", "/documents", "/documents", upload="Muster Versicherung 12345"
    ),
    Recording(
        "documents_add_version",
        "POST",
        UPLOADED + "/versions",
        "/documents/{id}/versions",
        upload="Muster Versicherung 12345, zweite Fassung",
        settle="uploaded",
    ),
    Recording(
        "documents_edit_pages",
        "POST",
        UPLOADED + "/edit/pages",
        "/documents/{id}/edit/pages",
        upload="Muster Versicherung, Anlage",
        settle="uploaded",
    ),
    Recording(
        "documents_edit",
        "POST",
        UPLOADED + "/edit",
        "/documents/{id}/edit",
        data={"parts": json.dumps([{"pages": [{"page": 1, "rotate": 90}], "replaces": True}])},
        settle="uploaded",
    ),
    Recording(
        "documents_confirm_open_fields",
        "POST",
        UPLOADED + "/confirm",
        "/documents/{id}/confirm",
        json={"changes": {"title": "Muster Versicherung"}},
        settle="uploaded",
    ),
    Recording(
        "documents_confirm",
        "POST",
        UPLOADED + "/confirm",
        "/documents/{id}/confirm",
        json={
            "changes": {
                "title": "Muster Versicherung",
                "contact_id": "{contact}",
                "document_type_id": "{document_type}",
                "document_date": "2026-10-01",
            }
        },
    ),
    Recording(
        "documents_move",
        "POST",
        UPLOADED + "/move",
        "/documents/{id}/move",
        json={"space_id": "{space}"},
        settle="uploaded",
    ),
    Recording(
        "documents_bulk",
        "POST",
        "/documents/bulk",
        "/documents/bulk",
        json={"document_ids": ["{uploaded}"], "action": {"kind": "confirm"}},
        settle="uploaded",
    ),
    Recording("documents_bulk_progress", "GET", "/documents/bulk/{bulk}", "/documents/bulk/{id}"),
    Recording("documents_delete", "DELETE", UPLOADED, "/documents/{id}", settle="uploaded"),
    Recording("search_reindex", "POST", "/search/reindex", "/search/reindex"),
]


def main() -> None:
    """Record the named recordings, or all of them."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--url", required=True, help="the throwaway Lekto instance")
    parser.add_argument("names", nargs="*", help="the recordings to make (default: all)")
    arguments = parser.parse_args()
    token = os.environ.get("PYLEKTO_SNAPSHOT_TOKEN")
    if not token:
        message = "PYLEKTO_SNAPSHOT_TOKEN is not set"
        raise SystemExit(message)
    recorder = Recorder(arguments.url, token)
    version = recorder.call("GET", "/auth/me")["lekto_version"]
    if version != LEKTO_VERSION:
        message = f"the instance runs Lekto {version}, the snapshot is of {LEKTO_VERSION}"
        raise SystemExit(message)
    unknown = set(arguments.names) - {r.name for r in RECORDINGS}
    if unknown:
        message = f"no such recordings: {', '.join(sorted(unknown))}"
        raise SystemExit(message)
    chosen = [r for r in RECORDINGS if not arguments.names or r.name in arguments.names]
    SNAPSHOT.mkdir(parents=True, exist_ok=True)
    for recording in chosen:
        status = recorder.record(recording)
        sys.stdout.write(f"{status} {recording.name}\n")


if __name__ == "__main__":
    main()
