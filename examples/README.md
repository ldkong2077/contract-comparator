# Examples / 示例文件

本目录包含合同扫描件比对工具的 API 调用示例和配置模板。

## 目录结构

```
examples/
├── README.md                           # 本文件
├── profiles/                           # 示例行业预设
│   └── custom_profile.json
└── api/                                # API 调用示例
    ├── curl_examples.sh
    └── python_client.py
```

## 快速试用

### 方式一：CLI 对比

```bash
# 自行准备一份 Word 文档（.docx）和一份扫描件 PDF（.pdf），然后执行：
python main.py --word /path/to/your-contract.docx --pdf /path/to/your-scan.pdf --output ./output
```

### 方式二：API 对比 (curl)

参见 `examples/api/curl_examples.sh`

### 方式三：Python SDK

参见 `examples/api/python_client.py`

> **注意:** 示例文件中的金额、日期、公司名称等数据均为虚构。请使用自己的合同文件进行测试。
>
> 开源版不附带真实的合同样本文件。如有需要，可自行创建包含虚构条款的 Word/PDF 文件进行功能验证。
