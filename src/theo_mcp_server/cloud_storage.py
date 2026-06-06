from __future__ import annotations

import base64
import json
import ssl
from typing import Protocol, runtime_checkable
from urllib import request as urlrequest
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode

from .config import Config


@runtime_checkable
class CloudStorage(Protocol):
    """Abstraction over a file cloud service.

    High-level code (e.g. the diagram tool) depends only on this interface, not
    on any concrete cloud provider — see `OwnCloudStorage` for the ownCloud impl.
    """

    def upload(
        self,
        filename: str,
        content: bytes | str,
        content_type: str = "application/octet-stream",
    ) -> str:
        """Upload `content` under `filename` and return a public download link."""
        ...

    def delete(self, filename: str) -> bool:
        """Delete a previously uploaded `filename`. Returns True if it is gone."""
        ...


class OwnCloudStorage:
    """`CloudStorage` backed by an ownCloud Infinite Scale (oCIS) instance.

    Authenticates with HTTP Basic auth using an oCIS **app token** (auth-app)
    as the password — this instance rejects Bearer on WebDAV but accepts
    `username:<plaintext-app-token>` via Basic auth. Uploads via WebDAV
    (`PUT /remote.php/dav/files/...`) and then creates a public share link
    through the OCS Share API, returning a direct download URL. Uses only the
    standard library so it adds no new dependency.
    """

    def __init__(
        self,
        base_url: str,
        username: str,
        token: str,
        *,
        remote_dir: str = "theo-diagrams",
        verify_ssl: bool = False,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._username = username
        self._token = token
        self._remote_dir = remote_dir.strip("/")
        # The endpoint is reached by IP over HTTPS and typically presents a
        # self-signed certificate, so verification is off by default.
        self._ssl_context = None if verify_ssl else ssl._create_unverified_context()

    @classmethod
    def from_config(cls, cfg: Config) -> "OwnCloudStorage":
        return cls(
            cfg.owncloud_url,
            cfg.owncloud_username,
            cfg.owncloud_token,
            remote_dir=cfg.owncloud_remote_dir,
            verify_ssl=cfg.owncloud_verify_ssl,
        )

    # --- internals -----------------------------------------------------------

    def _auth_header(self) -> str:
        creds = base64.b64encode(f"{self._username}:{self._token}".encode()).decode()
        return f"Basic {creds}"

    def _request(self, method: str, url: str, *, data: bytes | None = None,
                 headers: dict[str, str] | None = None):
        req = urlrequest.Request(url, data=data, method=method)
        req.add_header("Authorization", self._auth_header())
        for key, value in (headers or {}).items():
            req.add_header(key, value)
        return urlrequest.urlopen(req, context=self._ssl_context)

    def _dav_url(self, remote_path: str) -> str:
        return (
            f"{self._base_url}/remote.php/dav/files/"
            f"{quote(self._username)}/{quote(remote_path)}"
        )

    def _ensure_remote_dir(self) -> None:
        if not self._remote_dir:
            return
        try:
            self._request("MKCOL", self._dav_url(self._remote_dir))
        except HTTPError as e:
            # 405 Method Not Allowed => the collection already exists.
            if e.code != 405:
                raise RuntimeError(
                    f"ownCloud MKCOL failed ({e.code}): "
                    f"{e.read().decode(errors='replace')}"
                ) from e
        except URLError as e:
            raise RuntimeError(f"ownCloud MKCOL failed: {e.reason}") from e

    def _create_public_link(self, remote_path: str) -> str:
        url = f"{self._base_url}/ocs/v1.php/apps/files_sharing/api/v1/shares?format=json"
        body = urlencode(
            {"path": f"/{remote_path}", "shareType": "3", "permissions": "1"}
        ).encode()
        try:
            resp = self._request(
                "POST",
                url,
                data=body,
                headers={
                    "OCS-APIRequest": "true",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
            )
            payload = json.loads(resp.read().decode())
        except HTTPError as e:
            raise RuntimeError(
                f"ownCloud share creation failed ({e.code}): "
                f"{e.read().decode(errors='replace')}"
            ) from e
        except URLError as e:
            raise RuntimeError(f"ownCloud share creation failed: {e.reason}") from e

        share_url = payload.get("ocs", {}).get("data", {}).get("url")
        if not share_url:
            raise RuntimeError(f"ownCloud share response missing url: {payload}")
        return share_url

    # --- CloudStorage interface ----------------------------------------------

    def upload(
        self,
        filename: str,
        content: bytes | str,
        content_type: str = "application/octet-stream",
    ) -> str:
        if isinstance(content, str):
            content = content.encode("utf-8")

        self._ensure_remote_dir()
        remote_path = f"{self._remote_dir}/{filename}" if self._remote_dir else filename
        try:
            self._request(
                "PUT",
                self._dav_url(remote_path),
                data=content,
                headers={"Content-Type": content_type},
            )
        except HTTPError as e:
            raise RuntimeError(
                f"ownCloud upload failed ({e.code}): "
                f"{e.read().decode(errors='replace')}"
            ) from e
        except URLError as e:
            raise RuntimeError(f"ownCloud upload failed: {e.reason}") from e

        return self._create_public_link(remote_path)

    def delete(self, filename: str) -> bool:
        remote_path = f"{self._remote_dir}/{filename}" if self._remote_dir else filename
        try:
            self._request("DELETE", self._dav_url(remote_path))
        except HTTPError as e:
            # 404 Not Found => already gone; treat as success.
            if e.code == 404:
                return True
            raise RuntimeError(
                f"ownCloud delete failed ({e.code}): "
                f"{e.read().decode(errors='replace')}"
            ) from e
        except URLError as e:
            raise RuntimeError(f"ownCloud delete failed: {e.reason}") from e
        return True
