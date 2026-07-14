import asyncio
import re
from typing import Any, Dict, Optional

import httpx

from app.auth.oauth import refresh_google_token
from app.config import get_settings
from app.security.encryption import decrypt_drive_token

settings = get_settings()


class FileTooLargeError(ValueError):
    """Raised when a Drive file exceeds the in-memory processing limit."""


class DriveClient:
    """Google Drive API wrapper"""

    DRIVE_API_BASE = "https://www.googleapis.com/drive/v3"
    MAX_DOWNLOAD_BYTES = 100 * 1024 * 1024

    def __init__(
        self,
        access_token: str | None = None,
        refresh_token_encrypted: Optional[bytes] = None,
        api_key: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self.access_token = access_token
        self.refresh_token_encrypted = refresh_token_encrypted
        self.api_key = api_key
        self.transport = transport

    @property
    def _auth_headers(self) -> dict[str, str]:
        if not self.access_token:
            return {}
        return {"Authorization": f"Bearer {self.access_token}"}

    def _client(self) -> httpx.AsyncClient:
        timeout = httpx.Timeout(connect=15.0, read=120.0, write=30.0, pool=30.0)
        return httpx.AsyncClient(transport=self.transport, timeout=timeout)

    async def _ensure_access(self) -> None:
        if not self.access_token and self.refresh_token_encrypted:
            self.access_token = await self.refresh_access_token(self.refresh_token_encrypted)

    async def _request_with_retry(
        self,
        client: httpx.AsyncClient,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> httpx.Response:
        refreshed = False
        extra_headers = kwargs.pop("headers", {})
        base_params = kwargs.pop("params", None)

        for attempt in range(4):
            params = dict(base_params or {})
            if self.api_key:
                params["key"] = self.api_key
            response = await client.request(
                method,
                url,
                headers={**self._auth_headers, **extra_headers},
                params=params,
                **kwargs,
            )

            if response.status_code == 401 and not refreshed and self.refresh_token_encrypted:
                self.access_token = await self.refresh_access_token(self.refresh_token_encrypted)
                refreshed = True
                continue

            if response.status_code == 429 and attempt < 3:
                await asyncio.sleep(2 ** (attempt + 1))
                continue

            return response

        return response

    async def list_files(
        self, folder_id: str, page_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """List files in Drive folder, following all pages automatically."""
        await self._ensure_access()
        if not self.access_token and not self.api_key:
            raise ValueError("Drive access requires either an OAuth access token or GOOGLE_API_KEY")

        query = f"'{folder_id}' in parents and trashed=false"
        files: list[dict[str, Any]] = []
        next_page_token = page_token
        async with self._client() as client:
            while True:
                params = {
                    "q": query,
                    "spaces": "drive",
                    "fields": "nextPageToken,files(id,name,mimeType,size,md5Checksum,thumbnailLink,modifiedTime)",
                    "pageSize": 100,
                }
                if next_page_token:
                    params["pageToken"] = next_page_token

                response = await self._request_with_retry(
                    client,
                    "GET",
                    f"{self.DRIVE_API_BASE}/files",
                    params=params,
                )
                response.raise_for_status()
                payload = response.json()
                files.extend(payload.get("files", []))
                next_page_token = payload.get("nextPageToken")
                if not next_page_token:
                    break

        return {"files": files, "total": len(files)}

    async def download_file(self, file_id: str) -> bytes:
        """Download a Drive file into memory, capped at 100MB."""
        await self._ensure_access()
        if not self.access_token and not self.api_key:
            raise ValueError("Drive download requires either an OAuth access token or GOOGLE_API_KEY")

        metadata_url = f"{self.DRIVE_API_BASE}/files/{file_id}"
        media_url = f"{self.DRIVE_API_BASE}/files/{file_id}"

        async with self._client() as client:
            metadata = await self._request_with_retry(
                client,
                "GET",
                metadata_url,
                params={"fields": "size"},
            )
            metadata.raise_for_status()
            size = int(metadata.json().get("size") or 0)
            if size > self.MAX_DOWNLOAD_BYTES:
                raise FileTooLargeError("Drive file exceeds 100MB download limit")

            async with client.stream(
                "GET",
                media_url,
                params={"alt": "media", **({"key": self.api_key} if self.api_key else {})},
                headers=self._auth_headers,
            ) as response:
                if response.status_code == 401 and self.refresh_token_encrypted:
                    self.access_token = await self.refresh_access_token(self.refresh_token_encrypted)
                    return await self.download_file(file_id)

                if response.status_code == 429:
                    for delay in (2, 4, 8):
                        await asyncio.sleep(delay)
                        retry = await self._request_with_retry(
                            client,
                            "GET",
                            media_url,
                            params={"alt": "media"},
                        )
                        if retry.status_code != 429:
                            retry.raise_for_status()
                            if len(retry.content) > self.MAX_DOWNLOAD_BYTES:
                                raise FileTooLargeError("Drive file exceeds 100MB download limit")
                            return retry.content

                response.raise_for_status()
                chunks: list[bytes] = []
                downloaded = 0
                async for chunk in response.aiter_bytes():
                    downloaded += len(chunk)
                    if downloaded > self.MAX_DOWNLOAD_BYTES:
                        raise FileTooLargeError("Drive file exceeds 100MB download limit")
                    chunks.append(chunk)

        return b"".join(chunks)

    async def get_thumbnail(self, file_id: str, thumbnail_link: str) -> bytes:
        """Download file thumbnail"""
        if not thumbnail_link:
            return b""

        async with self._client() as client:
            response = await client.get(thumbnail_link)
            response.raise_for_status()
            return response.content

    async def get_fresh_thumbnail_bytes(self, file_id: str, size: int = 640) -> bytes:
        """Fetch a thumbnail via a freshly-minted link.

        Drive thumbnailLinks stored at indexing time expire within hours, so
        anything user-facing must re-request the link from file metadata at
        access time rather than trusting a stored copy.
        """
        await self._ensure_access()
        if not self.access_token and not self.api_key:
            raise ValueError("Drive access requires either an OAuth access token or GOOGLE_API_KEY")

        async with self._client() as client:
            metadata = await self._request_with_retry(
                client,
                "GET",
                f"{self.DRIVE_API_BASE}/files/{file_id}",
                params={"fields": "thumbnailLink"},
            )
            metadata.raise_for_status()
            link = metadata.json().get("thumbnailLink")
            if not link:
                raise ValueError("Drive did not provide a thumbnail for this file")

            # Links end in a size directive like =s220; ask for a card-sized one.
            link = re.sub(r"=s\d+(-c)?$", f"=s{size}", link)
            response = await client.get(link)
            response.raise_for_status()
            return response.content

    async def refresh_access_token(self, encrypted_refresh_token: bytes) -> str:
        """Decrypt the stored refresh token and get a new Google access token."""
        refresh_token = decrypt_drive_token(
            encrypted_refresh_token,
            settings.master_encryption_key.encode("utf-8"),
        )
        token_payload = await refresh_google_token(refresh_token)
        return str(token_payload["access_token"])
