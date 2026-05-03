"""Tests for storage/sqlite_store.py — SQLiteStore CRUD and table creation.

Satisfies CLAUDE.md requirement:
  "Integration tests use in-memory SQLite (':memory:')"
  "No shared mutable state between tests"

Blueprint reference: Section 7.1 (SQLite schema) — 8 tables, one store class.
"""

from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlmodel import Session, select

from cognitive_bridge.storage.sqlite_store import (
    AssertionRow, ConflictRow, DecisionRow, EventRow, KernelRow,
    ParametersRow, ProjectRow, SQLiteStore, VariantSetRow,
)

_TS = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)


class TestTableCreation:
    def _store(self) -> SQLiteStore:
        return SQLiteStore(":memory:")

    def test_assertions_table_queryable(self) -> None:
        with self._store().get_session() as session:
            assert session.exec(select(AssertionRow)).all() == []

    def test_conflicts_table_queryable(self) -> None:
        with self._store().get_session() as session:
            assert session.exec(select(ConflictRow)).all() == []

    def test_decisions_table_queryable(self) -> None:
        with self._store().get_session() as session:
            assert session.exec(select(DecisionRow)).all() == []

    def test_events_table_queryable(self) -> None:
        with self._store().get_session() as session:
            assert session.exec(select(EventRow)).all() == []

    def test_kernels_table_queryable(self) -> None:
        with self._store().get_session() as session:
            assert session.exec(select(KernelRow)).all() == []

    def test_parameters_table_queryable(self) -> None:
        with self._store().get_session() as session:
            assert session.exec(select(ParametersRow)).all() == []

    def test_variant_sets_table_queryable(self) -> None:
        with self._store().get_session() as session:
            assert session.exec(select(VariantSetRow)).all() == []

    def test_projects_table_queryable(self) -> None:
        with self._store().get_session() as session:
            assert session.exec(select(ProjectRow)).all() == []

    def test_all_eight_tables_accessible_without_error(self) -> None:
        with self._store().get_session() as session:
            session.exec(select(AssertionRow)).all()
            session.exec(select(ConflictRow)).all()
            session.exec(select(DecisionRow)).all()
            session.exec(select(EventRow)).all()
            session.exec(select(KernelRow)).all()
            session.exec(select(ParametersRow)).all()
            session.exec(select(VariantSetRow)).all()
            session.exec(select(ProjectRow)).all()


class TestListProjects:
    def _store(self) -> SQLiteStore:
        return SQLiteStore(":memory:")

    def _insert_project(self, store: SQLiteStore, project_id: str, name: str = "Test") -> None:
        row = ProjectRow(
            project_id=project_id, project_name=name,
            exchange_count=0, created_at=_TS, last_updated=_TS,
        )
        with store.get_session() as session:
            session.add(row)
            session.commit()

    def test_empty_store_returns_empty_list(self) -> None:
        assert self._store().list_projects() == []

    def test_one_project_returns_one_id(self) -> None:
        store = self._store()
        self._insert_project(store, "proj_aaa")
        assert store.list_projects() == ["proj_aaa"]

    def test_three_projects_returns_all_three_ids(self) -> None:
        store = self._store()
        ids = ["proj_aaa", "proj_bbb", "proj_ccc"]
        for pid in ids:
            self._insert_project(store, pid)
        result = store.list_projects()
        assert set(result) == set(ids)
        assert len(result) == 3

    def test_list_projects_returns_only_project_ids(self) -> None:
        store = self._store()
        self._insert_project(store, "proj_xyz", name="My Project")
        result = store.list_projects()
        assert result == ["proj_xyz"]
        assert isinstance(result[0], str)


