# 亳州学院官网 → ima 知识库 自动导入

[![GitHub Actions (daily-import)](https://github.com/gitfox-enter/bzuu-ima-importer/actions/workflows/daily-import.yml/badge.svg)](https://github.com/gitfox-enter/bzuu-ima-importer/actions/workflows/daily-import.yml)
[![GitHub Actions (test-ima)](https://github.com/gitfox-enter/bzuu-ima-importer/actions/workflows/test-ima.yml/badge.svg)](https://github.com/gitfox-enter/bzuu-ima-importer/actions/workflows/test-ima.yml)

自动抓取亳州学院官网（www.bzuu.edu.cn）的最新文章、附件和图片，通过 ima Open API 批量导入到 ima 知识库对应文件夹中。

## 系统架构

本项目采用**纯 GitHub Actions 运行模式**，不依赖任何外部服务器。

```
┌─────────────────────────────────────────────────────────────────────┐
│                     GitHub Actions 工作流体系                        │
│                                                                     │
│  daily-import.yml  →  增量爬取 + 导入 ima 知识库（每日定时）         │
│  test-ima.yml      →  ima API 连通性测试                            │
│                                                                     │
│  注：image-import、fix-attachments、fix-images 为历史工作流设计，    │
│  当前实际运行仅 daily-import 和 test-ima 两个工作流。               │
└─────────────────────────────────────────────────────────────────────┘
```

## 爬取范围

| 类别 | 范围 |
|------|------|
| 主站导航 | 学院概况、机构设置、招生就业、人才引进、网络课堂（含子栏目） |
| 快捷栏目 | 12 个快捷栏目（新闻、通知、学术活动等） |
| 子站 | 招生就业子站、国际教育、亳文化研究、信息公开 |

## 配置

### GitHub Secrets

| Secret | 说明 |
|--------|------|
| IMA_CLIENT_ID | ima openapi client_id |
| IMA_API_KEY | ima openapi api_key |

### 栏目映射配置

编辑 `sites_to_folders.yaml`（根目录），配置网站栏目 URL 到 ima 文件夹的映射：

```yaml
# 格式：
https://www.bzuu.edu.cn/xxx/: "folder_id_xxx"
```

当前共 14 个栏目映射，详见 [docs/MAINTENANCE.md](docs/MAINTENANCE.md)。

## 快速开始

1. **Fork** 本仓库
2. 在 GitHub Secrets 中设置 `IMA_CLIENT_ID` 和 `IMA_API_KEY`
3. 手动触发 `test-ima` 工作流验证 API 连通性
4. 手动触发 `daily-import` 工作流（带 `dry_run` 参数）验证爬取
5. 确认无误后，启用定时任务

## 手动触发

| 工作流 | 触发路径 | 可选参数 |
|--------|----------|----------|
| daily-import | Actions → 每日抓取导入 | dry_run（boolean） |
| test-ima | Actions → 测试 ima API | 无 |

## 定时任务

| 工作流 | 定时 | 说明 |
|--------|------|------|
| daily-import | 每日 14:00 UTC（北京时间 22:00） | 增量爬取 + 导入 |

## 文件说明

### 核心脚本

| 文件 | 说明 |
|------|------|
| bzuu_crawl_incremental.py | 增量爬取脚本：主站导航 + 快捷栏目 + 子站三级爬取 |
| ima_batch_import.py | 批量导入脚本：调用 ima import_urls API |
| ima_archive_import.py | 压缩包处理脚本 |
| ima_att_helpers.py | 附件提取公共模块（5 类正则匹配） |
| ima_image_import.py | 图片导入脚本（旧版） |

### 模板

| 文件 | 说明 |
|------|------|
| ima_import_template.md | 高校官网→ima 知识库全流程导入模板（8 阶段检查表） |

### 文档

| 文件 | 说明 |
|------|------|
| docs/MAINTENANCE.md | 维护手册（工作流说明、栏目映射、故障排查、维护清单） |
| docs/bzuu-disaster-recovery.md | 灾难恢复指南 |
| docs/fix-att-missed.md | 附件修复遗漏记录 |

### 数据文件

| 文件 | 说明 |
|------|------|
| crawl_results_v5.json | 爬取结果数据（约 42 MB） |
| main_articles.json | 主站文章列表（约 20 MB） |
| ima_import_progress.json | 导入进度记录（约 296 KB） |
| crawl_results_incremental.json | 增量爬取结果 |

## 技术栈

- **语言**: Python 3
- **爬虫**: urllib（纯标准库，无外部 HTTP 依赖）
- **解析**: BeautifulSoup
- **API**: ima Open API（import_urls 端点）
- **自动化**: GitHub Actions（2 个工作流）
- **配置**: YAML 文件

## 相关项目

- [wy-media-crawler](https://github.com/gitfox-enter/wy-media-crawler) — 网易文创资源矩阵 → ima 知识库导入（同技术栈，更简洁的代码结构）
- [RSSForge](https://github.com/gitfox-enter/RSSForge) — RSS 聚合器，支持 ima 知识库集成