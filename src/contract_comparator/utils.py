"""
通用工具函数
"""
import os
import re


def validate_file(path: str, extensions: list[str]) -> bool:
    """
    验证文件是否存在且扩展名匹配
    
    Args:
        path: 文件路径
        extensions: 允许的扩展名列表（如 ['.pdf', '.docx']）
    
    Returns:
        是否有效
    """
    if not os.path.exists(path):
        print(f"[ERROR] 文件不存在: {path}")
        return False
    
    ext = os.path.splitext(path)[1].lower()
    if ext not in extensions:
        print(f"[ERROR] 不支持的文件格式: {ext}（支持: {', '.join(extensions)}）")
        return False
    
    return True


def clean_ocr_text(text: str) -> str:
    """
    清理 OCR 文本中的常见噪声
    
    Args:
        text: OCR 识别文本
    
    Returns:
        清理后的文本
    """
    # 去除多余空格（保留单个）
    text = re.sub(r' +', ' ', text)
    
    # 去除行首行尾空白
    text = text.strip()
    
    return text


def normalize_whitespace(text: str) -> str:
    """标准化空白字符"""
    # 将所有空白字符（包括全角空格）统一为半角空格
    text = text.replace('\u3000', ' ')  # 全角空格
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def extract_numbers_from_text(text: str) -> list[str]:
    """从文本中提取所有数字字符串"""
    return re.findall(r'\d{1,3}(?:,\d{3})*(?:\.\d+)?', text)


def ensure_output_dir(output_dir: str) -> str:
    """确保输出目录存在"""
    os.makedirs(output_dir, exist_ok=True)
    return output_dir
