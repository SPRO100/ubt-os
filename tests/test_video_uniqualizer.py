"""Unit-тесты для video_uniqualizer: лёгкая уникализация на аккаунты проекта."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import ubt_os.pipelines.video_uniqualizer as vu


def _ready_video(**overrides):
    base = {
        "id": "vid-1", "status": "ready", "storage_url": "https://media/vid-1.mp4",
        "account_id": "acc_src", "duration_sec": 12, "parent_video_id": None,
    }
    base.update(overrides)
    return base


# ── чистые функции ──────────────────────────────────────────

def test_jitter_params_within_bounds():
    for _ in range(50):
        p = vu.jitter_params()
        assert vu.SPEED_RANGE[0] <= p["speed"] <= vu.SPEED_RANGE[1]
        assert vu.ZOOM_RANGE[0] <= p["zoom"] <= vu.ZOOM_RANGE[1]
        assert vu.BRIGHTNESS_RANGE[0] <= p["brightness"] <= vu.BRIGHTNESS_RANGE[1]
        assert vu.CONTRAST_RANGE[0] <= p["contrast"] <= vu.CONTRAST_RANGE[1]
        assert isinstance(p["flip"], bool)


def test_build_filters_contains_expected_pieces():
    vf, af = vu.build_filters({"zoom": 1.02, "flip": True, "brightness": 0.01,
                                "contrast": 1.0, "speed": 1.02})
    assert "scale=iw*1.02:ih*1.02" in vf
    assert "crop=iw/1.02:ih/1.02" in vf
    assert "hflip" in vf
    assert "eq=brightness=0.01:contrast=1.0" in vf
    assert af.startswith("atempo=")


def test_build_filters_no_flip_omits_hflip():
    vf, _ = vu.build_filters({"zoom": 1.0, "flip": False, "brightness": 0,
                               "contrast": 1, "speed": 1.0})
    assert "hflip" not in vf


# ── guard-условия uniqualize_video ──────────────────────────

@pytest.mark.asyncio
async def test_no_ffmpeg_returns_error():
    with patch.object(vu.shutil, "which", return_value=None):
        result = await vu.uniqualize_video("vid-1")
    assert "ffmpeg" in result["error"]


@pytest.mark.asyncio
async def test_video_not_found_returns_error():
    with patch.object(vu.shutil, "which", return_value="/usr/bin/ffmpeg"), \
         patch.object(vu.VideoReader, "get_by_id", return_value=None):
        result = await vu.uniqualize_video("missing")
    assert "не найдено" in result["error"]


@pytest.mark.asyncio
async def test_video_not_ready_returns_error():
    with patch.object(vu.shutil, "which", return_value="/usr/bin/ffmpeg"), \
         patch.object(vu.VideoReader, "get_by_id", return_value=_ready_video(status="generating")):
        result = await vu.uniqualize_video("vid-1")
    assert "не готово" in result["error"]


@pytest.mark.asyncio
async def test_video_without_account_returns_error():
    with patch.object(vu.shutil, "which", return_value="/usr/bin/ffmpeg"), \
         patch.object(vu.VideoReader, "get_by_id", return_value=_ready_video(account_id=None)):
        result = await vu.uniqualize_video("vid-1")
    assert "аккаунт" in result["error"]


@pytest.mark.asyncio
async def test_account_without_project_returns_error():
    with patch.object(vu.shutil, "which", return_value="/usr/bin/ffmpeg"), \
         patch.object(vu.VideoReader, "get_by_id", return_value=_ready_video()), \
         patch.object(vu.AccountReader, "get_by_id", return_value={"id": "acc_src", "project_id": None}):
        result = await vu.uniqualize_video("vid-1")
    assert "проект" in result["error"]


@pytest.mark.asyncio
async def test_no_other_accounts_in_project_returns_error():
    with patch.object(vu.shutil, "which", return_value="/usr/bin/ffmpeg"), \
         patch.object(vu.VideoReader, "get_by_id", return_value=_ready_video()), \
         patch.object(vu.AccountReader, "get_by_id", return_value={"id": "acc_src", "project_id": "proj1"}), \
         patch.object(vu, "_accounts_in_project", return_value=[]):
        result = await vu.uniqualize_video("vid-1")
    assert result["project_id"] == "proj1"
    assert "нет других" in result["error"]


# ── happy path: одна копия на каждый другой аккаунт проекта ──

@pytest.mark.asyncio
async def test_uniqualize_creates_one_variant_per_target_account():
    targets = [{"id": "acc_a"}, {"id": "acc_b"}]

    def _fake_ffmpeg_run(cmd, **kwargs):
        out_path = cmd[-1]
        with open(out_path, "wb") as f:
            f.write(b"fake-mp4")
        return MagicMock()

    inserted = []

    def _fake_insert(payload):
        inserted.append(payload)
        row_id = f"new-{payload['account_id']}"
        m = MagicMock()
        m.execute.return_value = MagicMock(data=[{"id": row_id}])
        return m

    db = MagicMock()
    db.table.return_value.insert.side_effect = _fake_insert

    with patch.object(vu.shutil, "which", return_value="/usr/bin/ffmpeg"), \
         patch.object(vu.VideoReader, "get_by_id", return_value=_ready_video()), \
         patch.object(vu.AccountReader, "get_by_id", return_value={"id": "acc_src", "project_id": "proj1"}), \
         patch.object(vu, "_accounts_in_project", return_value=targets), \
         patch.object(vu, "get_db", return_value=db), \
         patch.object(vu.subprocess, "run", side_effect=_fake_ffmpeg_run), \
         patch.object(vu, "upload_video", new=AsyncMock(side_effect=lambda content, folder, **kw: f"https://media/{folder}/x.mp4")):
        result = await vu.uniqualize_video("vid-1")

    assert result["status"] == "ok"
    assert len(result["created"]) == 2
    assert not result["errors"]
    account_ids = {c["account_id"] for c in result["created"]}
    assert account_ids == {"acc_a", "acc_b"}
    assert all(p["parent_video_id"] == "vid-1" for p in inserted)


@pytest.mark.asyncio
async def test_uniqualize_reports_per_account_errors():
    targets = [{"id": "acc_a"}, {"id": "acc_b"}]

    def _fake_ffmpeg_fail(cmd, **kwargs):
        raise RuntimeError("ffmpeg boom")

    db = MagicMock()

    with patch.object(vu.shutil, "which", return_value="/usr/bin/ffmpeg"), \
         patch.object(vu.VideoReader, "get_by_id", return_value=_ready_video()), \
         patch.object(vu.AccountReader, "get_by_id", return_value={"id": "acc_src", "project_id": "proj1"}), \
         patch.object(vu, "_accounts_in_project", return_value=targets), \
         patch.object(vu, "get_db", return_value=db), \
         patch.object(vu.subprocess, "run", side_effect=_fake_ffmpeg_fail):
        result = await vu.uniqualize_video("vid-1")

    assert result["status"] == "failed"
    assert not result["created"]
    assert len(result["errors"]) == 2
