# 附件遗漏修复说明（wp_pdf_player/pdfsrc）

## 问题

旧版 `ima_att_helpers.py` 的 `find_article_attachments` 只匹配 `<a href="...">` 传统附件链接，
完全无法捕获 WebPlus CMS 平台的 `wp_pdf_player` 嵌入式 PDF：

```html
<div class="wp_pdf_player" pdfsrc="/_upload/article/files/...pdf" swsrc="/...swf" sudyfile-attr="{title:...}">
```

结果：所有使用 wp_pdf_player 的文章附件均未被导入 ima，表现为「文章内容正常但附件缺失」。

## 扫描结果（2026-08-18）

- 存量 v5 数据：4213 篇文章，1373 个附件
- 使用 wp_pdf_player/pdfsrc 的文章：94 篇
- 旧提取器已捕获的附件：0 篇（100% 漏抓）

## 修复

### 1. `ima_att_helpers.py` 提取器重构
- 保留传统 `<a href="...">` 附件提取（向后兼容）
- 新增 `pdfsrc` 属性正则匹配
- 新增 `wp_pdf_player` div 容器兜底：扫描容器内所有 `/xxx.{pdf,docx,...}` 路径
- `find_article_attachments(url, html=None, timeout=15)` 新增 `html` 参数，支持直接传 HTML

### 2. `fix_missed_attachments.py` 补导脚本

用法（在服务器 /root 下）：
```bash
python3 fix_missed_attachments.py --dry-run   # 预览
python3 fix_missed_attachments.py --limit=10  # 试跑
python3 fix_missed_attachments.py             # 全部补导
```

### 3. 服务器同步（SSH 恢复后）
```bash
scp -P 2222 -i /root/.ssh/id_ed25519 ima_att_helpers.py fix_missed_attachments.py root@47.95.231.166:/root/
```

## 验收用例

- URL: `https://www.bzuu.edu.cn/gjjyxy/2026/0725/c2950a110940/page.htm`
- 标题：亳州学院2026年秋季国际学生入学指南
- 附件应包含：`/_upload/article/files/28/8a/95e9620449f09fe70c6849fe0e50/20b5c50a-f860-4862-858b-185ed7cfaec2.pdf`