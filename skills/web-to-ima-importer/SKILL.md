---
name: web-to-ima-importer
description: >
  爬取目标网站内容并导入腾讯 ima 知识库的全流程技能。当用户说"把网站内容导入ima""爬取官网导入知识库""网站→ima""网站内容迁移到ima"或类似需求时触发。
  也适用于用户说"服务器连不上了，用GitHub Actions备份""灾备方案""GitHub Actions接管爬虫""增量爬取导入ima"等场景。
  这是一个From-Scratch技能，从零开始爬取一个网站内容并导入 ima 知识库，包括：网站结构分析、爬虫脚本编写、ima API对接、附件上传、压缩包解压、增量更新、GitHub Actions灾备部署。
---

# 网站内容 → ima知识库 全流程导入技能

## 1. 适用范围

本技能适用于以下场景：
- **新项目**：从零开始爬取一个目标网站，把文章和附件导入 ima 知识库
- **增量更新**：已有进度文件，只爬取新文章并导入
- **灾备恢复**：服务器宕机，用 GitHub Actions 接替爬虫任务
- **日常运维**：每天自动爬取新文章，导入 ima 知识库

## 2. 核心架构

```
目标网站
   │
   ├─ 文章列表页 ──→ 文章详情页
   │                    ├─ 正文 ──→ ima import_urls API
   │                    └─ 附件(pdf/doc/xls/zip/rar)
   │                         ├─ 普通附件: create_media→COS→add_knowledge
   │                         └─ 压缩包: 下载→解压→逐文件上传
   │
   └─ 栏目结构 ──→ 文件夹映射 ──→ 文章归入对应folder
```

**关键认知**：附件有两条完全独立的导入链路，压缩包必须走归档链路。

## 3. 前置准备

### 3.1 必须获取的参数
| 参数 | 说明 | 获取方式 |
|------|------|----------|
| 目标站点URL | 如 `https://www.example.edu.cn` | 用户提供 |
| ima 知识库ID | `knowledge_base_id` | ima 开放平台后台 |
| ima Client ID | `client_id` | ima 开放平台申请 |
| ima API Key | `api_key` | ima 开放平台申请 |
| 栏目→文件夹映射 | 每个栏目对应一个 folder_id | 先在 ima 建好文件夹 |

### 3.2 ima API 端点
- BASE: `https://ima.qq.com/openapi/wiki/v1`
- 导入文章: `POST /import_urls`（批量导入文章URL，正文自动解析）
- 创建媒体: `POST /create_media`（获取 COS 上传凭证）
- 添加知识: `POST /add_knowledge`（上传媒体文件到知识库文件夹）
- 检查重复: `POST /check_repeated_names`（检查文件名是否已存在）
- 列出知识库: `POST /get_knowledge_list`（列出知识库文件列表）
- 搜索知识: `POST /search_knowledge`（搜索知识库内容）

### 3.3 COS 上传流程
```
create_media → 获取 upload_url + file_id → PUT upload_url → add_knowledge(file_id, folder_id)
```

## 4. 阶段一：网站结构分析

### 4.1 分析步骤
1. **访问首页**，观察导航栏栏目结构（主栏目、子栏目、快捷栏目）
2. **找文章列表页**规律：`/栏目ID/list.htm` 或类似模式
3. **找文章详情页**规律：`/栏目ID/年份/月份/c文章IDa数字/page.htm`
4. **确认分页规则**：`/栏目ID/list_页码.htm`
5. **确认子站结构**：部分栏目可能有独立子域名或路径前缀
6. **确认附件链接**：页面内附件链接的格式（如 sudyfile 系统）

### 4.2 输出
- 栏目列表（含ID、名称、URL）
- 子站列表（含路径前缀）
- 列表页/详情页URL模式
- 附件链接模式

## 5. 阶段二：编写爬虫脚本

### 5.1 基础爬虫模板

