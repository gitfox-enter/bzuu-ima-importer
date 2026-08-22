# bzxy 内容导入 ima 知识库 — 维护技术文档

> 最后更新：2026-08-22
> 维护模式：**纯 GitHub Actions，不依赖任何服务器**

---

## 1. 项目概述

将亳州学院官网 (`www.bzuu.edu.cn`) 各栏目的文章、附件、图片自动导入至 ima 知识库 (`KB_ID: 8UWnCJWk0DlQ15ppsKOIeyNofz8ZBOJVt7e9Taeu7bg=`)，全流程通过 GitHub Actions 在 GitHub 基础设施上执行，**不依赖外部服务器**。

**仓库**: `gitfox-enter/bzuu-ima-importer` (主分支 `main`)

---

## 2. 系统架构

```
亳州学院官网 → GitHub Actions (抓取) → crawl_results_v5.json / main_articles.json
                                         ↓
                              GitHub Actions (导入) → ima 知识库 API
                                         ↓
                              进度文件写回 GitHub → 断点续传
```

### 核心数据流

| 数据文件 | 大小 | 用途 | 产生方式 |
|---|---|---|---|
| `crawl_results_v5.json` | ~42 MB | 4213 篇文章 + 1373 个附件的原始爬取数据 | `bzuu_crawl_incremental.py` 增量抓取写入 |
| `main_articles.json` | ~20 MB | 4213 篇文章的元数据（含 images 字段） | 从 crawl_results_v5 派生，作为图片导入的数据源 |
| `ima_import_progress.json` | ~296 KB | 导入进度记录，支持断点续传 | 各导入脚本运行时更新并写回仓库 |
| `ima_archive_progress.json` | 小型 | 归档进度记录 | `fix_missed_attachments.py` 运行时更新 |

---

## 3. GitHub Actions 工作流

### 3.1 工作流一览

| 工作流文件 | 触发方式 | 执行脚本 | 用途 | 超时 |
|---|---|---|---|---|
| `.github/workflows/daily-import.yml` | 每天 18:00 UTC + 手动触发 | `bzuu_crawl_incremental.py` → `bzuu_image_import.py` | 日常增量抓取 + 图片导入 | 60 分钟 |
| `.github/workflows/test-ima.yml` | 仅手动触发 | `test_ima_import.py` | ima API 连通性测试 | 10 分钟 |

> 注：image-import.yml、fix-attachments.yml、fix-images.yml 为已设计但尚未创建/已下线的工作流，当前实际文件仅 daily-import 与 test-ima 两个。

### 3.2 各工作流说明

#### daily-import.yml — 日常增量

- **每日定时**: UTC 18:00（北京时间次日 02:00）
- **手动触发**: `workflow_dispatch` 始终可用
- **前置条件**: 仓库 Variables 中 `ENABLE_DAILY=true` 才执行定时任务；手动触发不受影响
- **步骤**: ① 增量抓取官网新文章 → ② 图片导入新文章
- **进度回写**: `crawl_results_v5.json`、`main_articles.json`、`ima_import_progress.json`、`ima_archive_progress.json` 全部写回仓库

#### test-ima.yml — API 测试

- **触发**: 仅 `workflow_dispatch`
- **脚本**: `test_ima_import.py`
- **用途**: 验证 `IMA_CLIENT_ID` 和 `IMA_API_KEY` secrets 是否有效，ima API 是否可达

### 3.3 所有工作流的公共配置

| 配置项 | 类型 | 位置 | 说明 |
|---|---|---|---|
| `IMA_CLIENT_ID` | Secret | Settings → Secrets and variables → Actions → Secrets | ima API 客户端 ID |
| `IMA_API_KEY` | Secret | Settings → Secrets and variables → Actions → Secrets | ima API 密钥 |
| `ENABLE_DAILY` | Variable | Settings → Secrets and variables → Actions → Variables | `true` 时启用 daily-import 定时任务 |
| Git 用户 | 硬编码 | 各 workflow 中 `git config` | `gitfox-enter` / `gitfox-enter@users.noreply.github.com` |

---

## 4. 核心脚本说明

### 4.1 `ima_batch_import.py` — 通用导入脚本（核心依赖根）

**SHA**: `3858044559` | **大小**: 16136 字节 | **Commit**: `3838a4f3`

所有其他脚本的依赖根。其他脚本通过 `sys.path.insert(0, ...)` + `from ima_batch_import import ...` 复用其核心函数。

#### 核心配置（硬编码）

