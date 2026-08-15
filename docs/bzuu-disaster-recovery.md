# BZUU 官网爬虫 → ima 知识库：GitHub Actions 灾备迁移记录

> **事件时间**：2026-08-14
> **事件性质**：阿里云服务器 SSH 认证故障，业务紧急迁移至 GitHub Actions
> **当前状态**：✅ 已完成迁移，GitHub Actions 每日自动运行

---

## 1. 事件背景

### 1.1 原有架构
- **爬虫服务器**：阿里云 ECS（47.95.231.166:2222）
- **任务**：每日爬取 [亳州学院官网](https://www.bzuu.edu.cn) 新文章，导入腾讯 ima 知识库
- **技术栈**：Python 3 + BeautifulSoup + ima Open API + COS
- **数据**：1258 个附件、4213 个文章 URL 已导入 ima 知识库

### 1.2 故障发生
- 2026-08-14 下午，SSH 连接失败（`Permission denied`）
- ping 通（47ms）、TCP 握手正常、密钥被服务器接受（"Server accepts key"）
- 但最终认证失败，无法登录服务器
- 用户放弃阿里云工单排障，决定启用 GitHub Actions 灾备方案

---

## 2. 灾备方案设计（事前准备）

### 2.1 提前准备（故障前已完成）
早在部署初期，就在 GitHub 上创建了备份仓库：
- **仓库**：`gitfox-enter/bzuu-ima-importer`（私有）
- **内容**：爬虫脚本、导入脚本、进度文件、workflow 配置
- **进度文件**：`ima_import_progress.json`（296KB，含 4213 个已完成 URL）

### 2.2 迁移目标
| 项 | 服务器方案 | GitHub Actions 方案 |
|----|-----------|---------------------|
| 定时触发 | 服务器 cron `0 2 * * *` | Actions cron `0 18 * * *`（UTC，北京02:00） |
| 运行环境 | 阿里云 Ubuntu | ubuntu-latest runner |
| 密钥管理 | 服务器文件 | GitHub Secrets |
| 进度文件 | 服务器本地 | 提交回 GitHub 仓库 |

---

## 3. 迁移执行过程

### 3.1 第一步：检查备份仓库状态
```bash
# 检查仓库是否存在、代码是否最新
GET /repos/gitfox-enter/bzuu-ima-importer
# ✅ 仓库存在，最后一次推送为今天，代码最新
```

### 3.2 第二步：启用定时任务
```bash
# 将 ENABLE_DAILY 变量从 false 改为 true
PATCH /repos/gitfox-enter/bzuu-ima-importer/actions/variables/ENABLE_DAILY
{"name": "ENABLE_DAILY", "value": "true"}
# ✅ 验证 updated_at 已更新
```

### 3.3 第三步：验证 Secrets
```bash
# 检查 ima API 密钥是否还在
GET /repos/gitfox-enter/bzuu-ima-importer/actions/secrets/IMA_CLIENT_ID
GET /repos/gitfox-enter/bzuu-ima-importer/actions/secrets/IMA_API_KEY
# ✅ 两个 secrets 均存在
```

### 3.4 第四步：手动触发验证
```bash
POST /repos/gitfox-enter/bzuu-ima-importer/actions/workflows/daily-import.yml/dispatches
{"ref": "main"}
# ✅ HTTP 204，workflow 启动
```

### 3.5 第五步：确认运行成功
```
Run ID: 31783398023
Status: completed ✅
Conclusion: success ✅
耗时: 约 50 分钟（08:18 → 09:08）

关键日志：
[08:19:26] 已加载 4213 个已有 URL
[09:08:40] 爬取完成。新文章: 0 篇
[09:08:40] 无新文章，跳过导入
[09:08:40] 进度文件已提交回仓库
```

**验证结果**：
- ✅ 增量爬虫正常加载 4213 个已有 URL
- ✅ 全站爬取完成（0 篇新文章，说明服务器期间已导入全部内容）
- ✅ 进度文件自动提交回 GitHub 仓库

---

## 4. 当前架构（灾备后）

```
亳州学院官网 (bzuu.edu.cn)
        │
        ▼
GitHub Actions (每天 UTC 18:00 / 北京 02:00)
        │
        ├─ bzuu_crawl_incremental.py  ← 增量爬虫
        │        │
        │        └─ 新文章？→ ima import_urls API → ima知识库
        │
        ├─ ima_import_progress.json    ← 进度文件（自动提交回仓库）
        │
        └─ IMA_CLIENT_ID / IMA_API_KEY ← GitHub Secrets
```

## 5. 运维指南

### 5.1 手动触发
```bash
POST /repos/gitfox-enter/bzuu-ima-importer/actions/workflows/daily-import.yml/dispatches
{"ref": "main"}
```

### 5.2 暂停/恢复定时任务
- 暂停：`ENABLE_DAILY=false`
- 恢复：`ENABLE_DAILY=true`

### 5.3 查看运行日志
```bash
GET /repos/gitfox-enter/bzuu-ima-importer/actions/runs?per_page=5
```

### 5.4 服务器恢复后切换
1. 修复服务器 SSH 认证问题
2. 将进度文件同步到服务器
3. 设置 `ENABLE_DAILY=false`
4. 重新启用服务器 cron

---

## 6. 关键文件清单

| 文件 | 用途 |
|------|------|
| `bzuu_crawl_incremental.py` | 增量爬虫 + 导入主脚本 |
| `ima_import_progress.json` | 导入进度（4213 URL） |
| `main_attachments.json` | 主站附件清单 |
| `requirements.txt` | Python 依赖 |
| `.github/workflows/daily-import.yml` | 每日任务 workflow |
| `.github/workflows/test-ima.yml` | ima API 测试 workflow |

## 7. 经验总结

1. **备份要趁早**：进度文件（`ima_import_progress.json`）的存在是本次快速恢复的关键
2. **Secrets 独立**：API 密钥放在 GitHub Secrets 而非代码中，安全且可随时更新
3. **变量开关**：`ENABLE_DAILY` 变量实现了定时任务的远程开关，无需改代码
4. **增量设计**：爬虫基于进度文件做增量，服务器故障期间积压的数据也能在下次运行自动补齐
5. **验证先行**：先手动触发一次验证全链路，再依赖 cron 自动运行，避免半夜发现问题

---

*记录人：Operit AI*
*日期：2026-08-14*