# 高校官网 → ima知识库 全流程导入操作模板 v1.0

> **用途**：新接一个学校官网（或类似内容型网站）时，按本模板从零完成"爬取 → 解析分类 → 导入ima知识库 → 增量更新 → 验收"全流程。
> **定位**：流程操作模板（非通用爬虫工具）。每次新项目需按模板改写脚本参数。
> **适用对象**：AI助手本人（能看懂、能记住、能按步骤执行）。
> **存储**：本文件双份保存（记忆库 + 服务器 /root/）。

---

## 0. 开工前必读（10分钟）

### 0.1 项目关键参数清单（每个项目必填）
| 参数 | 例（亳州学院） | 新项目填写 |
|------|--------------|-----------|
| 目标站点 | www.bzuu.edu.cn | |
| 知识库ID | 8UWnCJWk0DlQ15ppsKOIeyNofz8ZBOJVt7e9Taeu7bg= | |
| 服务器 | root@47.95.231.166:2222 | |
| 主栏目列表 | 学校要闻/校园快讯/通知公告/学术动态... | |
| 子站列表 | 招生就业/国际教育/亳文化研究/信息公开 | |
| 目录映射 | 栏目名 → folder_xxx | |
| 进度文件 | /root/ima_import_progress.json | |

### 0.2 架构认知（先理解再动手）
```
官网HTML页面
   │
   ├─ 文章列表页(list.htm) ──→ 文章详情页(page.htm)
   │                              ├─ 正文 ──→ ima知识库(import_urls 或 手动)
   │                              └─ 附件(pdf/doc/xls/zip) ──→ 两条链路:
   │                                   ├─ 普通附件: create_media→COS→add_knowledge
   │                                   └─ 压缩包: 下载→解压→逐文件上传
   │
   └─ 栏目结构 ──→ 目录映射(FOLDERS) ──→ 文章归入对应folder
```
**⚠️ 最重要的认知：附件有两条完全独立的导入链路，压缩包必须走归档链路。**

---

## 1. 阶段一：爬虫（全量抓取）

### 1.1 流程检查表
- [ ] ① 分析站点结构：导航、快捷栏目、子站（是否有独立域名/路径前缀）
- [ ] ② 找文章列表页规律：`/栏目ID/list.htm`，确认分页规则
- [ ] ③ 找文章详情页规律：`/栏目ID/年份/月份/c文章IDa数字/page.htm`
- [ ] ④ 编写爬虫脚本（模板见 §8.1），抓取字段: url/title/column/content
- [ ] ⑤ 输出 crawl_results.json，**统计总数并抽查10条URL有效性**
- [ ] ⑥ 确认子站页面结构（附件往往藏在子站！）

### 1.2 踩坑提醒
- **子站 ≠ 主站**：招生就业(zzxx)、国际教育(gjjyxy)等子站可能有独立的列表页结构，需单独抓
- **列表页可能只有部分文章**：老文章可能不再出现在列表第1页，需翻页或用栏目归档页
- **页面是动态加载的**？先用 curl 看是否有静态HTML，没有则需换方案

---

## 2. 阶段二：解析与分类

### 2.1 流程检查表
- [ ] ① 解析文章详情页：标题(title)、正文(content)、栏目(column)
- [ ] ② 建立 栏目→文件夹 映射（在ima知识库建好对应folder）
- [ ] ③ 将文章按栏目归组，准备批量导入
- [ ] ④ 输出结构化 JSON：`crawl_results.json`（articles: [{url,title,column,content}]）

### 2.2 常用命令
```bash
# 从页面提取PDF真实地址（sudyfile系统常见）
curl -s "文章URL" | grep -oiP 'href="[^"]*\.(pdf|doc|docx|xls|xlsx|zip|rar)[^"]*"' | head
# URL相对路径转绝对: 前缀 https://域名
```

---

## 3. 阶段三：导入ima知识库（核心，三线并行）

### 3.1 三条导入链路（必须分开走！）
| 链路 | 内容 | 脚本 | 进度文件 |
|------|------|------|---------|
| ① 文章 | 正文 | ima_batch_import.py (mode=articles) | articles_done |
| ② 附件 | pdf/doc/docx/xls/xlsx | ima_batch_import.py (mode=attachments) | atts_done |
| ③ 压缩包 | zip/rar | ima_archive_import.py | archives_done + files_done |

### 3.2 检查表
- [ ] ① 文章批量导入（import_urls API，每批≤10个URL）
- [ ] ② 附件批量导入（create_media→COS→add_knowledge）
- [ ] ③ 压缩包解压导入（unzip/unrar→逐文件create_media）
- [ ] ④ **子站附件单独扫描补导**（见 §3.3，本模板最重要的新增步骤！）
- [ ] ⑤ 每100条打印进度，确认无批量失败

### 3.3 ⚠️ 子站附件扫描补导（必做，防遗漏）
**为什么必做**：`import_urls` API **只导入正文，不解析页面内附件**。主站附件走附件链路没问题，但子站文章如果也走 import_urls，其附件会被系统性遗漏。

```bash
# 步骤1: 扫描所有子站文章，提取页面内附件链接，与的进度比对
python3 /root/check_subsite_attachments.py   # 参考脚本见 §8.4
# 步骤2: 将未导入附件加入附件导入队列（复用 §3.2②链路）
python3 /root/ima_subsite_att_import.py      # 参考脚本见 §8.5
# 步骤3: 压缩包走归档链路
# 步骤4: 重试失败项（附件下载偶发超时，先重试再判死）
```

