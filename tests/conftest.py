"""
共享测试夹具
提供数据库、样本文本、OCR 结果、比对结果等通用 fixture
"""
import sys
import os

# 确保项目根目录在 sys.path 中
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
import tempfile


@pytest.fixture
def tmp_db_path(tmp_path):
    """返回临时 SQLite 数据库路径"""
    return str(tmp_path / "test_contract.db")


@pytest.fixture
def db_manager(tmp_db_path):
    """创建并销毁 DatabaseManager 实例"""
    from database import DatabaseManager
    manager = DatabaseManager(db_path=tmp_db_path)
    yield manager
    # 清理：删除数据库文件及相关文件
    for suffix in ["", ".secret", ".wal", ".shm", "-journal"]:
        path = tmp_db_path + suffix
        if os.path.exists(path):
            try:
                os.remove(path)
            except OSError:
                pass
    # 删除加密密钥文件
    db_dir = os.path.dirname(tmp_db_path)
    enc_key = os.path.join(db_dir, ".db_encryption_key")
    if os.path.exists(enc_key):
        try:
            os.remove(enc_key)
        except OSError:
            pass


@pytest.fixture
def sample_word_text():
    """样本 Word 合同文本（中文）"""
    return """
    合同编号：HT-2024-001

    甲方：深圳市XX科技有限公司
    乙方：北京市YY咨询有限公司

    根据《中华人民共和国合同法》，甲乙双方经协商一致，签订本合同。

    第一条 项目概况
    本项目为XX系统开发项目，包干费用为¥900000.00元。

    第二条 工期
    工期：180天，自2024年1月15日起至2024年7月14日止。

    第三条 付款方式
    合同签订后支付合同总价的30%，即¥270000.00元；
    项目验收合格后支付剩余70%，即¥630000.00元。

    第四条 违约责任
    任何一方违约，应向守约方支付违约金50000元。
    违约金按每日5%计算。

    第五条 保密条款
    双方应对本合同内容严格保密。

    签订日期：2024年1月15日
    """


@pytest.fixture
def sample_pdf_text():
    """样本 PDF OCR 识别文本（中文，与 Word 文本有差异）"""
    return """
    合同编号：HT-2024-001

    甲方：深圳市XX科技有限公司
    乙方：北京市YY咨询有限公司

    根据《中华人民共和国合同法》，甲乙双方经协商一致，签订本合同。

    第一条 项目概况
    本项目为XX系统开发项目，包干费用为¥900000.00元。

    第二条 工期
    工期：180天，自2024年1月15日起至2024年7月15日止。

    第三条 付款方式
    合同签订后支付合同总价的30%，即¥270000.00元；
    项目验收合格后支付剩余70%，即¥630000.00元。

    第四条 违约责任
    任何一方违约，应向守约方支付违约金5000元。
    违约金按每日3%计算。

    第五条 保密条款
    双方应对本合同内容严格保密。

    签订日期：2024年1月16日
    """


@pytest.fixture
def sample_ocr_results():
    """模拟 OCR 识别结果（含置信度）"""
    return [
        {
            "text": "合同编号：HT-2024-001",
            "confidence": 0.95,
            "bbox": [[10, 20], [200, 20], [200, 40], [10, 40]],
        },
        {
            "text": "甲方：深圳市XX科技有限公司",
            "confidence": 0.92,
            "bbox": [[10, 50], [250, 50], [250, 70], [10, 70]],
        },
        {
            "text": "包干费用为¥900000.00元",
            "confidence": 0.88,
            "bbox": [[10, 120], [220, 120], [220, 140], [10, 140]],
        },
        {
            "text": "工期：180天",
            "confidence": 0.91,
            "bbox": [[10, 160], [130, 160], [130, 180], [10, 180]],
        },
        {
            "text": "违约金50000元",
            "confidence": 0.75,
            "bbox": [[10, 220], [150, 220], [150, 240], [10, 240]],
        },
        {
            "text": "5%",
            "confidence": 0.65,
            "bbox": [[10, 260], [50, 260], [50, 280], [10, 280]],
        },
    ]


@pytest.fixture
def sample_comparison_result():
    """模拟比对结果"""
    return {
        "numbers": {
            "matched": [
                {"word": {"raw": "900000", "normalized": 900000.0}, "pdf": {"raw": "900000", "normalized": 900000.0}},
            ],
            "missing_in_pdf": [],
            "extra_in_pdf": [],
            "has_diff": False,
        },
        "dates": {
            "matched": [
                {"raw": "2024-01-15", "normalized": "2024-01-15"},
            ],
            "missing_in_pdf": [
                {"raw": "2024-07-14", "normalized": "2024-07-14"},
            ],
            "extra_in_pdf": [
                {"raw": "2024-07-15", "normalized": "2024-07-15"},
            ],
            "has_diff": True,
        },
        "amounts_words": {
            "matched": [],
            "missing_in_pdf": [],
            "extra_in_pdf": [],
            "has_diff": False,
        },
        "amounts_digits": {
            "matched": [],
            "missing_in_pdf": [
                {"raw": "50000", "normalized": 50000.0, "keyword": "违约金"},
            ],
            "extra_in_pdf": [
                {"raw": "5000", "normalized": 5000.0, "keyword": "违约金"},
            ],
            "has_diff": True,
        },
        "percentages": {
            "matched": [],
            "missing_in_pdf": [
                {"raw": "5%", "normalized": 0.05},
            ],
            "extra_in_pdf": [
                {"raw": "3%", "normalized": 0.03},
            ],
            "has_diff": True,
        },
    }
