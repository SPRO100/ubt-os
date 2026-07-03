"""Unit-тесты для media_storage: загрузка видео в Supabase Storage по папкам."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ubt_os.core.media_storage import upload_video


def _mock_async_client(post_return=None):
    client = AsyncMock()
    client.post.return_value = post_return or MagicMock(raise_for_status=MagicMock())
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=client)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm, client


@pytest.mark.asyncio
async def test_upload_video_bytes_builds_folder_path(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "secret")
    cm, client = _mock_async_client()

    with patch("ubt_os.core.media_storage.httpx.AsyncClient", return_value=cm):
        url = await upload_video(b"fake-bytes", folder="projects/p1/acc1", filename="clip.mp4")

    assert url == "https://example.supabase.co/storage/v1/object/public/media/projects/p1/acc1/clip.mp4"
    called_url = client.post.call_args.args[0]
    assert called_url == "https://example.supabase.co/storage/v1/object/media/projects/p1/acc1/clip.mp4"
    assert client.post.call_args.kwargs["content"] == b"fake-bytes"


@pytest.mark.asyncio
async def test_upload_video_strips_slashes_and_defaults_filename(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "secret")
    cm, client = _mock_async_client()

    with patch("ubt_os.core.media_storage.httpx.AsyncClient", return_value=cm):
        url = await upload_video(b"x", folder="/projects/p1/acc1/")

    assert url.startswith("https://example.supabase.co/storage/v1/object/public/media/projects/p1/acc1/")
    assert url.endswith(".mp4")


@pytest.mark.asyncio
async def test_upload_video_from_url_downloads_first(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "secret")
    cm, client = _mock_async_client()
    client.get.return_value = MagicMock(content=b"downloaded", raise_for_status=MagicMock())

    with patch("ubt_os.core.media_storage.httpx.AsyncClient", return_value=cm):
        await upload_video("https://cdn.example.com/temp.mp4", folder="projects/p1/acc1")

    client.get.assert_called_once()
    assert client.post.call_args.kwargs["content"] == b"downloaded"