### 3.4 API 速查
| API | 用途 | 关键参数 |
|-----|------|---------|
| /import_urls | 导入文章正文 | knowledge_base_id, folder_id, urls[] |
| /create_media | 创建媒体（拿COS凭证） | file_name, file_size, content_type, knowledge_base_id, file_ext |
| /add_knowledge | 加入知识库 | media_type, media_id, title, knowledge_base_id, folder_id, file_info |
| COS put_object | 实际上传 | Bucket, Body, Key, ContentType |

**MEDIA_TYPE 映射**：pdf=1, doc/docx=3, ppt/pptx=4, xls/xlsx/csv=5, md=7, png/jpg/jpeg/webp=9, txt=13, mp3/m4a/wav/aac=15。**不含 zip/rar**（这就是为什么压缩包必须走单独链路）。

---

## 4. 阶段四：增量更新（cron）

### 4.1 检查表
- [ ] ① 编写增量脚本：加载已有URL集合 → 爬列表页 → 只收集**不在集合中**的新URL → import_urls导入 → 追加附件补导
- [ ] ② 写 cron：`0 2 * * * cd /root && python3 /root/xxx_incremental.py >> /root/xxx_incremental.log 2>&1`
- [ ] ③ 验证：手动跑一次，确认"新文章: 0 篇"或数量正确
- [ ] ④ **增量脚本必须包含附件补导逻辑**（新文章的附件也要导入，见 §8.6 ima_att_helpers）

### 4.2 局限性（已确认的边界）
- cron 只抓**新发布文章**，不追踪已有文章内容修改（用户已确认不需要）
- cron 不检测已有文章新增附件（如需此能力需额外增强，当前版本不做）
- 增量脚本在全量数据存在时运行，首次全量后生成 `crawl_results.json` 作为基线

---

## 5. 阶段五：验收

### 5.1 统计验收
```bash
# 汇总各进度文件
python3 -c "
import json
p = json.load(open('/root/ima_import_progress.json'))
a = json.load(open('/root/ima_archive_progress.json'))
print('文章:', len(p.get('articles_done',[])))
print('附件:', len(p.get('atts_done',[])))
print('归档包:', len(a.get('archives_done',{})))
print('解压文件:', len(a.get('files_done',[])))
"
```

### 5.2 抽查验收（关键）
- [ ] ① 随机挑3篇文章，在ima搜索标题，确认能检索到
- [ ] ② **挑1篇含附件的文章，搜索附件关键词（如"新生入学"）确认附件能被检索到** ← 这次用户发现的坑就在这里
- [ ] ③ 确认失败清单可解释（源站404/被删/0字节）

### 5.3 失败附件处置四步法
```
① 重试1次（若超时，多试）
② 验证源站：curl -sI URL → 看 HTTP 状态码和 Content-Length
   - 404 → 源站删除，不可恢复
   - 200 但 Content-Length: 0 → 源站清空，不可恢复
   - 200 有内容 → 换UA/Referer重试
③ 压缩包 → 检查是否已在 archives_done（可能不是真失败）
④ 记录到最终报告，给出不可恢复原因
```

---

## 6. 踩坑经验库（每个项目必读）

| # | 坑 | 现象 | 解法 |
|:-:|:--|:-----|:-----|
| 1 | **import_urls 不导附件** | 子站文章附件全部缺失 | 子站也必须走附件导入链路（§3.3） |
| 2 | **MEDIA_TYPE 无 zip/rar** | 压缩包导入报错/跳过 | 压缩包走独立归档链路（§3.1③） |
| 3 | **heredoc 引号转义** | 脚本里中文/引号反复报错 | 本地写脚本 → 管道传到服务器执行 |
| 4 | **附件下载偶发超时** | 一次失败就放弃 | 先重试再判死（§5.3①） |
| 5 | **源站删除≠下载问题** | Content-Length:0 或 404 | 用 curl -sI 验证，区分可恢复/不可恢复 |
| 6 | **本地/tmp 与服务器/tmp 不同** | ssh 管道 cat 不到文件 | 用 /sdcard/Download/ 或 read_file 读内容重写 |
| 7 | **子站结构独立** | 主站爬虫不覆盖子站 | 子站单独爬取+单独附件扫描 |
| 8 | **http/https 双版本附件URL** | atts_done 出现重复 | 附件URL归一化（统一https）后再比对 |

---

## 7. 速查检查表（最终版，每项目打印使用）

```
□ 爬虫: 主站+子站全量URL，抽查10条
□ 解析: 栏目映射完成，JSON结构化输出
□ 导入-文章: import_urls 批导入，0失败或失败可解释
□ 导入-附件: create_media→COS→add_knowledge
□ 导入-压缩包: 归档链路独立进度
□ 导入-子站附件: 扫描+补导（防遗漏关键步骤）
□ 增量: cron每日跑，含附件补导
□ 验收: 统计+抽查3文章+抽查1附件+失败清单可解释
□ 报告: 生成 stepX_report.md 存档
□ 清理: 删除临时脚本，保持服务器整洁
```

---

## 8. 脚本模板索引（详见服务器 /root/）

| 文件 | 用途 | 对应阶段 |
|------|------|---------|
| ima_batch_import.py | 文章+附件批量导入 | §3.1①② |
| ima_archive_import.py | 压缩包解压导入 | §3.1③ |
| ima_att_helpers.py | 附件提取+补导公共模块 | §3.3/§4 |
| check_subsite_attachments.py | 子站附件扫描 | §3.3 |
| ima_subsite_att_import.py | 子站附件补导 | §3.3 |
| bzuu_crawl_incremental.py | 增量爬取+导入 | §4 |

> **下一个项目的执行路径**：读本模板 → 替换 §0.1 参数 → 按 §7 检查表逐项执行 → 踩坑时查 §6 经验库。