class TestProjectExists:
    def _store(self) -> SQLiteStore:
        return SQLiteStore(":memory:")

    def _insert_project(self, store: SQLiteStore, project_id: str) -> None:
        row = ProjectRow(
            project_id=project_id, project_name="Test",
            exchange_count=0, created_at=_TS, last_updated=_TS,
        )
        with store.get_session() as session:
            session.add(row)
            session.commit()

    def test_returns_false_on_empty_store(self) -> None:
        assert self._store().project_exists("foo") is False

    def test_returns_false_for_unknown_id(self) -> None:
        store = self._store()
        self._insert_project(store, "proj_known")
        assert store.project_exists("proj_unknown") is False

    def test_returns_true_after_insert(self) -> None:
        store = self._store()
        self._insert_project(store, "proj_real")
        assert store.project_exists("proj_real") is True

    def test_case_sensitive_id_check(self) -> None:
        store = self._store()
        self._insert_project(store, "proj_abc")
        assert store.project_exists("proj_ABC") is False
        assert store.project_exists("proj_abc") is True


class TestGetSession:
    def test_get_session_returns_session_instance(self) -> None:
        store = SQLiteStore(":memory:")
        session = store.get_session()
        assert isinstance(session, Session)
        session.close()

    def test_session_can_add_and_commit_row(self) -> None:
        store = SQLiteStore(":memory:")
        row = ProjectRow(
            project_id="proj_session_test", project_name="Session Test",
            exchange_count=0, created_at=_TS, last_updated=_TS,
        )
        with store.get_session() as session:
            session.add(row)
            session.commit()
        assert store.project_exists("proj_session_test") is True

    def test_two_sessions_share_same_data(self) -> None:
        store = SQLiteStore(":memory:")
        with store.get_session() as session_a:
            session_a.add(ProjectRow(
                project_id="proj_shared", project_name="Shared",
                exchange_count=0, created_at=_TS, last_updated=_TS,
            ))
            session_a.commit()
        with store.get_session() as session_b:
            result = session_b.get(ProjectRow, "proj_shared")
        assert result is not None
        assert result.project_id == "proj_shared"

    def test_session_add_multiple_rows_different_tables(self) -> None:
        store = SQLiteStore(":memory:")
        with store.get_session() as session:
            session.add(ProjectRow(
                project_id="proj_multi", project_name="Multi",
                exchange_count=0, created_at=_TS, last_updated=_TS,
            ))
            session.add(EventRow(
                id="evt_aabbccddeeff", project_id="proj_multi",
                event_type="assertion_created", timestamp=_TS,
                actor="ai", target_id="ast_111111111111", detail_json="{}",
            ))
            session.commit()
        with store.get_session() as session:
            assert len(session.exec(select(ProjectRow)).all()) == 1
            assert len(session.exec(select(EventRow)).all()) == 1


class TestFilePersistence:
    def test_data_persists_after_store_disposal(self, tmp_path: Path) -> None:
        db_file = str(tmp_path / "test.db")
        store1 = SQLiteStore(db_file)
        with store1.get_session() as session:
            session.add(ProjectRow(
                project_id="proj_persist", project_name="Persisted Project",
                exchange_count=42, created_at=_TS, last_updated=_TS,
            ))
            session.commit()
        del store1
        store2 = SQLiteStore(db_file)
        with store2.get_session() as session:
            row = session.get(ProjectRow, "proj_persist")
        assert row is not None
        assert row.project_name == "Persisted Project"
        assert row.exchange_count == 42

    def test_multiple_rows_persist_across_reopen(self, tmp_path: Path) -> None:
        db_file = str(tmp_path / "multi.db")
        store1 = SQLiteStore(db_file)
        ids = ["proj_one", "proj_two", "proj_three"]
        for pid in ids:
            with store1.get_session() as session:
                session.add(ProjectRow(
                    project_id=pid, project_name=pid,
                    exchange_count=0, created_at=_TS, last_updated=_TS,
                ))
                session.commit()
        del store1
        store2 = SQLiteStore(db_file)
        assert set(store2.list_projects()) == set(ids)

    def test_in_memory_store_does_not_persist_to_file(self, tmp_path: Path) -> None:
        db_file = tmp_path / "should_not_exist.db"
        store = SQLiteStore(":memory:")
        with store.get_session() as session:
            session.add(ProjectRow(
                project_id="proj_mem", project_name="Memory Only",
                exchange_count=0, created_at=_TS, last_updated=_TS,
            ))
            session.commit()
        del store
        assert not db_file.exists()
