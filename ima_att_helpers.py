#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""附件处理公共模块：从文章页提取附件链接并补导到ima知识库
供增量脚本(bzuu_crawl_incremental.py)调用，处理新文章的附件
"""
import json, os, re, sys, time
import urllib.request
from urllib.parse import urljoin

# 复用 ima_batch_import 的导入函数
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ima_batch_import import download_attachment, call_api, KB_ID, FOLDERS, MEDIA_TYPE, import_attachment

PROGRESS_FILE = os.environ.get("IMPORT_PROGRESS_FILE", "ima_import_progress.json")
ARCHIVE_PROGRESS_FILE = os.environ.get("ARCHIVE_PROGRESS_FILE", "ima_archive_progress.json")
EXTS = ("pdf", "doc", "docx", "xls", "xlsx", "zip", "rar")


def log(msg):
    print("[附件] " + msg, flush=True)


def find_article_attachments(url, timeout=15):
    """获取文章页面，提取附件真实链接列表（绝对URL）"""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            html = r.read().decode(errors="replace")
    except Exception as e:
        log("获取页面失败 %s: %s" % (url, e))
        return []
    atts = []
    for m in re.finditer(r"href=\\?[\"\x27]([^\"\x27]*?\.(?:%s))[\"\x27]" % "|".join(EXTS), html, re.I):
        href = m.group(1)
        if href.startswith("javascript") or "sudyfile" in href.lower():
            continue
        full = urljoin(url, href)
        full = full.split("?")[0]
        atts.append(full)
    # 去重
    return list(dict.fromkeys(atts))


def load_progress():
    with open(PROGRESS_FILE) as f:
        return json.load(f)


def save_progress(prog):
    with open(PROGRESS_FILE, "w") as f:
        json.dump(prog, f, ensure_ascii=False, indent=2)


def load_archive_progress():
    try:
        with open(ARCHIVE_PROGRESS_FILE) as f:
            return json.load(f)
    except Exception:
        return {"archives_done": {}, "files_done": []}


def save_archive_progress(arch):
    with open(ARCHIVE_PROGRESS_FILE, "w") as f:
        json.dump(arch, f, ensure_ascii=False, indent=2)


def column_to_folder(column):
    """栏目名转 folder_id"""
    folder_id = FOLDERS.get(column, KB_ID)
    if folder_id == KB_ID:
        for k in FOLDERS:
            if k in column:
                folder_id = FOLDERS[k]
                break
    return folder_id


def import_article_attachments(article, prog=None, arch=None):
    """导入一篇文章的所有附件，返回(成功数, 失败数, 跳过数)"""
    url = article.get("url", "")
    column = article.get("column", "未分类")
    if not url:
        return 0, 0, 0
    atts = find_article_attachments(url)
    if not atts:
        return 0, 0, 0
    if prog is None:
        prog = load_progress()
    if arch is None:
        arch = load_archive_progress()
    atts_done = set(prog.get("atts_done", []))
    arch_done = set(arch.get("archives_done", {}).keys())
    files_done = set(arch.get("files_done", []))
    folder_id = column_to_folder(column)

    ok = fail = skip = 0
    for att_url in atts:
        ext = att_url.rsplit(".", 1)[-1].lower() if "." in att_url else ""
        if ext not in EXTS:
            continue
        # 压缩包走归档逻辑（简单模式：直接作为附件无法上传，跳过并记录）
        if ext in ("zip", "rar"):
            if att_url in arch_done or att_url in files_done:
                skip += 1
                continue
            log("压缩包需手动处理: %s (来自 %s)" % (att_url, url))
            skip += 1
            continue
        if att_url in atts_done:
            skip += 1
            continue
        fname = os.path.basename(att_url)
        att = {"url": att_url, "name": fname, "column": column}
        try:
            mid = import_attachment(att, folder_id)
            if mid:
                prog.setdefault("atts_done", []).append(att_url)
                ok += 1
                log("✅ 附件导入: %s" % fname)
            else:
                fail += 1
                log("❌ 附件导入失败: %s" % fname)
        except Exception as e:
            fail += 1
            log("❌ 附件异常: %s -> %s" % (fname, e))
        time.sleep(0.2)
    save_progress(prog)
    return ok, fail, skip


if __name__ == "__main__":
    # 命令行直接测试
    import sys
    art = {"url": sys.argv[1], "column": sys.argv[2] if len(sys.argv) > 2 else "通知公告"}
    ok, fail, skip = import_article_attachments(art)
    print("成功:%d 失败:%d 跳过:%d" % (ok, fail, skip))