```python
#!/usr/bin/env python3
"""增量爬虫脚本模板"""

import requests
import json
import re
import os
from urllib.parse import urljoin
from bs4 import BeautifulSoup

BASE_URL = "https://www.example.edu.cn"  # 替换为实际目标
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; crawler/1.0)"}

# 栏目配置
COLUMNS = {
    "column_name": {
        "id": "栏目ID数字",
        "folder_id": "ima知识库folder_id",
        "list_url": f"{BASE_URL}/栏目ID/list.htm"
    },
}

# 进度文件
PROGRESS_FILE = "import_progress.json"

def load_progress():
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE) as f:
            return json.load(f)
    return {"urls_done": [], "atts_done": [], "archives_done": []}

def save_progress(progress):
    with open(PROGRESS_FILE, 'w') as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)

def crawl_article_list(column_url, max_pages=50):
    """爬取文章列表页，返回文章URL列表"""
    articles = []
    for page in range(1, max_pages + 1):
        list_url = re.sub(r'list\.htm$', f'list_{page}.htm', column_url)
        if page == 1:
            list_url = column_url
        resp = requests.get(list_url, headers=HEADERS, timeout=10)
        if resp.status_code != 200:
            break
        soup = BeautifulSoup(resp.text, 'lxml')
        # 根据实际页面结构调整选择器
        links = soup.select('a[href*="/page.htm"]')
        if not links:
            break
        for a in links:
            url = urljoin(BASE_URL, a['href'])
            if url not in articles:
                articles.append(url)
    return articles

def crawl_article_detail(url):
    """爬取文章详情页，返回标题、正文、附件链接"""
    resp = requests.get(url, headers=HEADERS, timeout=10)
    soup = BeautifulSoup(resp.text, 'lxml')
    title = soup.select_one('.article-title, h1').text.strip()
    content = str(soup.select_one('.article-content, .content'))
    # 提取附件链接
    attachments = []
    for a in soup.select('a[href*=".pdf"], a[href*=".doc"], a[href*=".zip"], a[href*=".rar"]'):
        attachments.append(urljoin(BASE_URL, a['href']))
    return {"url": url, "title": title, "content": content, "attachments": attachments}

def main():
    progress = load_progress()
    done_urls = set(progress.get("urls_done", []))
    
    new_articles = []
    for col_name, col in COLUMNS.items():
        urls = crawl_article_list(col["list_url"])
        for url in urls:
            if url not in done_urls:
                detail = crawl_article_detail(url)
                detail["column"] = col_name
                detail["folder_id"] = col["folder_id"]
                new_articles.append(detail)
    
    print(f"新文章: {len(new_articles)} 篇")
    # 保存结果供后续导入
    result = {"new_articles": new_articles, "progress": progress}
    with open("crawl_results.json", "w") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
```

### 5.2 注意事项
- 第一页 URL 可能没有 `_1` 后缀，需单独处理
- 设置合理的 User-Agent 和超时
- 注意反爬机制（频率限制、cookie等）
- 子站如果有独立域名，需单独处理
- 附件链接可能是相对路径，需要补充为绝对URL

## 6. 阶段三：导入 ima 知识库

### 6.1 文章导入（import_urls API）

```python
def import_articles(articles, client_id, api_key, knowledge_base_id):
    """批量导入文章到ima知识库"""
    base_url = "https://ima.qq.com/openapi/wiki/v1"
    headers = {
        "X-Client-Id": client_id,
        "X-Api-Key": api_key,
        "Content-Type": "application/json"
    }
    
    # 每批最多10个URL
    batch_size = 10
    for i in range(0, len(articles), batch_size):
        batch = articles[i:i+batch_size]
        payload = {
            "knowledge_base_id": knowledge_base_id,
            "urls": [a["url"] for a in batch],
            "folder_id": batch[0]["folder_id"]
        }
        resp = requests.post(f"{base_url}/import_urls", json=payload, headers=headers)
        if resp.status_code == 200:
            print(f"批次 {i//batch_size + 1} 导入成功")
        else:
            print(f"批次 {i//batch_size + 1} 失败: {resp.text}")
```

### 6.2 附件上传（create_media → COS → add_knowledge）

```python
def upload_attachment(file_path, file_name, folder_id, client_id, api_key, knowledge_base_id):
    """上传附件到ima知识库"""
    base_url = "https://ima.qq.com/openapi/wiki/v1"
    headers = {
        "X-Client-Id": client_id,
        "X-Api-Key": api_key,
        "Content-Type": "application/json"
    }
    
    # Step 1: 获取 COS 上传凭证
    media_resp = requests.post(f"{base_url}/create_media", json={
        "knowledge_base_id": knowledge_base_id,
        "file_name": file_name,
        "folder_id": folder_id
    }, headers=headers)
    media_data = media_resp.json()
    upload_url = media_data["data"]["upload_url"]
    file_id = media_data["data"]["file_id"]
    
    # Step 2: 上传文件到 COS
    with open(file_path, 'rb') as f:
        requests.put(upload_url, data=f)
    
    # Step 3: 添加到知识库
    add_resp = requests.post(f"{base_url}/add_knowledge", json={
        "knowledge_base_id": knowledge_base_id,
        "file_id": file_id,
        "folder_id": folder_id
    }, headers=headers)
    return add_resp.json()
```

### 6.3 压缩包处理（归档链路）

