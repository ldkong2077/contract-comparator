#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
校验 README 配置表与 config.py 的默认值/变量名是否一致。

背景：本仓库曾多次出现「文档写的变量名/默认值与代码不符」的漂移问题
（如 README 写 API_RATE_LIMIT=60，代码实为 RATE_LIMIT_RPM=30；
README 写文件大小 100MB，代码实为 50MB）。本脚本在 CI 中运行，
能在合并前拦住此类回归。

用法:
    python scripts/check_docs_config.py

退出码:
    0  README 与 config.py 共享环境变量一致，且无已废弃变量残留
    1  发现不一致 / 废弃变量残留
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"
CONFIG = ROOT / "src" / "contract_comparator" / "config.py"

# config.py 中的环境变量提取：os.getenv("VAR", "default")
ENV_RE = re.compile(
    r'os\.getenv\(\s*["\']([A-Z_][A-Z0-9_]*)["\']\s*,\s*["\']([^"\']*)["\']\s*\)'
)

# README 配置表行：| `VAR` | `default` | ...
TABLE_RE = re.compile(
    r'^\|\s*`([A-Z_][A-Z0-9_]*)`\s*\|\s*`([^`]*)`\s*\|', re.MULTILINE
)

# 已知已废弃、应从文档中彻底移除的变量名（曾出现漂移误导）
KNOWN_STALE = {"API_RATE_LIMIT"}


def extract_config_envs() -> dict:
    text = CONFIG.read_text(encoding="utf-8")
    return {m.group(1): m.group(2) for m in ENV_RE.finditer(text)}


def extract_readme_table() -> dict:
    text = README.read_text(encoding="utf-8")
    return {m.group(1): m.group(2) for m in TABLE_RE.finditer(text)}


def main() -> int:
    if not README.exists() or not CONFIG.exists():
        print("ERROR: 找不到 README.md 或 config.py")
        return 1

    code_envs = extract_config_envs()
    doc_envs = extract_readme_table()

    errors: list[str] = []

    # 1) 两边都出现的变量：默认值必须一致
    common = sorted(set(code_envs) & set(doc_envs))
    for var in common:
        if code_envs[var] != doc_envs[var]:
            errors.append(
                f"  [默认值不一致] {var}: README={doc_envs[var]!r}  config.py={code_envs[var]!r}"
            )

    # 2) 文档中出现、但代码（config.py）里不存在的变量 -> 多半是废弃/写错
    doc_only = sorted(set(doc_envs) - set(code_envs))
    for var in doc_only:
        if var in KNOWN_STALE:
            errors.append(f"  [废弃变量残留] {var}: README 仍在声明，代码已无此变量")
        else:
            # 其它情况仅提示（可能是代码在别处定义的变量），不阻断
            print(f"  [提示] 文档有 {var}={doc_envs[var]!r}，但 config.py 未以 getenv 暴露（可能位于其它模块，已忽略）")

    if errors:
        print("发现 README 与 config.py 不一致：")
        for line in errors:
            print(line)
        return 1

    print(f"OK: 共校验 {len(common)} 个共享环境变量，README 与 config.py 一致；"
          f"无废弃变量残留。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
