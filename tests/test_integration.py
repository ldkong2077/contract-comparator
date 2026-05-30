"""
集成测试 — 核心比对流程
端到端验证：任务创建 → 字段抽取 → 比对 → 结果存储
"""
import os
import sys
import json
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from database import DatabaseManager
from comparator import Comparator
from field_extractor import FieldExtractor


class TestEndToEndComparisonFlow(unittest.TestCase):
    """端到端比对流程集成测试"""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmp_dir, "integration_test.db")
        self.db = DatabaseManager(db_path=self.db_path)
        self.comparator = Comparator()
        self.extractor = FieldExtractor()

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

    def test_full_comparison_pipeline(self):
        """完整比对流程：创建任务 → 抽取字段 → 比对 → 存储结果"""
        # 1. 创建比对任务
        self.db.create_task(
            task_id="pipeline-001",
            word_file="原版合同.pdf",
            pdf_file="扫描件.pdf"
        )

        # 2. 模拟字段抽取
        text_a = "合同金额：人民币100,000.00元\n签订日期：2025-01-15\n甲方：北京某某科技有限公司"
        text_b = "合同金额：人民币120,000.00元\n签订日期：2025-01-15\n甲方：北京某某科技有限公司"

        fields_a = self.extractor.extract_all(text_a, source="原版合同.pdf")
        fields_b = self.extractor.extract_all(text_b, source="扫描件.pdf")
        self.assertIsInstance(fields_a, dict)
        self.assertIsInstance(fields_b, dict)

        # 3. 执行比对
        comparison_result = self.comparator.compare(fields_a, fields_b)
        self.assertIsNotNone(comparison_result)
        self.assertIsInstance(comparison_result, dict)

        # 4. 存储比对结果
        result_json = json.dumps(comparison_result, ensure_ascii=False, default=str)
        self.db.update_task("pipeline-001", status="completed", result_summary=result_json)

        # 5. 查询并验证
        stored = self.db.get_task("pipeline-001")
        self.assertIsNotNone(stored)
        self.assertEqual(stored["status"], "completed")


class TestMultipleComparisons(unittest.TestCase):
    """多任务并发比对集成测试"""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmp_dir, "multi_test.db")
        self.db = DatabaseManager(db_path=self.db_path)
        self.extractor = FieldExtractor()

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

    def test_multiple_comparisons(self):
        """多任务并发比对"""
        task_ids = []
        for i in range(5):
            task_id = f"multi-{i:03d}"
            self.db.create_task(
                task_id=task_id,
                word_file=f"原版_{i}.pdf",
                pdf_file=f"扫描件_{i}.pdf"
            )
            task_ids.append(task_id)

        self.assertEqual(len(task_ids), 5)
        self.assertEqual(len(set(task_ids)), 5)

        all_tasks = self.db.list_tasks()
        self.assertGreaterEqual(len(all_tasks), 5)

    def test_status_lifecycle(self):
        """任务状态生命周期"""
        task_id = "lifecycle-001"
        self.db.create_task(task_id=task_id, word_file="a.pdf", pdf_file="b.pdf")

        result = self.db.get_task(task_id)
        self.assertEqual(result["status"], "pending")

        self.db.update_task(task_id, status="processing")
        result = self.db.get_task(task_id)
        self.assertEqual(result["status"], "processing")

        self.db.update_task(task_id, status="completed")
        result = self.db.get_task(task_id)
        self.assertEqual(result["status"], "completed")
        self.assertIsNotNone(result["completed_at"])


class TestSecurityAndDatabaseIntegration(unittest.TestCase):
    """安全模块与数据库集成测试"""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmp_dir, "sec_db_test.db")
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

    def test_sensitive_data_not_in_plaintext(self):
        """敏感数据掩码后不应包含原始信息"""
        from security import mask_sensitive
        sensitive_text = "联系电话：13812345678"
        masked, entities = mask_sensitive(sensitive_text)
        self.assertNotIn("13812345678", masked)

    def test_file_path_validation_before_storage(self):
        """存储前应验证文件路径"""
        from security import validate_upload
        result = validate_upload("test.pdf", ["pdf", "docx", "xlsx", "png", "jpg"])
        self.assertIsNotNone(result)


class TestConfigIntegration(unittest.TestCase):
    """配置模块集成测试"""

    def test_output_config_exists(self):
        """OUTPUT_CONFIG 应存在"""
        from config import OUTPUT_CONFIG
        self.assertIsNotNone(OUTPUT_CONFIG)
        self.assertIsInstance(OUTPUT_CONFIG, dict)

    def test_auth_config_exists(self):
        """AUTH_CONFIG 应存在"""
        from config import AUTH_CONFIG
        self.assertIsNotNone(AUTH_CONFIG)
        self.assertIsInstance(AUTH_CONFIG, dict)


if __name__ == "__main__":
    unittest.main(verbosity=2)
