"""Unit-тесты для account_cleanup: каскадное удаление аккаунта."""
from types import SimpleNamespace
from unittest.mock import patch

import pytest

import ubt_os.pipelines.account_cleanup as ac


class _FakeTable:
    def __init__(self, store: dict, name: str):
        self.store = store
        self.name = name
        self._filters: list[tuple] = []
        self._mode = "select"
        self._payload: dict = {}

    def select(self, *_a, **_kw):
        self._mode = "select"
        return self

    def delete(self):
        self._mode = "delete"
        return self

    def update(self, payload):
        self._mode = "update"
        self._payload = payload
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
        if self._mode == "select":
            return SimpleNamespace(data=matched)
        if self._mode == "delete":
            self.store[self.name] = [r for r in rows_ if r not in matched]
            return SimpleNamespace(data=matched)
        if self._mode == "update":
            for r in matched:
                r.update(self._payload)
            return SimpleNamespace(data=matched)
        raise AssertionError("unreachable")


class _FakeDb:
    def __init__(self, store: dict):
        self.store = store

    def table(self, name):
        return _FakeTable(self.store, name)


def _store():
    return {
        "content_plans": [{"id": "cp1", "account_id": "acc1"}],
        "videos": [
            {"id": "v1", "account_id": "acc1", "content_plan_id": "cp1", "parent_video_id": None},
            # копия v1 на ДРУГОМ аккаунте — не должна удалиться, только отвязаться
            {"id": "v2", "account_id": "acc2", "content_plan_id": None, "parent_video_id": "v1"},
        ],
        "publications": [
            {"id": "p1", "account_id": "acc1", "video_id": "v1"},
        ],
        "direct_publish_jobs": [{"id": "j1", "account_id": "acc1"}],
        "direct_publish_accounts": [{"id": "d1", "account_id": "acc1"}],
        "accounts": [{"id": "acc1"}, {"id": "acc2"}],
    }


@pytest.mark.asyncio
async def test_dry_run_counts_without_deleting():
    store = _store()
    with patch.object(ac, "get_db", return_value=_FakeDb(store)):
        result = await ac.delete_account_cascade("acc1", dry_run=True)

    assert result["status"] == "dry_run"
    assert result["counts"] == {"content_plans": 1, "videos": 1, "publications": 1}
    assert len(store["accounts"]) == 2
    assert len(store["videos"]) == 2
    assert len(store["publications"]) == 1


@pytest.mark.asyncio
async def test_cascade_delete_removes_dependents_and_account():
    store = _store()
    with patch.object(ac, "get_db", return_value=_FakeDb(store)):
        result = await ac.delete_account_cascade("acc1", dry_run=False)

    assert result["status"] == "deleted"
    assert [a["id"] for a in store["accounts"]] == ["acc2"]
    assert [v["id"] for v in store["videos"]] == ["v2"]
    assert store["publications"] == []
    assert store["content_plans"] == []
    assert store["direct_publish_jobs"] == []
    assert store["direct_publish_accounts"] == []
    # копия на другом аккаунте выжила, но ссылка на удалённого родителя отвязана
    assert store["videos"][0]["parent_video_id"] is None


@pytest.mark.asyncio
async def test_cascade_delete_finds_videos_by_direct_account_id():
    """v2 привязан к acc2 напрямую через videos.account_id (не через content_plan) —
    уникализированная копия без своего content_plan должна найтись и удалиться."""
    store = _store()
    with patch.object(ac, "get_db", return_value=_FakeDb(store)):
        result = await ac.delete_account_cascade("acc2", dry_run=False)

    assert result["status"] == "deleted"
    assert result["counts"] == {"content_plans": 0, "videos": 1, "publications": 0}
    assert [a["id"] for a in store["accounts"]] == ["acc1"]
    assert not any(v["id"] == "v2" for v in store["videos"])
    # acc1 и его видео/контент-план не затронуты
    assert any(v["id"] == "v1" for v in store["videos"])