```python
import zipfile
import os
import subprocess

def process_archive(archive_path, folder_id, client_id, api_key, knowledge_base_id):
    """解压压缩包并逐文件上传"""
    ext = os.path.splitext(archive_path)[1].lower()
    extract_dir = os.path.splitext(archive_path)[0]
    
    if ext == '.zip':
        with zipfile.ZipFile(archive_path, 'r') as zf:
            zf.extractall(extract_dir)
    elif ext == '.rar':
        subprocess.run(['unrar', 'x', archive_path, extract_dir + '/'])
    
    # 逐个上传解压后的文件
    for root, dirs, files in os.walk(extract_dir):
        for f in files:
            file_path = os.path.join(root, f)
            upload_attachment(file_path, f, folder_id, client_id, api_key, knowledge_base_id)
```

### 6.4 进度管理

使用 `import_progress.json` 跟踪进度：
```json
{
  "urls_done": ["https://.../page.htm", ...],
  "atts_done": ["https://.../file.pdf", ...],
  "archives_done": ["https://.../archive.zip", ...],
  "files_done_from_archive": ["file1.pdf", "file2.pdf", ...]
}
```

每次导入前检查是否已处理，避免重复导入。

## 7. 阶段四：GitHub Actions 灾备方案

### 7.1 创建 GitHub 仓库
- 仓库名：建议 `{项目名}-ima-importer`（如 `bzuu-ima-importer`）
- 包含：爬虫脚本、导入脚本、进度文件、依赖文件

### 7.2 创建 workflow 文件

`.github/workflows/daily-import.yml`：
```yaml
name: Daily Import
on:
  workflow_dispatch:
  schedule:
    - cron: "0 18 * * *"  # UTC 18:00 = 北京 02:00
permissions:
  contents: write
jobs:
  import:
    runs-on: ubuntu-latest
    timeout-minutes: 180
    if: ${{ github.event_name == 'workflow_dispatch' || vars.ENABLE_DAILY == 'true' }}
    steps:
      - name: Checkout
        uses: actions/checkout@v4
      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Install deps
        run: |
          sudo apt-get update
          sudo apt-get install -y unrar unzip
          pip install -r requirements.txt
      - name: Run incremental import
        env:
          IMA_CLIENT_ID: ${{ secrets.IMA_CLIENT_ID }}
          IMA_API_KEY: ${{ secrets.IMA_API_KEY }}
        run: python bzuu_crawl_incremental.py 2>&1
      - name: Commit progress back
        run: |
          git config user.name "your-username"
          git config user.email "your-username@users.noreply.github.com"
          git add -A
          if ! git diff --cached --quiet; then
            git commit -m "auto: daily progress update $(date +%Y-%m-%d)"
            git push origin main
          fi
```

### 7.3 设置 GitHub Secrets
- `IMA_CLIENT_ID`：ima Client ID
- `IMA_API_KEY`：ima API Key

### 7.4 设置 GitHub Variables
- `ENABLE_DAILY`：`true`（启用定时任务）| `false`（暂停定时任务）

### 7.5 灾备切换流程
当服务器宕机时：
1. 设 `ENABLE_DAILY=true` 启用定时任务
2. 手动触发一次 workflow 验证链路
3. 确认正常运行后，告知用户 GitHub Actions 已接管

## 8. 阶段五：增量更新

### 8.1 增量爬虫逻辑
```python
def incremental_crawl():
    progress = load_progress()
    done_urls = set(progress.get("urls_done", []))
    
    for col_name, col in COLUMNS.items():
        urls = crawl_article_list(col["list_url"])
        new_urls = [u for u in urls if u not in done_urls]
        
        if new_urls:
            for url in new_urls:
                # 爬取新文章详情
                detail = crawl_article_detail(url)
                # 导入到ima
                import_article_to_ima(detail)
                # 更新进度
                progress["urls_done"].append(url)
                save_progress(progress)
```

### 8.2 定时执行
- GitHub Actions cron：每天 UTC 18:00（北京凌晨）
- 或服务器 cron：`0 2 * * * cd /root/project && python3 bzuu_crawl_incremental.py`

## 9. 常见问题

### 9.1 附件上传失败
- 检查文件大小是否超过 ima 限制
- 检查 COS 上传凭证是否过期
- 检查网络连接是否稳定
- 实现重试机制（最多3次）

### 9.2 文章解析失败
- 检查页面结构是否变化（选择器失效）
- 检查页面是否需要登录或验证码
- 检查页面是否动态加载（需用 Selenium/Playwright）

### 9.3 API 限流
- 遇到 429 时自动递增等待
- 批次间添加随机延迟
- 最多重试 6 次

### 9.4 服务器 SSH 连接失败
- 检查密钥权限（600）和目录权限（700）
- 确认 SSH 端口和配置
- 确认服务器安全组规则
- 应急方案：启用 GitHub Actions 灾备

## 10. 相关资源
- ima 开放平台文档：参考 ima 官方 API 文档
- 本技能配套的完整项目示例：`gitfox-enter/bzuu-ima-importer`