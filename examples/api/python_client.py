#!/usr/bin/env python3
"""
合同扫描件比对工具 - Python 客户端示例
Contract Document Comparator - Python Client Example

使用前提: FastAPI 服务已启动 (默认端口 8080)
Usage: python python_client.py
"""

import os
import sys
import json
import time
from pathlib import Path
from typing import Optional, Dict, Any

try:
    import requests
except ImportError:
    print("请先安装 requests: pip install requests")
    sys.exit(1)


class ContractComparatorClient:
    """合同比对工具 API 客户端"""
    
    def __init__(self, base_url: str = "http://localhost:8080", api_key: str = None):
        """
        初始化客户端
        
        Args:
            base_url: API 服务地址
            api_key: API 密钥 (可选，不传则使用无认证模式)
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.session = requests.Session()
        
        if self.api_key:
            self.session.headers["X-API-Key"] = self.api_key
    
    def health_check(self) -> Dict[str, Any]:
        """
        健康检查
        
        Returns:
            服务状态信息
        """
        response = self.session.get(f"{self.base_url}/health")
        response.raise_for_status()
        return response.json()
    
    def generate_api_key(self, name: str = "client-key", role: str = "analyst", 
                         expires_in_days: int = 30) -> Dict[str, Any]:
        """
        生成 API Key
        
        Args:
            name: Key 名称
            role: 角色 (admin/analyst/viewer)
            expires_in_days: 过期天数
            
        Returns:
            包含 key 的信息
        """
        response = self.session.post(
            f"{self.base_url}/api/v1/auth/key",
            json={
                "name": name,
                "role": role,
                "expires_in_days": expires_in_days
            }
        )
        response.raise_for_status()
        return response.json()
    
    def compare_documents(self, word_file: str, pdf_file: str, 
                          profile: str = "general",
                          use_llm: bool = False,
                          model: str = None) -> Dict[str, Any]:
        """
        上传文档进行对比
        
        Args:
            word_file: Word 文档路径 (.docx)
            pdf_file: PDF 扫描件路径 (.pdf)
            profile: 行业预设 (general/construction/leasing/procurement/labor)
            use_llm: 是否启用 LLM 分析
            model: LLM 模型名称 (可选)
            
        Returns:
            对比任务信息
        """
        # 验证文件存在
        if not Path(word_file).exists():
            raise FileNotFoundError(f"Word 文件不存在: {word_file}")
        if not Path(pdf_file).exists():
            raise FileNotFoundError(f"PDF 文件不存在: {pdf_file}")
        
        # 准备文件上传
        with open(word_file, "rb") as wf, open(pdf_file, "rb") as pf:
            files = {
                "word_file": (
                    Path(word_file).name,
                    wf,
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                ),
                "pdf_file": (
                    Path(pdf_file).name,
                    pf,
                    "application/pdf"
                )
            }
            
            data = {
                "profile": profile,
                "use_llm": str(use_llm).lower()
            }
            
            if model:
                data["model"] = model
            
            response = self.session.post(
                f"{self.base_url}/api/v1/compare",
                files=files,
                data=data
            )
        
        response.raise_for_status()
        return response.json()
    
    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """
        获取任务状态
        
        Args:
            task_id: 任务 ID
            
        Returns:
            任务状态信息
        """
        response = self.session.get(f"{self.base_url}/api/v1/compare/{task_id}")
        response.raise_for_status()
        return response.json()
    
    def wait_for_completion(self, task_id: str, timeout: int = 300, 
                            poll_interval: int = 2) -> Dict[str, Any]:
        """
        等待任务完成
        
        Args:
            task_id: 任务 ID
            timeout: 超时时间 (秒)
            poll_interval: 轮询间隔 (秒)
            
        Returns:
            最终任务结果
        """
        start_time = time.time()
        
        while True:
            elapsed = time.time() - start_time
            if elapsed > timeout:
                raise TimeoutError(f"任务 {task_id} 超时 ({timeout}秒)")
            
            status = self.get_task_status(task_id)
            task_status = status.get("status", "unknown")
            
            print(f"  任务状态: {task_status} (已等待 {elapsed:.1f}秒)")
            
            if task_status == "completed":
                return status
            elif task_status == "failed":
                raise Exception(f"任务失败: {status.get('error', '未知错误')}")
            
            time.sleep(poll_interval)
    
    def get_profiles(self) -> list:
        """
        获取行业预设列表
        
        Returns:
            预设列表
        """
        response = self.session.get(f"{self.base_url}/api/v1/profiles")
        response.raise_for_status()
        return response.json()
    
    def export_result(self, task_id: str, format: str = "json", 
                      output_path: str = None) -> str:
        """
        导出对比结果
        
        Args:
            task_id: 任务 ID
            format: 导出格式 (txt/json/docx/xlsx/pdf/zip)
            output_path: 输出文件路径 (可选)
            
        Returns:
            导出的文件路径
        """
        valid_formats = ["txt", "json", "docx", "xlsx", "pdf", "zip"]
        if format not in valid_formats:
            raise ValueError(f"不支持的格式: {format}. 支持: {valid_formats}")
        
        response = self.session.get(
            f"{self.base_url}/api/v1/export/{task_id}",
            params={"format": format},
            stream=True
        )
        response.raise_for_status()
        
        # 确定输出路径
        if not output_path:
            output_path = f"comparison_result_{task_id[:8]}.{format}"
        
        # 保存文件
        with open(output_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        print(f"  导出完成: {output_path}")
        return output_path
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        获取系统指标 (需要 Admin 权限)
        
        Returns:
            系统指标
        """
        response = self.session.get(f"{self.base_url}/api/v1/metrics")
        response.raise_for_status()
        return response.json()


