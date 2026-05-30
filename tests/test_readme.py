"""
README 一致性测试 — 验证 README.md 无重复元素、无空引用、措辞准确
"""
import os
import re

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture
def readme_content():
    readme_path = os.path.join(PROJECT_ROOT, "README.md")
    with open(readme_path, "r", encoding="utf-8") as f:
        return f.read()


class TestReadmeBadges:
    """验证 badge 无重复"""

    def test_no_duplicate_badge_lines(self, readme_content):
        lines = readme_content.split("\n")
        badge_lines = [
            line.strip()
            for line in lines
            if "img.shields.io/badge" in line
        ]
        seen = set()
        duplicates = []
        for badge in badge_lines:
            if badge in seen:
                duplicates.append(badge)
            seen.add(badge)
        assert len(duplicates) == 0, f"Duplicate badge(s) found: {duplicates}"


class TestReadmeScreenshots:
    """验证无指向不存在图片的引用"""

    def test_no_broken_image_refs(self, readme_content):
        img_pattern = re.compile(r'<img\s+src="([^"]+)"')
        matches = img_pattern.findall(readme_content)

        broken = []
        for src in matches:
            if src.startswith("http"):
                continue
            full_path = os.path.join(PROJECT_ROOT, src)
            if not os.path.exists(full_path):
                broken.append(src)

        assert len(broken) == 0, f"Broken image references: {broken}"

    def test_no_screenshot_placeholder(self, readme_content):
        assert "截图待替换" not in readme_content, (
            "README still contains screenshot placeholder text '截图待替换'"
        )


class TestReadmeWording:
    """验证关键措辞准确"""

    def test_no_production_grade_api_claim(self, readme_content):
        assert "Production-grade" not in readme_content, (
            "README should not claim 'Production-grade' for local REST API"
        )
        assert "production-grade" not in readme_content.lower() or "production-grade rest api" not in readme_content.lower(), (
            "README should not claim 'production-grade' for REST API"
        )

    def test_fastapi_described_appropriately(self, readme_content):
        if "FastAPI" in readme_content and "REST" in readme_content:
            lines = readme_content.split("\n")
            for line in lines:
                if "FastAPI" in line and "REST" in line:
                    lower = line.lower()
                    assert "production-grade" not in lower, (
                        f"FastAPI line should not say 'production-grade': {line.strip()}"
                    )


class TestReadmeStructure:
    """验证 README 引用的关键文件存在"""

    def test_referenced_files_exist(self, readme_content):
        md_link_pattern = re.compile(r'\[.*?\]\(([^)]+\.md)\)')
        links = md_link_pattern.findall(readme_content)

        missing = []
        for link in links:
            if link.startswith("http"):
                continue
            full_path = os.path.join(PROJECT_ROOT, link)
            if not os.path.exists(full_path):
                missing.append(link)

        assert len(missing) == 0, f"Referenced markdown files missing: {missing}"

    def test_license_file_exists(self):
        assert os.path.exists(os.path.join(PROJECT_ROOT, "LICENSE")), "LICENSE file must exist"

    def test_security_md_exists(self):
        assert os.path.exists(os.path.join(PROJECT_ROOT, "SECURITY.md")), "SECURITY.md must exist"

    def test_contributing_md_exists(self):
        assert os.path.exists(os.path.join(PROJECT_ROOT, "CONTRIBUTING.md")), "CONTRIBUTING.md must exist"
