#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""补导脚本：修复后对所有 wp_pdf_player/pdfsrc 嵌入附件的文章重新抓取并导入
用法：
  python3 fix_missed_attachments.py [--limit N] [--dry-run]
默认从 /root/crawl_results_v5.json 读取存量数据，重新访问文章页提取附件并导入 ima。
"""
import json, os, sys, time, re
from urllib.parse import urljoin

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ima_att_helpers as att_mod
from ima_att_helpers import (
    find_article_attachments,
    import_article_attachments,
    load_progress,
    load_archive_progress,
    save_progress,
    save_archive_progress,
    log,
)

DEFAULT_DATA = os.environ.get("CRAWL_DATA", "/root/crawl_results_v5.json")
MISSED_OUT = os.environ.get("MISSED_REPORT", "missed_attachments_report.json")
PROG_DEFAULT = os.environ.get("IMPORT_PROGRESS_FILE", "ima_import_progress.json")


def load_data(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def scan_missed(data):
    """从存量数据中找出所有 wp_pdf_player/pdfsrc 嵌入附件的文章
    返回 [{url, title, column, html, missing_atts}]
    """
    arts = data.get("articles", [])
    atts = data.get("attachments", [])
    amap = {}
    for a in atts:
        amap.setdefault(a.get("article_url"), []).append(a["url"])
    missed = []
    # pdfsrc 正则（与 att_mod.PDFSRC_RE 保持一致）
    pdfsrc_re = re.compile(r'pdfsrc\s*=\s*["\']([^"\']+\.(?:pdf|docx?|xlsx?|pptx?|zip|rar))["\']', re.I)
    wp_block_re = re.compile(r'<div[^>]*wp_pdf_player[^>]*>(.*?)</div>', re.I | re.DOTALL)
    embed_ext_re = re.compile(r'/(?:[^/]+\.)?(pdf|doc|docx|xls|xlsx|ppt|pptx|zip|rar)(?:\?[^/"\'\s>]*)?', re.I)
    for a in arts:
        h = a.get("content_html", "") or a.get("html", "")
        if not h:
            continue
        if "wp_pdf_player" not in h and "pdfsrc" not in h:
            continue
        expected = set()
        for m in pdfsrc_re.finditer(h):
            p = m.group(1)
            expected.add(p if p.startswith("http") else urljoin(a["url"], p))
        for blk in wp_block_re.finditer(h):
            inner = blk.group(1)
            # 提取 div 内的 /xxx.pdf 路径
            for path_match in re.finditer(r'(/[^"\']+\.(?:pdf|docx?|xlsx?|pptx?|zip|rar)(?:\?[^"\']*)?)', inner, re.I):
                p = path_match.group(1).split("?")[0]
                expected.add(p if p.startswith("http") else urljoin(a["url"], p))
        recorded = set(amap.get(a["url"], []))
        unc = [p for p in expected if p not in recorded]
        if unc:
            missed.append({
                "url": a["url"],
                "title": a.get("title", ""),
                "column": a.get("column", "未分类"),
                "html": h,
                "missing_atts": unc,
            })
    return missed


def main():
    data_path = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else DEFAULT_DATA
    limit = None
    dry_run = False
    for arg in sys.argv[1:]:
        if arg.startswith("--limit="):
            limit = int(arg.split("=", 1)[1])
        elif arg == "--dry-run":
            dry_run = True

    if not os.path.exists(data_path):
        print(f"[fix] 数据文件不存在: {data_path}")
        print("[fix] 使用 set CRAWL_DATA=/path/to/crawl_results_v5.json 或传入参数")
        sys.exit(1)

    print(f"[fix] 加载存量数据: {data_path}")
    data = load_data(data_path)
    missed = scan_missed(data)
    print(f"[fix] 发现需补导文章: {len(missed)} 篇")
    if limit:
        missed = missed[:limit]
        print(f"[fix] --limit={limit}，仅处理前 {limit} 篇")

    report = {
        "total": len(missed),
        "imported": 0,
        "failed": 0,
        "skipped": 0,
        "re_fetch_needed": 0,
        "dry_run": dry_run,
        "details": [],
    }

    prog = load_progress() if os.path.exists(PROG_DEFAULT) else {"atts_done": []}
    arch = load_archive_progress() if os.path.exists(
        os.environ.get("ARCHIVE_PROGRESS_FILE", "ima_archive_progress.json")) else {"archives_done": {}, "files_done": []}

    for i, item in enumerate(missed):
        url = item["url"]
        title = item.get("title", "")
        column = item.get("column", "未分类")
        html = item.get("html", "")
        log(f"[{i+1}/{len(missed)}] {title[:60]} | {column}")

        # 用存量 html 尝试提取
        atts = find_article_attachments(url, html=html)
        if not atts and html:
            # 存量 html 中没抓到（可能 html 字段被截断/只有文本），尝试在线重抓
            log("  存量 html 未提取到附件，尝试在线重抓...")
            atts = find_article_attachments(url)
            if atts:
                report["re_fetch_needed"] += 1
            else:
                log("  ❌ 在线重抓也未提取到附件，跳过")
                report["failed"] += 1
                report["details"].append({"url": url, "title": title, "status": "failed"})
                continue

        if not atts:
            log("  无附件可导入，跳过")
            report["skipped"] += 1
            report["details"].append({"url": url, "title": title, "status": "skip-no-atts"})
            continue

        if dry_run:
            for a in atts:
                log(f"  [dry-run] 将导入: {a}")
            report["imported"] += len(atts)
            continue

        art = {"url": url, "title": title, "column": column, "html": html}
        ok, fail, skip = import_article_attachments(art, prog=prog, arch=arch)
        report["imported"] += ok
        report["failed"] += fail
        report["skipped"] += skip
        report["details"].append({"url": url, "title": title, "ok": ok, "fail": fail, "skip": skip})

        # 限速（避免 ima API 429）
        time.sleep(0.5)

    save_progress(prog)
    save_archive_progress(arch)

    with open(MISSED_OUT, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"[fix] 完成。总 {report['total']} 篇，导入 {report['imported']}，失败 {report['failed']}，跳过 {report['skipped']}，需重抓 {report['re_fetch_needed']}")
    print(f"[fix] 报告写入: {MISSED_OUT}")


if __name__ == "__main__":
    main()