def main():
    """主函数 - 演示客户端用法"""
    
    # 配置
    base_url = os.getenv("API_BASE_URL", "http://localhost:8080")
    api_key = os.getenv("API_KEY")
    word_file = os.getenv("WORD_FILE", "./sample_contract.docx")
    pdf_file = os.getenv("PDF_FILE", "./sample_scan.pdf")
    
    print("=" * 60)
    print(" 合同比对工具 Python 客户端示例")
    print(" Contract Comparator Python Client Example")
    print("=" * 60)
    print()
    
    # 创建客户端
    client = ContractComparatorClient(base_url=base_url, api_key=api_key)
    
    # 1. 健康检查
    print("[1] 健康检查 / Health Check")
    try:
        health = client.health_check()
        print(f"  状态: {health.get('status', 'unknown')}")
        print(f"  版本: {health.get('version', 'unknown')}")
    except requests.RequestException as e:
        print(f"  错误: 无法连接到服务 ({e})")
        print("  请确保 FastAPI 服务已启动: uvicorn api_server:app --reload")
        return
    print()
    
    # 2. 获取行业预设
    print("[2] 行业预设 / Industry Profiles")
    try:
        profiles = client.get_profiles()
        print(f"  可用预设: {[p.get('name') for p in profiles]}")
    except Exception as e:
        print(f"  获取预设失败: {e}")
    print()
    
    # 3. 文件对比 (如果文件存在)
    print("[3] 文件对比 / Document Comparison")
    if Path(word_file).exists() and Path(pdf_file).exists():
        try:
            print(f"  Word: {word_file}")
            print(f"  PDF:  {pdf_file}")
            
            result = client.compare_documents(
                word_file=word_file,
                pdf_file=pdf_file,
                profile="general",
                use_llm=False
            )
            
            task_id = result.get("task_id")
            print(f"  任务已提交: {task_id}")
            
            # 等待完成
            print("  等待任务完成...")
            final_result = client.wait_for_completion(task_id, timeout=120)
            
            # 导出结果
            print("  导出对比结果...")
            output_file = client.export_result(task_id, format="json")
            print(f"  结果已保存: {output_file}")
            
        except Exception as e:
            print(f"  对比失败: {e}")
    else:
        print(f"  跳过: 未找到测试文件")
        print(f"  请设置环境变量指向实际文件:")
        print(f"    export WORD_FILE=./your_contract.docx")
        print(f"    export PDF_FILE=./your_scan.pdf")
    print()
    
    # 4. 系统指标
    print("[4] 系统指标 / System Metrics")
    try:
        metrics = client.get_metrics()
        print(f"  活跃任务: {metrics.get('active_tasks', 0)}")
        print(f"  总任务数: {metrics.get('total_tasks', 0)}")
    except Exception as e:
        print(f"  获取指标失败 (可能需要 Admin 权限): {e}")
    print()
    
    print("=" * 60)
    print(" 示例完成 / Example Complete")
    print("=" * 60)


if __name__ == "__main__":
    main()
