"""Unit-тесты для video_uniqualizer: лёгкая уникализация на аккаунты проекта."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import ubt_os.pipelines.video_uniqualizer as vu


class _FakeTable:
    """Минимальный in-memory фейк postgrest-таблицы для теста каскадного удаления —
    нужен, т.к. запросы к videos и publications оба используют .delete().in_(...)
    и общий MagicMock не смог бы их различить."""

    def __init__(self, store: dict, name: str):
        self.store = store
        self.name = name
        self._filters: list[tuple] = []
        self._mode = "select"

    def select(self, *_a, **_kw):
        self._mode = "select"
        return self

    def delete(self):
        self._mode = "delete"
        return self

    def eq(self, col, val):
        self._filters.append(("eq", col, val))
        return self

    def in_(self, col, vals):
        self._filters.append(("in", col, list(vals)))
        return self

    def _matches(self, row):
        for kind, col, val in self._filters:
            if kind == "eq" and row.get(col) != val:
                return False
            if kind == "in" and row.get(col) not in val:
                return False
        return True

    def execute(self):
        rows_ = self.store.setdefault(self.name, [])
        matched = [r for r in rows_ if self._matches(r)]
        if self._mode == "delete":
            self.store[self.name] = [r for r in rows_ if r not in matched]
        return SimpleNamespace(data=matched)


class _FakeDb:
    def __init__(self, store: dict):
        self.store = store

    def table(self, name):
        return _FakeTable(self.store, name)


def _ready_video(**overrides):
    base = {
        "id": "vid-1", "status": "ready", "storage_url": "https://media/vid-1.mp4",
        "account_id": "acc_src", "duration_sec": 12, "parent_video_id": None,
    }
    base.update(overrides)
    return base


def test_accounts_with_live_copy_returns_account_ids_of_ready_copies():
    db = MagicMock()
    db.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = \
        MagicMock(data=[{"account_id": "acc_a"}, {"account_id": "acc_b"}])
    with patch.object(vu, "get_db", return_value=db):
        result = vu._accounts_with_live_copy("vid-1")
    assert result == {"acc_a", "acc_b"}


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
    assert not result["skipped"]
    account_ids = {c["account_id"] for c in result["created"]}
    assert account_ids == {"acc_a", "acc_b"}
    assert all(p["parent_video_id"] == "vid-1" for p in inserted)
    assert all(p.get("expires_at") for p in inserted)
    assert all("/copies" in c["storage_url"] for c in result["created"])


@pytest.mark.asyncio
async def test_uniqualize_skips_accounts_with_live_copy():
    targets = [{"id": "acc_a"}, {"id": "acc_b"}]

    def _fake_ffmpeg_run(cmd, **kwargs):
        out_path = cmd[-1]
        with open(out_path, "wb") as f:
            f.write(b"fake-mp4")
        return MagicMock()

    inserted = []

    def _fake_insert(payload):
        inserted.append(payload)
        m = MagicMock()
        m.execute.return_value = MagicMock(data=[{"id": f"new-{payload['account_id']}"}])
        return m

    db = MagicMock()
    db.table.return_value.insert.side_effect = _fake_insert

    with patch.object(vu.shutil, "which", return_value="/usr/bin/ffmpeg"), \
         patch.object(vu.VideoReader, "get_by_id", return_value=_ready_video()), \
         patch.object(vu.AccountReader, "get_by_id", return_value={"id": "acc_src", "project_id": "proj1"}), \
         patch.object(vu, "_accounts_in_project", return_value=targets), \
         patch.object(vu, "_accounts_with_live_copy", return_value={"acc_a"}), \
         patch.object(vu, "get_db", return_value=db), \
         patch.object(vu.subprocess, "run", side_effect=_fake_ffmpeg_run), \
         patch.object(vu, "upload_video", new=AsyncMock(side_effect=lambda content, folder, **kw: f"https://media/{folder}/x.mp4")):
        result = await vu.uniqualize_video("vid-1")

    assert result["skipped"] == ["acc_a"]
    assert [c["account_id"] for c in result["created"]] == ["acc_b"]
    assert len(inserted) == 1


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


# ── cleanup_expired_copies ───────────────────────────────────

def _db_with_expired(expired_rows):
    db = MagicMock()
    (db.table.return_value.select.return_value.eq.return_value
     .lt.return_value.limit.return_value.execute.return_value) = MagicMock(data=expired_rows)
    return db


@pytest.mark.asyncio
async def test_cleanup_expired_copies_deletes_file_and_marks_expired():
    db = _db_with_expired([
        {"id": "v1", "storage_url": "https://media/v1.mp4"},
        {"id": "v2", "storage_url": "https://media/v2.mp4"},
    ])
    updates = []
    db.table.return_value.update.side_effect = lambda payload: (
        updates.append(payload) or MagicMock(eq=MagicMock(return_value=MagicMock(execute=MagicMock())))
    )

    with patch.object(vu, "get_db", return_value=db), \
         patch.object(vu, "delete_video", new=AsyncMock(return_value=True)):
        result = await vu.cleanup_expired_copies()

    assert result == {"status": "ok", "checked": 2, "cleaned": 2, "failed": 0}
    assert all(u == {"status": "expired", "storage_url": None} for u in updates)


@pytest.mark.asyncio
async def test_cleanup_expired_copies_counts_failed_deletes_without_marking_expired():
    db = _db_with_expired([{"id": "v1", "storage_url": "https://media/v1.mp4"}])
    updates = []
    db.table.return_value.update.side_effect = lambda payload: (
        updates.append(payload) or MagicMock(eq=MagicMock(return_value=MagicMock(execute=MagicMock())))
    )

    with patch.object(vu, "get_db", return_value=db), \
         patch.object(vu, "delete_video", new=AsyncMock(return_value=False)):
        result = await vu.cleanup_expired_copies()

    assert result == {"status": "ok", "checked": 1, "cleaned": 0, "failed": 1}
    assert not updates


@pytest.mark.asyncio
async def test_cleanup_expired_copies_noop_when_nothing_expired():
    db = _db_with_expired([])
    with patch.object(vu, "get_db", return_value=db):
        result = await vu.cleanup_expired_copies()
    assert result == {"status": "ok", "checked": 0, "cleaned": 0, "failed": 0}


# ── delete_video_cascade ──────────────────────────────────────

def _lifecycle_store():
    return {
        "videos": [
            {"id": "orig-1", "storage_url": "https://media/orig-1.mp4", "parent_video_id": None},
            {"id": "copy-a", "storage_url": "https://media/copy-a.mp4", "parent_video_id": "orig-1"},
            {"id": "copy-b", "storage_url": "https://media/copy-b.mp4", "parent_video_id": "orig-1"},
            {"id": "other", "storage_url": "https://media/other.mp4", "parent_video_id": None},
        ],
        "publications": [
            {"id": "p1", "video_id": "orig-1"},
            {"id": "p2", "video_id": "copy-a"},
            {"id": "p3", "video_id": "other"},
        ],
    }


@pytest.mark.asyncio
async def test_delete_video_cascade_not_found():
    with patch.object(vu.VideoReader, "get_by_id", return_value=None):
        result = await vu.delete_video_cascade("missing")
    assert "не найдено" in result["error"]


@pytest.mark.asyncio
async def test_delete_video_cascade_dry_run_only_counts():
    store = _lifecycle_store()
    with patch.object(vu.VideoReader, "get_by_id", return_value=store["videos"][0]), \
         patch.object(vu, "get_db", return_value=_FakeDb(store)):
        result = await vu.delete_video_cascade("orig-1", dry_run=True)

    assert result == {"status": "dry_run", "video_id": "orig-1",
                       "counts": {"copies": 2, "publications": 2}}
    # ничего не удалено
    assert len(store["videos"]) == 4
    assert len(store["publications"]) == 3


@pytest.mark.asyncio
async def test_delete_video_cascade_deletes_branch_and_publications():
    store = _lifecycle_store()
    deleted_urls = []

    async def _fake_delete_video(url):
        deleted_urls.append(url)
        return True

    with patch.object(vu.VideoReader, "get_by_id", return_value=store["videos"][0]), \
         patch.object(vu, "get_db", return_value=_FakeDb(store)), \
         patch.object(vu, "delete_video", new=_fake_delete_video):
        result = await vu.delete_video_cascade("orig-1", dry_run=False)

    assert result["status"] == "deleted"
    assert result["counts"] == {"copies": 2, "publications": 2}
    remaining_ids = {v["id"] for v in store["videos"]}
    assert remaining_ids == {"other"}
    remaining_pub_ids = {p["id"] for p in store["publications"]}
    assert remaining_pub_ids == {"p3"}
    assert set(deleted_urls) == {
        "https://media/orig-1.mp4", "https://media/copy-a.mp4", "https://media/copy-b.mp4",
    }
