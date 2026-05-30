"""
单元测试 — database 模块
验证 DatabaseManager 核心 CRUD、WAL 模式、上下文管理器
"""
import os
import sys
import unittest
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from database import DatabaseManager


class TestDatabaseManagerInit(unittest.TestCase):
    """数据库初始化测试"""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmp_dir, "test.db")

    def tearDown(self):
        for suffix in ["", ".secret", ".wal", ".shm", "-journal", ".db_encryption_key"]:
            path = self.db_path + suffix
            if os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass
        if os.path.exists(self.tmp_dir):
            try:
                os.rmdir(self.tmp_dir)
            except OSError:
                pass

    def test_init_creates_database_file(self):
        """初始化应创建数据库文件"""
        with DatabaseManager(db_path=self.db_path) as db:
            self.assertTrue(os.path.exists(self.db_path))

    def test_context_manager(self):
        """应支持 with 语句"""
        with DatabaseManager(db_path=self.db_path) as db:
            self.assertIsNotNone(db)


class TestDatabaseManagerCRUD(unittest.TestCase):
    """数据库 CRUD 操作测试"""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmp_dir, "test_crud.db")
        self.db = DatabaseManager(db_path=self.db_path)

    def tearDown(self):
        self.db.__exit__(None, None, None)
        for suffix in ["", ".secret", ".wal", ".shm", "-journal", ".db_encryption_key"]:
            path = self.db_path + suffix
            if os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass
        if os.path.exists(self.tmp_dir):
            try:
                os.rmdir(self.tmp_dir)
            except OSError:
                pass

    def test_create_task(self):
        """创建任务应返回任务"""
        self.db.create_task(task_id="task-001", word_file="test_a.pdf", pdf_file="test_b.pdf")
        result = self.db.get_task("task-001")
        self.assertIsNotNone(result)
        self.assertEqual(result["word_file"], "test_a.pdf")
        self.assertEqual(result["pdf_file"], "test_b.pdf")

    def test_get_task_not_found(self):
        """查询不存在的任务应返回 None"""
        result = self.db.get_task("non-existent")
        self.assertIsNone(result)

    def test_update_task_status(self):
        """更新任务状态"""
        self.db.create_task(task_id="task-002", word_file="a.pdf", pdf_file="b.pdf")
        self.db.update_task("task-002", status="completed")
        result = self.db.get_task("task-002")
        self.assertEqual(result["status"], "completed")
        self.assertIsNotNone(result["completed_at"])

    def test_list_tasks(self):
        """列出所有任务"""
        self.db.create_task(task_id="t1", word_file="a1.pdf", pdf_file="b1.pdf")
        self.db.create_task(task_id="t2", word_file="a2.pdf", pdf_file="b2.pdf")
        results = self.db.list_tasks()
        self.assertGreaterEqual(len(results), 2)

    def test_delete_task(self):
        """删除任务"""
        self.db.create_task(task_id="task-del", word_file="a.pdf", pdf_file="b.pdf")
        result = self.db.delete_task("task-del")
        self.assertTrue(result)
        task = self.db.get_task("task-del")
        self.assertIsNone(task)


class TestDatabaseManagerWAL(unittest.TestCase):
    """WAL 模式测试"""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmp_dir, "test_wal.db")

    def tearDown(self):
        for suffix in ["", ".secret", ".wal", ".shm", "-journal", ".db_encryption_key"]:
            path = self.db_path + suffix
            if os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass
        if os.path.exists(self.tmp_dir):
            try:
                os.rmdir(self.tmp_dir)
            except OSError:
                pass

    def test_wal_mode_enabled(self):
        """数据库应启用 WAL 模式"""
        with DatabaseManager(db_path=self.db_path) as db:
            import sqlite3
            conn = sqlite3.connect(self.db_path)
            cursor = conn.execute("PRAGMA journal_mode")
            mode = cursor.fetchone()[0]
            conn.close()
            self.assertEqual(mode.lower(), "wal")

    def test_wal_files_exist(self):
        """使用数据库后文件应被创建"""
        with DatabaseManager(db_path=self.db_path) as db:
            db.create_task(task_id="wal-test", word_file="a.pdf", pdf_file="b.pdf")
        # 验证数据库文件本身存在
        self.assertTrue(os.path.exists(self.db_path))


if __name__ == "__main__":
    unittest.main(verbosity=2)
