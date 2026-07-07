import asyncio
import os
import sys

import httpx
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../backend"))

from app.drive.client import DriveClient, FileTooLargeError


class QueueTransport(httpx.AsyncBaseTransport):
    def __init__(self, responses: list[httpx.Response]):
        self.responses = responses
        self.requests: list[httpx.Request] = []

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if not self.responses:
            raise AssertionError(f"Unexpected request: {request.url}")
        response = self.responses.pop(0)
        return httpx.Response(
            status_code=response.status_code,
            headers=response.headers,
            content=response.content,
            request=request,
        )


@pytest.mark.asyncio
async def test_list_files_follows_pagination() -> None:
    transport = QueueTransport(
        [
            httpx.Response(
                200,
                json={
                    "nextPageToken": "page-2",
                    "files": [{"id": "file-1", "name": "one.jpg"}],
                },
            ),
            httpx.Response(200, json={"files": [{"id": "file-2", "name": "two.jpg"}]}),
        ]
    )

    client = DriveClient(access_token="access-token", transport=transport)
    payload = await client.list_files("folder-id")

    assert len(transport.requests) == 2
    assert transport.requests[1].url.params["pageToken"] == "page-2"
    assert payload["total"] == 2
    assert [file["id"] for file in payload["files"]] == ["file-1", "file-2"]


@pytest.mark.asyncio
async def test_download_file_rejects_files_over_100mb() -> None:
    transport = QueueTransport(
        [httpx.Response(200, json={"size": str(101 * 1024 * 1024)})]
    )
    client = DriveClient(access_token="access-token", transport=transport)

    with pytest.raises(FileTooLargeError):
        await client.download_file("too-large")


@pytest.mark.asyncio
async def test_download_file_streams_content() -> None:
    transport = QueueTransport(
        [
            httpx.Response(200, json={"size": "11"}),
            httpx.Response(200, content=b"hello world"),
        ]
    )
    client = DriveClient(access_token="access-token", transport=transport)

    assert await client.download_file("file-1") == b"hello world"
    assert transport.requests[1].url.params["alt"] == "media"


@pytest.mark.asyncio
async def test_429_retries_with_backoff(monkeypatch: pytest.MonkeyPatch) -> None:
    async def no_sleep(_: int) -> None:
        return None

    monkeypatch.setattr(asyncio, "sleep", no_sleep)
    transport = QueueTransport(
        [
            httpx.Response(429),
            httpx.Response(429),
            httpx.Response(200, json={"files": [{"id": "file-1"}]}),
        ]
    )

    client = DriveClient(access_token="access-token", transport=transport)
    payload = await client.list_files("folder-id")

    assert len(transport.requests) == 3
    assert payload["total"] == 1


@pytest.mark.asyncio
async def test_401_refreshes_token_once(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_refresh(_: DriveClient, __: bytes) -> str:
        return "new-token"

    monkeypatch.setattr(DriveClient, "refresh_access_token", fake_refresh)
    transport = QueueTransport(
        [
            httpx.Response(401),
            httpx.Response(200, json={"files": [{"id": "file-1"}]}),
        ]
    )

    client = DriveClient(
        access_token="expired-token",
        refresh_token_encrypted=b"encrypted-refresh-token",
        transport=transport,
    )
    payload = await client.list_files("folder-id")

    assert len(transport.requests) == 2
    assert transport.requests[1].headers["authorization"] == "Bearer new-token"
    assert client.access_token == "new-token"
    assert payload["files"][0]["id"] == "file-1"
