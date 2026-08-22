# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [v4] - 当前版本

### Added

- `ima_att_helpers.py` — 附件提取公共模块（5 类正则匹配，支持 WebPlus PDF 嵌入式附件）
- `fix_missed_attachments.py` — 附件补导脚本
- `bzuu_image_import.py` — 旧版图片导入脚本（由 daily-import.yml 调用）
- `docs/archive/` — 一次性过程报告归档

### Changed

- `ima_batch_import.py` 重构为依赖根模块，各脚本复用其核心函数
- `daily-import.yml` 工作流从 5 个精简为 2 个实际运行文件

## [v3]

### Added

- `ima_archive_import.py` — 压缩包处理脚本
- `bzuu_crawl_incremental.py` — 二级/三级子站爬取
- `docs/MAINTENANCE.md` — 完整维护手册

## [v2]

### Added

- 14 个栏目完整映射（主站 + 子站）
- 附件导入支持（`ima_batch_import.py` 增强）
- 图片导入（COS 上传 + add_knowledge）

## [v1]

### Added

- 初始版本：主站文章爬取 + ima import_urls 批量导入
- 基础 YAML 配置
