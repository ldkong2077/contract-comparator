# 域名与邮箱配置指南 / Domain & Email Setup Guide

## 概述

项目已统一使用 `info@numboxhub.com` 作为所有联系邮箱。

## 当前配置的邮箱地址

| 用途 | 邮箱 | 使用位置 |
|------|------|----------|
| 综合咨询 | info@numboxhub.com | README.md, SECURITY.md, pyproject.toml |
| 安全漏洞报告 | info@numboxhub.com | SECURITY.md, CODE_OF_CONDUCT.md |
| 团队联系 | info@numboxhub.com | CONTRIBUTING_zh.md |

## 域名配置（可选）

如需使用独立域名邮箱（如 `team@contract-comparator.dev`），可按以下步骤操作：

### 步骤一：注册域名

- 推荐注册商：Namecheap、Cloudflare、GoDaddy
- 域名：contract-comparator.dev

### 步骤二：配置邮箱

- 使用 Google Workspace 或 Zoho Mail 创建企业邮箱
- 或使用域名转发服务（如 Mailgun、SendGrid）

### 步骤三：更新文档

更新以下文件中的邮箱地址：

- [ ] `SECURITY.md` - 安全报告邮箱
- [ ] `README.md` - 联系方式
- [ ] `pyproject.toml` - 作者邮箱
- [ ] `.github/CODE_OF_CONDUCT.md` - 联系方式

### 步骤四：验证

- [ ] 发送测试邮件确认邮箱可达
- [ ] 更新 GitHub 仓库的联系方式

## 域名注册后检查清单

- [ ] 更新所有文档中的邮箱地址
- [ ] 配置 SPF/DKIM/DMARC 记录
- [ ] 设置邮箱自动回复（可选）
- [ ] 更新 GitHub 仓库设置
- [ ] 测试所有邮箱地址的可达性

---

*此文档创建于 2026-05-30，用于指导域名和邮箱配置。*
*邮箱已于 2026-05-30 统一为 info@numboxhub.com。*
