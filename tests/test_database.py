"""
DatabaseManager 单元测试
测试 SQLite 存储：任务 CRUD、审计日志、自动清理、上下文管理器、线程安全、JSON 迁移
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import json
import threading
import time
from datetime import datetime, timedelta, timezone

import pytest

from database import DatabaseManager


class TestTaskCRUD:
    """比对任务 CRUD 测试"""

    def test_create_and_get_task(self, db_manager):
        """创建任务后应能通过 task_id 查询到"""
        db_manager.create_task("t1", "a.docx", "b.pdf", "user1")
        task = db_manager.get_task("t1")
        assert task is not None
        assert task["task_id"] == "t1"
        assert task["word_file"] == "a.docx"
        assert task["pdf_file"] == "b.pdf"
        assert task["status"] == "pending"
        assert task["user_id"] == "user1"

    def test_update_task(self, db_manager):
        """更新任务字段后应反映在查询结果中"""
        db_manager.create_task("t2", "a.docx", "b.pdf")
        result = db_manager.update_task("t2", status="completed", result_summary="无差异")
        assert result is True
        task = db_manager.get_task("t2")
        assert task["status"] == "completed"
        assert task["result_summary"] == "无差异"
        # 状态变为 completed 时应自动设置 completed_at
        assert task["completed_at"] is not None

    def test_update_task_no_kwargs(self, db_manager):
        """不传更新字段时应返回 False"""
        db_manager.create_task("t2b", "a.docx", "b.pdf")
        result = db_manager.update_task("t2b")
        assert result is False

    def test_update_nonexistent_task(self, db_manager):
        """更新不存在的任务应返回 False"""
        result = db_manager.update_task("nonexistent", status="completed")
        assert result is False

    def test_list_tasks(self, db_manager):
        """列出任务应包含所有已创建的任务"""
        db_manager.create_task("t3a", "a.docx", "b.pdf", "user1")
        db_manager.create_task("t3b", "c.docx", "d.pdf", "user2")
        tasks = db_manager.list_tasks()
        assert len(tasks) >= 2

    def test_list_tasks_by_user(self, db_manager):
        """按用户过滤任务"""
        db_manager.create_task("t4a", "a.docx", "b.pdf", "user1")
        db_manager.create_task("t4b", "c.docx", "d.pdf", "user2")
        tasks = db_manager.list_tasks(user_id="user1")
        assert all(t["user_id"] == "user1" for t in tasks)

    def test_list_tasks_pagination(self, db_manager):
        """分页查询任务"""
        for i in range(5):
            db_manager.create_task(f"t5_{i}", f"{i}.docx", f"{i}.pdf")
        # 第一页
        page1 = db_manager.list_tasks(limit=2, offset=0)
        assert len(page1) <= 2
        # 第二页
        page2 = db_manager.list_tasks(limit=2, offset=2)
        assert len(page2) <= 2

    def test_delete_task(self, db_manager):
        """删除任务后应查询不到"""
        db_manager.create_task("t6", "a.docx", "b.pdf")
        result = db_manager.delete_task("t6")
        assert result is True
        task = db_manager.get_task("t6")
        assert task is None

    def test_delete_nonexistent_task(self, db_manager):
        """删除不存在的任务应返回 False"""
        result = db_manager.delete_task("nonexistent")
        assert result is False


class TestAuditLogCRUD:
    """审计日志 CRUD 测试"""

    def test_log_event_and_query(self, db_manager):
        """记录审计事件后应能查询到"""
        db_manager.log_event("login", "user1", {"ip": "127.0.0.1"})
        logs = db_manager.query_logs(user_id="user1")
        assert len(logs) >= 1
        assert logs[0]["event_type"] == "login"
        assert logs[0]["details"]["ip"] == "127.0.0.1"

    def test_query_logs_by_event_type(self, db_manager):
        """按事件类型过滤日志"""
        db_manager.log_event("compare", "user1")
        db_manager.log_event("export", "user1")
        logs = db_manager.query_logs(event_type="compare")
        assert all(l["event_type"] == "compare" for l in logs)

    def test_query_logs_by_time_range(self, db_manager):
        """按时间范围过滤日志"""
        now = datetime.now(timezone.utc)
        start = (now - timedelta(hours=1)).isoformat()
        end = (now + timedelta(hours=1)).isoformat()
        db_manager.log_event("test_event", "user1")
        logs = db_manager.query_logs(start_time=start, end_time=end)
        assert isinstance(logs, list)

    def test_query_logs_limit(self, db_manager):
        """日志查询应受 limit 限制"""
        for i in range(5):
            db_manager.log_event("bulk_event", "user1", {"idx": i})
        logs = db_manager.query_logs(limit=3)
        assert len(logs) <= 3


class TestCleanup:
    """自动清理测试"""

    def test_cleanup_expired_tasks(self, db_manager):
        """清理过期任务应删除超龄记录"""
        db_manager.create_task("old_task", "a.docx", "b.pdf")
        # 手动将 created_at 设为很久以前
        with db_manager._connect() as conn:
            old_time = (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat()
            conn.execute(
                "UPDATE comparison_tasks SET created_at = ? WHERE task_id = ?",
                (old_time, "old_task"),
            )
        deleted = db_manager.cleanup_expired_tasks(max_age_hours=24)
        assert deleted >= 1
        assert db_manager.get_task("old_task") is None

    def test_cleanup_expired_tasks_keeps_recent(self, db_manager):
        """清理不应删除近期任务"""
        db_manager.create_task("recent_task", "a.docx", "b.pdf")
        deleted = db_manager.cleanup_expired_tasks(max_age_hours=24)
        assert db_manager.get_task("recent_task") is not None

    def test_cleanup_expired_audit_logs(self, db_manager):
        """清理过期审计日志应删除超龄记录"""
        db_manager.log_event("old_log", "user1")
        # 手动将 timestamp 设为很久以前
        with db_manager._connect() as conn:
            old_time = (datetime.now(timezone.utc) - timedelta(days=180)).isoformat()
            conn.execute(
                "UPDATE audit_logs SET timestamp = ? WHERE event_type = ?",
                (old_time, "old_log"),
            )
        deleted = db_manager.cleanup_expired_audit_logs(max_age_days=90)
        assert deleted >= 1

    def test_auto_cleanup(self, db_manager):
        """综合自动清理应返回任务和日志的删除数量"""
        db_manager.create_task("auto_cleanup_task", "a.docx", "b.pdf")
        result = db_manager.run_auto_cleanup(task_max_age_hours=24, log_max_age_days=90)
        assert "tasks" in result
        assert "audit_logs" in result
        assert isinstance(result["tasks"], int)
        assert isinstance(result["audit_logs"], int)


class TestContextManager:
    """上下文管理器测试"""

    def test_context_manager(self, tmp_db_path):
        """使用 with 语句应正常创建和退出"""
        with DatabaseManager(db_path=tmp_db_path) as db:
            db.create_task("ctx_task", "a.docx", "b.pdf")
            task = db.get_task("ctx_task")
            assert task is not None
            assert task["task_id"] == "ctx_task"


class TestThreadSafety:
    """线程安全基本测试"""

    def test_thread_safety(self, db_manager):
        """多线程并发写入不应导致数据损坏"""
        errors = []
        num_threads = 5
        tasks_per_thread = 10

        def create_tasks(thread_id):
            try:
                for i in range(tasks_per_thread):
                    db_manager.create_task(
                        f"thread_{thread_id}_task_{i}",
                        f"t{thread_id}_{i}.docx",
                        f"t{thread_id}_{i}.pdf",
                    )
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=create_tasks, args=(tid,))
            for tid in range(num_threads)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"线程安全测试出错: {errors}"
        # 验证所有任务都已创建
        tasks = db_manager.list_tasks(limit=1000)
        assert len(tasks) >= num_threads * tasks_per_thread


class TestMigrationFromJson:
    """JSON 数据迁移测试"""

    def test_migration_from_json_api_keys(self, db_manager, tmp_path):
        """从 JSON 文件迁移 API Keys 数据"""
        json_data = {
            "keys": [
                {
                    "key_id": "key1",
                    "key_hash": "abc123",
                    "role": "admin",
                    "label": "测试密钥",
                    "created_at": "2024-01-01T00:00:00",
                    "is_active": True,
                },
            ]
        }
        json_path = str(tmp_path / "api_keys.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(json_data, f, ensure_ascii=False)

        count = db_manager.migrate_from_json(json_path)
        assert count >= 1

    def test_migration_from_json_profiles(self, db_manager, tmp_path):
        """从 JSON 文件迁移 Profile 数据"""
        json_data = {
            "name": "默认配置",
            "created_at": "2024-01-01T00:00:00",
            "updated_at": "2024-01-01T00:00:00",
            "industry": "general",
        }
        json_path = str(tmp_path / "profile.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(json_data, f, ensure_ascii=False)

        count = db_manager.migrate_from_json(json_path)
        assert count >= 1

    def test_migration_from_nonexistent_file(self, db_manager):
        """从不存在的文件迁移应返回 0"""
        count = db_manager.migrate_from_json("/nonexistent/path.json")
        assert count == 0