- `KB_ID`: `8UWnCJWk0DlQ15ppsKOIeyNofz8ZBOJVt7e9Taeu7bg=`
- `BASE_URL`: ima API 基础 URL
- `FOLDERS`: 14 个栏目 → folder_id 映射
- `MEDIA_TYPE`: 扩展名 → media_type 映射
- `CONTENT_TYPE`: 扩展名 → MIME 类型映射

#### 栏目映射

| 栏目名 | folder_id |
|---|---|
| 学校要闻 | 7702b959-e92e-4c45-9797-35922a62734c |
| 校园快讯 | 8262f9f1-1d38-447f-b186-447e50a18f3c |
| 通知公告 | 481d4d3a-7465-441a-9066-00d420c21b31 |
| 亳院先锋 | 758c6a0f-91b2-4303-9953-10b9c6e49a7f |
| 学术动态 | a49a35a1-8a39-4bca-a9a5-7f28697eb321 |
| 人才引进 | fb8610e5-a714-4311-833a-83c646d6c1e6 |
| 学习环境 | 93c094d6-b3b9-4600-82e6-b5d985a3f17b |
| 媒体聚焦 | 4e5715f0-802e-42ee-9125-200705533623 |
| 食宿环境 | 4a229169-e60e-485f-8447-807a65e35558 |
| 国际教育 | 8153284d-2554-415a-9f8c-9b7211527c4c |
| 影像亳院 | 18b00b7a-8e1d-4187-a7c2-1037b8281169 |
| 招生就业 | 0d8c09f5-103b-48be-9055-09f8929a06d9 |
| 亳文化研究 | d71786e9-1d42-4543-904a-d8938f75c443 |
| 信息公开 | b29f4e8f-c0d1-4b89-992b-4c4c84a79295 |

#### 支持的调用模式

```bash
python3 ima_batch_import.py            # 默认模式：从 crawl_results_v5 导入文章+附件
python3 ima_batch_import.py images     # 图片补导模式：从 main_articles 补导所有图片
python3 ima_batch_import.py test       # 测试模式：测试 API 连通性
```

#### 环境变量

| 变量 | 说明 | 默认值 |
|---|---|---|
| `IMA_CLIENT_ID` | ima API 客户端 ID | 回退读取 `~/.config/ima/client_id` 文件 |
| `IMA_API_KEY` | ima API 密钥 | 回退读取 `~/.config/ima/api_key` 文件 |
| `CRAWL_DATA` | 爬取数据文件路径 | `/root/crawl_results_v5.json`（GitHub Actions 中应改为仓库内路径） |
| `MAIN_ARTICLES_FILE` | 文章数据文件路径 | `main_articles.json` |
| `IMPORT_PROGRESS_FILE` | 进度文件路径 | `ima_import_progress.json` |

#### 图片导入逻辑 (`import_article_images` 函数)

1. 从 `main_articles.json` 读取文章
2. 遍历 `images_done` 进度，跳过已完成的
3. 对每篇有 `images` 字段的文章：
   - 验证图片 URL 可访问
   - 调用 `create_media` API 获取 COS 上传地址
   - 上传至腾讯 COS
   - 调用 `add_knowledge` 将图片写入 ima
4. 更新 `images_done` 进度并写回仓库

### 4.2 `ima_att_helpers.py` — 附件提取公共模块

**SHA**: `7483728d` | **大小**: 6302 字节 | **Commit**: `7483728d`

#### 修复内容

旧版只匹配 `<a href="...">` 传统附件链接，**无法捕获 WebPlus CMS 的 `wp_pdf_player` 嵌入式 PDF**。新增四类正则：

| 正则变量 | 匹配内容 | 用途 |
|---|---|---|
| `PDFSRC_RE` | `pdfsrc="/..."` 属性 | 直接匹配嵌入式 PDF 的 pdfsrc 路径 |
| `SWSRC_RE` | `swsrc="/..."` 属性 | 匹配 flash 播放器备份路径 |
| `SUDYFILE_RE` | `sudyfile-attr="{title:...}"` | 提取附件标题元数据 |
| `WP_PDF_BLOCK_RE` | `<div class="wp_pdf_player" ...>` 容器 | 兜底匹配整个容器，扫描容器内所有附件路径 |
| `EMBED_EXT_RE` | `/xxx.{pdf,doc,docx,ppt,pptx,xls,xlsx,zip,rar}` | 容器内附件路径匹配 |

#### 核心函数

- `find_article_attachments(url, html=None, timeout=15)` — 主入口，支持传入预取 HTML 或直接抓取
- `import_article_attachments(art, progress, articles_file, dry_run=False)` — 高层函数，被 `fix_missed_attachments.py` 调用

