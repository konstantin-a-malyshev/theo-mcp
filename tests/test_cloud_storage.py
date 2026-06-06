import datetime
import uuid

import pytest

from theo_mcp_server.cloud_storage import OwnCloudStorage
from theo_mcp_server.config import get_config


@pytest.fixture
def cloud_storage():
    return OwnCloudStorage.from_config(get_config())


def _unique_name() -> str:
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"test_cloud_storage_{stamp}_{uuid.uuid4().hex}.svg"


_SVG = '<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg"><text>hello</text></svg>'


@pytest.mark.anyio
async def test_upload_returns_download_link(cloud_storage):
    filename = _unique_name()
    try:
        download_url = cloud_storage.upload(filename, _SVG, content_type="image/svg+xml")
        assert isinstance(download_url, str)
        assert download_url.startswith("http")
    finally:
        cloud_storage.delete(filename)


@pytest.mark.anyio
async def test_update_overwrites_existing_file(cloud_storage):
    filename = _unique_name()
    try:
        first = cloud_storage.upload(filename, _SVG, content_type="image/svg+xml")
        assert first.startswith("http")

        # Re-uploading the same filename overwrites it (WebDAV PUT) and still
        # yields a usable download link.
        updated = '<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg"><text>updated</text></svg>'
        second = cloud_storage.upload(filename, updated, content_type="image/svg+xml")
        assert second.startswith("http")
    finally:
        cloud_storage.delete(filename)


@pytest.mark.anyio
async def test_delete_removes_file_and_is_idempotent(cloud_storage):
    filename = _unique_name()
    cloud_storage.upload(filename, _SVG, content_type="image/svg+xml")

    # First delete removes the file.
    assert cloud_storage.delete(filename) is True
    # Deleting an already-gone file (404) is treated as success.
    assert cloud_storage.delete(filename) is True
