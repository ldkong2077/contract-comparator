"""
比对配置文件管理模块

提供比对配置文件的定义、预设行业配置、持久化存储及运行时应用到 config.py 的能力。
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, ClassVar

import config


# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

DEFAULT_PROFILES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "profiles")
ACTIVE_PROFILE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".active_profile")


# ---------------------------------------------------------------------------
# 1. Profile 数据类
# ---------------------------------------------------------------------------

@dataclass
class Profile:
    """比对配置文件。

    Attributes:
        name: 配置文件名称（唯一标识）。
        description: 配置文件的用途说明。
        contract_type: 适用的合同类型（如 租赁合同、采购合同）。
        amount_keywords: 金额相关关键词列表。
        number_patterns: 数字匹配正则表达式列表。
        date_patterns: 日期匹配正则表达式列表。
        risk_rules: 风险规则字典，映射风险类型到严重等级（high / medium / low）。
        comparison_thresholds: 比对阈值字典（number_tolerance, similarity_threshold, min_segment_length）。
        created_at: 创建时间（ISO 格式字符串）。
        updated_at: 最后更新时间（ISO 格式字符串）。
    """

    name: str
    description: str = ""
    contract_type: str = "通用合同"
    amount_keywords: list[str] = field(default_factory=list)
    number_patterns: list[str] = field(default_factory=list)
    date_patterns: list[str] = field(default_factory=list)
    risk_rules: dict[str, str] = field(default_factory=dict)
    comparison_thresholds: dict = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self) -> None:
        """初始化时自动填充时间戳。"""
        now = datetime.now().isoformat(timespec="seconds")
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now

    def to_dict(self) -> dict[str, Any]:
        """将 Profile 序列化为字典。"""
        return {
            "name": self.name,
            "description": self.description,
            "contract_type": self.contract_type,
            "amount_keywords": self.amount_keywords,
            "number_patterns": self.number_patterns,
            "date_patterns": self.date_patterns,
            "risk_rules": self.risk_rules,
            "comparison_thresholds": self.comparison_thresholds,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Profile":
        """从字典反序列化为 Profile。"""
        return cls(
            name=data["name"],
            description=data.get("description", ""),
            contract_type=data.get("contract_type", "通用合同"),
            amount_keywords=data.get("amount_keywords", []),
            number_patterns=data.get("number_patterns", []),
            date_patterns=data.get("date_patterns", []),
            risk_rules=data.get("risk_rules", {}),
            comparison_thresholds=data.get("comparison_thresholds", {}),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
        )


# ---------------------------------------------------------------------------
# 2. 行业预设配置
# ---------------------------------------------------------------------------

PRESETS: dict[str, Profile] = {
    "租赁合同": Profile(
        name="租赁合同",
        description="适用于房屋、商铺、场地等租赁合同的比对",
        contract_type="租赁合同",
        amount_keywords=[
            "¥", "￥", "$", "元",
            "租金", "押金", "物业费", "物业管理费",
            "水电费", "保证金", "违约金",
            "金额", "合计", "总额", "总计",
        ],
        number_patterns=[
            r"\d{1,3}(?:,\d{3})*(?:\.\d+)?",
            r"\d+%",
        ],
        date_patterns=[
            r"\d{4}[-/.年]\d{1,2}[-/.月]\d{1,2}[日号]?",
            r"\d{4}年\s*\d{1,2}月\s*\d{1,2}日",
            r"\d{1,2}[-/.月]\d{1,2}[日号]?\s*\d{4}年?",
        ],
        risk_rules={
            "押金减少": "high",
            "租期缩短": "high",
            "租金提高": "medium",
            "物业费提高": "medium",
            "违约金提高": "low",
            "面积减少": "medium",
        },
        comparison_thresholds={
            "number_tolerance": 0.01,
            "similarity_threshold": 0.85,
            "min_segment_length": 4,
        },
    ),
    "采购合同": Profile(
        name="采购合同",
        description="适用于货物、设备、原材料等采购合同的比对",
        contract_type="采购合同",
        amount_keywords=[
            "¥", "￥", "$", "元",
            "采购价", "单价", "总价", "合计",
            "金额", "质保金", "保证金", "违约金",
            "运费", "保险费", "税费",
        ],
        number_patterns=[
            r"\d{1,3}(?:,\d{3})*(?:\.\d+)?",
            r"\d+%",
        ],
        date_patterns=[
            r"\d{4}[-/.年]\d{1,2}[-/.月]\d{1,2}[日号]?",
            r"\d{4}年\s*\d{1,2}月\s*\d{1,2}日",
            r"\d{1,2}[-/.月]\d{1,2}[日号]?\s*\d{4}年?",
        ],
        risk_rules={
            "单价提高": "high",
            "质保缩短": "high",
            "交货期延长": "medium",
            "质保金减少": "medium",
            "违约金降低": "low",
        },
        comparison_thresholds={
            "number_tolerance": 0.01,
            "similarity_threshold": 0.85,
            "min_segment_length": 4,
        },
    ),
    "劳动合同": Profile(
        name="劳动合同",
        description="适用于劳动合同、劳务协议的比对",
        contract_type="劳动合同",
        amount_keywords=[
            "¥", "￥", "元",
            "工资", "薪资", "基本工资", "绩效工资",
            "社保", "公积金", "补贴", "津贴",
            "奖金", "年终奖", "违约金",
            "竞业限制补偿金",
        ],
        number_patterns=[
            r"\d{1,3}(?:,\d{3})*(?:\.\d+)?",
            r"\d+%",
        ],
        date_patterns=[
            r"\d{4}[-/.年]\d{1,2}[-/.月]\d{1,2}[日号]?",
            r"\d{4}年\s*\d{1,2}月\s*\d{1,2}日",
            r"\d{1,2}[-/.月]\d{1,2}[日号]?\s*\d{4}年?",
        ],
        risk_rules={
            "薪资降低": "high",
            "试用期延长": "medium",
            "社保基数降低": "high",
            "竞业限制范围扩大": "medium",
            "违约金提高": "medium",
            "年假减少": "low",
        },
        comparison_thresholds={
            "number_tolerance": 0.01,
            "similarity_threshold": 0.85,
            "min_segment_length": 4,
        },
    ),
    "工程施工合同": Profile(
        name="工程施工合同",
        description="适用于工程建设、装修施工等合同的比对",
        contract_type="工程施工合同",
        amount_keywords=[
            "¥", "￥", "元",
            "工程款", "预付款", "进度款", "结算款",
            "质保金", "履约保证金", "违约金",
            "赔偿金", "总价", "合计", "金额",
        ],
        number_patterns=[
            r"\d{1,3}(?:,\d{3})*(?:\.\d+)?",
            r"\d+%",
        ],
        date_patterns=[
            r"\d{4}[-/.年]\d{1,2}[-/.月]\d{1,2}[日号]?",
            r"\d{4}年\s*\d{1,2}月\s*\d{1,2}日",
            r"\d{1,2}[-/.月]\d{1,2}[日号]?\s*\d{4}年?",
        ],
        risk_rules={
            "工程款减少": "high",
            "工期延长": "medium",
            "质保期缩短": "medium",
            "违约金降低": "low",
            "履约保证金减少": "medium",
        },
        comparison_thresholds={
            "number_tolerance": 0.01,
            "similarity_threshold": 0.85,
            "min_segment_length": 4,
        },
    ),
    "通用合同": Profile(
        name="通用合同",
        description="适用于各类通用合同的比对，提供均衡的默认设置",
        contract_type="通用合同",
        amount_keywords=[
            "¥", "￥", "$", "元",
            "金额", "总价", "合计", "总额", "总计",
            "费用", "价款", "报酬", "单价",
            "违约金", "赔偿金", "保证金", "押金", "罚金",
            "包干费用", "合同总价", "合同总额", "合同费用",
            "含税", "不含税", "增值税",
        ],
        number_patterns=[
            r"\d{1,3}(?:,\d{3})*(?:\.\d+)?",
            r"\d+%",
        ],
        date_patterns=[
            r"\d{4}[-/.年]\d{1,2}[-/.月]\d{1,2}[日号]?",
            r"\d{4}年\s*\d{1,2}月\s*\d{1,2}日",
            r"\d{1,2}[-/.月]\d{1,2}[日号]?\s*\d{4}年?",
        ],
        risk_rules={
            "金额变更": "medium",
            "日期变更": "low",
            "条款删除": "high",
            "条款新增": "medium",
        },
        comparison_thresholds={
            "number_tolerance": 0.01,
            "similarity_threshold": 0.85,
            "min_segment_length": 4,
        },
    ),
}


# ---------------------------------------------------------------------------
# 3. ProfileManager 类
# ---------------------------------------------------------------------------

class ProfileManager:
    """比对配置文件管理器。

    负责配置文件的持久化（JSON 文件）、预设管理及激活状态的维护。
    配置文件存储在 ``./profiles/`` 目录下，每个文件对应一个 Profile。
    """

    # 类变量：存储目录
    _profiles_dir: ClassVar[str] = DEFAULT_PROFILES_DIR
    _active_profile_file: ClassVar[str] = ACTIVE_PROFILE_FILE

    def __init__(self, profiles_dir: str | None = None) -> None:
        """初始化管理器。

        Args:
            profiles_dir: 自定义配置文件存储目录，为 None 时使用默认目录。
        """
        if profiles_dir is not None:
            self._profiles_dir = profiles_dir
        os.makedirs(self._profiles_dir, exist_ok=True)

    # ------------------------------------------------------------------
    # 内部辅助方法
    # ------------------------------------------------------------------

    @staticmethod
    def _profile_path(profiles_dir: str, name: str) -> str:
        """获取指定名称的配置文件路径。

        Args:
            profiles_dir: 存储目录。
            name: 配置文件名称。

        Returns:
            对应的 JSON 文件完整路径。
        """
        safe_name = name.replace("/", "_").replace("\\", "_")
        return os.path.join(profiles_dir, f"{safe_name}.json")

    # ------------------------------------------------------------------
    # 公开方法
    # ------------------------------------------------------------------

    def load_profile(self, name: str) -> Profile:
        """从 JSON 文件加载配置。

        Args:
            name: 配置文件名称（不含扩展名）。

        Returns:
            反序列化后的 Profile 对象。

        Raises:
            FileNotFoundError: 配置文件不存在时抛出。
        """
        path = self._profile_path(self._profiles_dir, name)
        if not os.path.isfile(path):
            raise FileNotFoundError(f"配置文件不存在: {path}")
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return Profile.from_dict(data)

    def save_profile(self, name: str, profile: Profile) -> None:
        """将 Profile 保存为 JSON 文件。

        Args:
            name: 保存的文件名（不含扩展名）。
            profile: 要保存的 Profile 对象。
        """
        profile.updated_at = datetime.now().isoformat(timespec="seconds")
        path = self._profile_path(self._profiles_dir, name)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(profile.to_dict(), fh, ensure_ascii=False, indent=2)

    def list_profiles(self) -> list[str]:
        """列出所有已保存的配置文件名称。

        Returns:
            配置文件名列表（不含扩展名和路径），按字母排序。
        """
        if not os.path.isdir(self._profiles_dir):
            return []
        names: list[str] = []
        for entry in os.listdir(self._profiles_dir):
            if entry.endswith(".json"):
                names.append(entry[:-5])  # 去掉 .json
        return sorted(names)

    def delete_profile(self, name: str) -> None:
        """删除指定的配置文件。

        Args:
            name: 要删除的配置文件名称。

        Raises:
            FileNotFoundError: 配置文件不存在时抛出。
        """
        path = self._profile_path(self._profiles_dir, name)
        if not os.path.isfile(path):
            raise FileNotFoundError(f"配置文件不存在，无法删除: {path}")
        os.remove(path)

    @staticmethod
    def get_presets() -> dict[str, str]:
        """列出所有内置预设的名称及描述。

        Returns:
            字典，键为预设名称，值为描述文本。
        """
        return {name: profile.description for name, profile in PRESETS.items()}

    def clone_preset(self, preset_name: str, new_name: str) -> Profile:
        """基于内置预设创建新配置文件。

        Args:
            preset_name: 预设名称（必须存在于 PRESETS 中）。
            new_name: 新配置文件的名称。

        Returns:
            克隆得到的新 Profile 对象（已保存到文件）。

        Raises:
            ValueError: 预设名称不存在时抛出。
        """
        if preset_name not in PRESETS:
            available = ", ".join(PRESETS.keys())
            raise ValueError(
                f"预设 '{preset_name}' 不存在，可用预设: {available}"
            )
        new_profile = Profile(
            name=new_name,
            description=f"基于「{preset_name}」预设创建",
            contract_type=PRESETS[preset_name].contract_type,
            amount_keywords=list(PRESETS[preset_name].amount_keywords),
            number_patterns=list(PRESETS[preset_name].number_patterns),
            date_patterns=list(PRESETS[preset_name].date_patterns),
            risk_rules=dict(PRESETS[preset_name].risk_rules),
            comparison_thresholds=dict(PRESETS[preset_name].comparison_thresholds),
        )
        self.save_profile(new_name, new_profile)
        return new_profile

    def set_active_profile(self, name: str) -> None:
        """将指定配置文件设为当前活动配置。

        Args:
            name: 配置文件名称。

        Raises:
            FileNotFoundError: 配置文件不存在时抛出。
        """
        # 验证文件存在
        path = self._profile_path(self._profiles_dir, name)
        if not os.path.isfile(path):
            raise FileNotFoundError(f"配置文件不存在: {path}")
        with open(self._active_profile_file, "w", encoding="utf-8") as fh:
            fh.write(name)

    def get_active_profile(self) -> Profile | None:
        """获取当前活动配置并应用到 config.py。

        读取 .active_profile 文件中的名称，加载对应配置，并调用
        :func:`apply_profile` 将设置写入 config.py。

        Returns:
            当前活动的 Profile 对象，如果未设置则返回 None。
        """
        if not os.path.isfile(self._active_profile_file):
            return None
        with open(self._active_profile_file, "r", encoding="utf-8") as fh:
            name = fh.read().strip()
        if not name:
            return None
        try:
            profile = self.load_profile(name)
        except FileNotFoundError:
            return None
        apply_profile(profile)
        return profile


# ---------------------------------------------------------------------------
# 4. Profile → Config 映射函数
# ---------------------------------------------------------------------------

def apply_profile(profile: Profile) -> None:
    """将 Profile 的配置应用到 config.py 的 FIELD_CONFIG 和 COMPARATOR_CONFIG。

    此函数直接修改 config 模块中的全局配置字典，使得后续的字段抽取
    与比对流程使用指定 Profile 的参数。

    Args:
        profile: 要应用的 Profile 对象。
    """
    # --- 字段配置 ---
    if profile.amount_keywords:
        config.FIELD_CONFIG["amount_keywords"] = list(profile.amount_keywords)
    if profile.number_patterns:
        config.FIELD_CONFIG["number_patterns"] = list(profile.number_patterns)
    if profile.date_patterns:
        config.FIELD_CONFIG["date_patterns"] = list(profile.date_patterns)

    # --- 比对配置 ---
    thresholds = profile.comparison_thresholds
    if "number_tolerance" in thresholds:
        config.COMPARATOR_CONFIG["number_tolerance"] = thresholds["number_tolerance"]
    if "similarity_threshold" in thresholds:
        config.COMPARATOR_CONFIG["similarity_threshold"] = thresholds["similarity_threshold"]
    if "min_segment_length" in thresholds:
        config.COMPARATOR_CONFIG["min_segment_length"] = thresholds["min_segment_length"]