### 4.3 `fix_missed_attachments.py` — 附件补导脚本

**SHA**: `73c3b493` | **大小**: 6326 字节 | **Commit**: `3838a4f3`

#### 执行流程

1. 读取 `crawl_results_v5.json`（路径由 `CRAWL_DATA` 指定）
2. 遍历 4213 篇文章，扫描 HTML 中是否包含 `wp_pdf_player`/`pdfsrc`
3. 对 94 篇匹配文章：
   - 跳过已在 `ima_import_progress.json` 中成功的
   - 调用 `ima_att_helpers.import_article_attachments` 重新提取并导入
4. 更新进度文件写回仓库

#### 参数

| 参数 | 说明 |
|---|---|
| `--dry-run` | 仅打印将执行的操作，不做实际导入 |
| `--limit=N` | 限制处理前 N 篇（调试用） |

### 4.4 `bzuu_image_import.py` — 旧版图片导入脚本

**大小**: 9007 字节 | 独立脚本，由 `daily-import.yml` 调用。

> 注：新版图片导入已集成到 `ima_batch_import.py images`，但旧版 workflow 仍使用此脚本进行日常增量图片导入。

### 4.5 `bzuu_crawl_incremental.py` — 增量抓取脚本

由 `daily-import.yml` 调用，从亳州学院官网各栏目增量抓取新文章。

### 4.6 `test_ima_import.py` — API 测试脚本

由 `test-ima.yml` 调用，验证 ima API 连通性。

---

## 5. 依赖说明

### `requirements.txt`

```text
requests>=2.20
beautifulsoup4>=4.12
lxml>=5.0
cos-python-sdk-v5>=1.9
```

### GitHub Actions 运行环境

- 操作系统: Ubuntu Latest（`ubuntu-latest`）
- Python: 3.11
- 额外系统包: `unrar`（附件补导需要，用于解压 .rar 附件）

---

## 6. 故障排查

### 6.1 workflow 运行失败

| 症状 | 可能原因 | 排查步骤 |
|---|---|---|
| 所有 workflow 都报认证错误 | `IMA_CLIENT_ID` / `IMA_API_KEY` secrets 未设置或过期 | 运行 `test-ima.yml` 确认 secrets 有效性 |
| 附件补导下载失败 | 官网附件 URL 404 | 查看日志中的 404 URL，确认官网链接是否仍有效 |
| 图片补导超时 | 单篇文章图片过多 | 进度文件已保存，重跑即可从断点继续 |
| git push 失败 | 仓库权限或冲突 | 检查日志中的 git 错误信息 |
| 进度文件未写回 | `git diff --cached --quiet` 无差异 | 正常情况，说明脚本运行时没有新进度需要提交 |

### 6.2 常见问题

**Q: 如何手动触发补导？**| A: 在 GitHub 仓库 → Actions 页面 → 选择对应 workflow → 点 "Run workflow" → 点 "Run workflow" 确认。

**Q: 补导可以中断吗？**| A: 可以。进度文件已写回仓库，下次重跑会从断点继续。

**Q: 图片补导会不会重复导入？**| A: 不会。`images_done` 字段记录已导入的文章，跳过已完成的。

**Q: 附件补导会不会重复导入？**| A: 不会。`ima_archive_progress.json` 和 `ima_import_progress.json` 记录已导入的文章和附件。

---

## 7. 安全说明

- `IMA_CLIENT_ID` 和 `IMA_API_KEY` 为 GitHub Secrets，不会出现在仓库代码或日志中
- 进度文件包含已导入内容的记录，但不包含 API 密钥
- 旧版 `docs/fix-att-missed.md` 中曾包含 SSH 服务器同步命令，该方案已弃用，请直接删除
- 任何需要执行代码的操作都通过 GitHub Actions 完成，不需要也不应该连接任何外部服务器

---

## 8. 维护清单

日常维护仅需关注 GitHub 仓库：

1. **检查 workflow 运行状态**: 打开 Actions 页面，确认 daily-import 每日运行正常
2. **补充执行补导**: 如发现有遗漏内容，手动触发对应的 fix workflow
3. **更新 secrets**: 如 ima API 密钥轮换，更新 GitHub Secrets
4. **更新依赖**: 如 `requirements.txt` 有更新，重新运行 workflow 验证
5. **清理旧文档**: 删除 `docs/fix-att-missed.md` 中过时的服务器同步内容（已由本文档替代）
