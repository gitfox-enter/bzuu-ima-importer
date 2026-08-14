#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""BZUU增量爬取+自动导入ima知识库(v1)"""
import json, os, sys, time, re
import urllib.request, urllib.error
from urllib.parse import urljoin
from bs4 import BeautifulSoup

BASE_URL = "https://www.bzuu.edu.cn"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
RESULTS_FILE = os.environ.get("RESULTS_FILE", "crawl_results_v5.json")
INCREMENTAL_RESULTS = os.environ.get("INCREMENTAL_RESULTS", "crawl_results_incremental.json")
LOG_FILE = os.environ.get("LOG_FILE", "crawl_incremental.log")
KB_ID = "8UWnCJWk0DlQ15ppsKOIeyNofz8ZBOJVt7e9Taeu7bg="
BASE = "https://ima.qq.com/openapi/wiki/v1"
CLIENT_ID = os.environ.get("IMA_CLIENT_ID") or open(os.path.expanduser("~/.config/ima/client_id")).read().strip()
API_KEY = os.environ.get("IMA_API_KEY") or open(os.path.expanduser("~/.config/ima/api_key")).read().strip()
FOLDERS = {
    "学校要闻": "folder_7493563487102220",
    "校园快讯": "folder_7493563491295428",
    "通知公告": "folder_7493563495490231",
    "亳院先锋": "folder_7493563495492675",
    "学术动态": "folder_7493563499705585",
    "人才引进": "folder_7493563503900179",
    "学习环境": "folder_7493563508096422",
    "媒体聚焦": "folder_7493563508073754",
    "食宿环境": "folder_7493563512267920",
    "影像亳院": "folder_7493563516483017",
    "招生就业": "folder_7493563516461742",
    "亳文化研究": "folder_7493563520677002",
    "国际教育": "folder_7493563520677165",
    "信息公开": "folder_7493563524871631",
}

def log(msg):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    line = "[%s] %s" % (ts, msg)
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
    except Exception:
        pass

def fetch_page(url, timeout=20, retries=3):
    for attempt in range(retries + 1):
        try:
            import requests
            r = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
            r.encoding = "utf-8"
            return r.text, r.status_code
        except Exception as e:
            if attempt < retries:
                time.sleep(2)
            else:
                return None, 0
    return None, 0

def is_error_page(html):
    if not html:
        return True
    soup = BeautifulSoup(html, "lxml")
    title = soup.find("title")
    if title and ("提示信息" in title.get_text() or "没有找到" in title.get_text()):
        return True
    return False

def extract_article_title(html):
    soup = BeautifulSoup(html, "lxml")
    h1 = soup.find("h1")
    if h1:
        title = h1.get_text(strip=True)
        if title:
            return title
    title_tag = soup.find("title")
    if title_tag:
        title = title_tag.get_text(strip=True)
        title = re.sub(r"\s*[-_|]\s*亳州学院.*$", "", title).strip()
        if title and title != "提示信息":
            return title
    return ""

def extract_single_page_content(html):
    soup = BeautifulSoup(html, "lxml")
    for cls in ["wp_articlecontent", "entry", "read", "contant", "con"]:
        div = soup.find("div", class_=cls)
        if div:
            return str(div)
    return ""

def extract_article_links_from_list(html, base_url):
    articles = []
    soup = BeautifulSoup(html, "lxml")
    news_list = soup.find("ul", class_=lambda c: c and "news_list" in c)
    if not news_list:
        return articles
    for li in news_list.find_all("li", class_=lambda c: c and "news" in c):
        a = li.find("a", href=True)
        if not a:
            continue
        href = a["href"].strip()
        if "page.htm" not in href and "show.htm" not in href:
            continue
        abs_url = urljoin(base_url, href)
        title_div = li.find("div", class_=lambda c: c and "news_title" in c)
        title = title_div.get_text(strip=True) if title_div else a.get_text(strip=True)
        date_str = ""
        year_span = li.find("span", class_=lambda c: c and "news_year" in c)
        day_span = li.find("span", class_=lambda c: c and "news_day" in c)
        if year_span:
            year = year_span.get_text(strip=True)
            day = day_span.get_text(strip=True) if day_span else ""
            date_str = "%s-%s" % (year, day)
        articles.append({"url": abs_url, "title": title, "date": date_str})
    return articles

def get_next_page_url(html, base_url):
    if not html:
        return None
    soup = BeautifulSoup(html, "lxml")
    for a in soup.find_all("a", href=True):
        text = a.get_text(strip=True)
        href = a["href"].strip()
        if ("下一页" in text or "下页" in text or ">>" in text) and href and href != "javascript:void(0)":
            return urljoin(base_url, href)
    return None

def crawl_article_page(url, column_name):
    html, status = fetch_page(url, timeout=15)
    if not html or is_error_page(html):
        return None
    title = extract_article_title(html)
    if not title:
        title = url.split("/")[-2]
    content_html = extract_single_page_content(html)
    content_text = ""
    images = []
    if content_html:
        content_soup = BeautifulSoup(content_html, "lxml")
        content_text = content_soup.get_text(separator="\n", strip=True)
        for img in content_soup.find_all("img", src=True):
            images.append(urljoin(url, img["src"]))
        if len(content_text) < 50 and images:
            content_text = "[图片文章] 正文为图片，共%d张。图片链接：%s" % (len(images), " ".join(images[:5]))
    return {
        "url": url,
        "title": title,
        "content": content_text[:10000],
        "content_html": content_html[:50000] if content_html else "",
        "column": column_name,
        "images": images,
    }

def crawl_column(column_name, list_url, visited, existing_urls, new_articles, max_pages=100):
    if list_url in visited:
        return 0
    page_num = 0
    new_count = 0
    current_url = list_url
    while current_url and page_num < max_pages:
        if current_url in visited:
            break
        visited.add(current_url)
        page_num += 1
        html, status = fetch_page(current_url)
        if not html:
            break
        soup = BeautifulSoup(html, "lxml")
        news_list = soup.find("ul", class_=lambda c: c and "news_list" in c)
        if not news_list:
            if not is_error_page(html):
                content_html = extract_single_page_content(html)
                if content_html:
                    content_soup = BeautifulSoup(content_html, "lxml")
                    content_text = content_soup.get_text(separator="\n", strip=True)
                    if len(content_text) > 50:
                        title = extract_article_title(html) or column_name
                        if current_url not in existing_urls:
                            new_articles.append({
                                "url": current_url, "title": title,
                                "content": content_text[:10000], "column": column_name,
                                "content_html": content_html[:50000], "images": []
                            })
                            new_count += 1
            break
        articles = extract_article_links_from_list(html, current_url)
        for art in articles:
            art_url = art["url"]
            if art_url in visited:
                continue
            visited.add(art_url)
            if art_url in existing_urls:
                continue
            article_data = crawl_article_page(art_url, column_name)
            if article_data:
                if not article_data["title"]:
                    if art["title"]:
                        article_data["title"] = art["title"]
                    else:
                        continue
                new_articles.append(article_data)
                new_count += 1
                log("  NEW: %s..." % article_data["title"][:60])
            time.sleep(0.3)
        next_url = get_next_page_url(html, current_url)
        if next_url and next_url != current_url:
            current_url = next_url
        else:
            break
    return new_count

def call_api(path, payload, timeout=120):
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "ima-openapi-clientid": CLIENT_ID,
            "ima-openapi-apikey": API_KEY,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")[:500]
        return {"code": e.code, "error": body}
    except Exception as e:
        return {"error": str(e)}

def import_new_articles(new_articles):
    if not new_articles:
        log("没有新文章需要导入")
        return
    by_column = {}
    for art in new_articles:
        col = art["column"]
        matched = None
        for key in FOLDERS:
            if col.startswith(key):
                matched = key
                break
        if not matched:
            for key in FOLDERS:
                if key in col:
                    matched = key
                    break
        if not matched:
            matched = "通知公告"
        by_column.setdefault(matched, []).append(art)
    total_new = len(new_articles)
    total_imported = 0
    total_failed = 0
    for col_name, arts in by_column.items():
        folder_id = FOLDERS[col_name]
        urls = [a["url"] for a in arts]
        log("导入 %s: %d 篇" % (col_name, len(arts)))
        for i in range(0, len(urls), 10):
            batch = urls[i:i+10]
            res = call_api("/import_urls", {
                "knowledge_base_id": KB_ID,
                "folder_id": folder_id,
                "urls": batch,
            }, timeout=120)
            if res.get("code") == 0:
                results = res.get("data", {}).get("results", {})
                for u in batch:
                    r = results.get(u, {})
                    if r.get("ret_code") == 0:
                        total_imported += 1
                    else:
                        total_failed += 1
                        log("  FAIL: %s -> %s" % (u, str(r)[:200]))
            else:
                ok = False
                for attempt in range(1, 4):
                    time.sleep(3)
                    res = call_api("/import_urls", {
                        "knowledge_base_id": KB_ID,
                        "folder_id": folder_id,
                        "urls": batch,
                    }, timeout=120)
                    if res.get("code") == 0:
                        ok = True
                        results = res.get("data", {}).get("results", {})
                        for u in batch:
                            r = results.get(u, {})
                            if r.get("ret_code") == 0:
                                total_imported += 1
                            else:
                                total_failed += 1
                        break
                if not ok:
                    total_failed += len(batch)
                    log("  BATCH FAILED: %s" % batch[0])
            time.sleep(1.5)
        log("  %s 导入完成: %d 篇" % (col_name, len(arts)))
    log("导入汇总: 新增 %d 篇, 成功 %d, 失败 %d" % (total_new, total_imported, total_failed))

def main():
    log("=" * 60)
    log("BZUU 增量爬取 + 自动导入")
    log("=" * 60)
    existing_urls = set()
    if os.path.exists(RESULTS_FILE):
        try:
            with open(RESULTS_FILE) as f:
                data = json.load(f)
            for art in data.get("articles", []):
                existing_urls.add(art["url"])
            log("已加载 %d 个已有 URL" % len(existing_urls))
        except Exception as e:
            log("加载已有结果失败: %s" % e)
    else:
        log("未找到 %s，将进行全量爬取" % RESULTS_FILE)
    visited = set()
    visited.add(BASE_URL + "/")
    new_articles = []

    nav = [
        ("学院概况", "%s/9/list.htm" % BASE_URL, [
            ("学院简介", "%s/10/list.htm" % BASE_URL),
            ("学院章程", "%s/11/list.htm" % BASE_URL),
            ("现任领导", "%s/12/list.htm" % BASE_URL),
            ("历任领导", "%s/13/list.htm" % BASE_URL),
            ("校徽校训", "%s/14/list.htm" % BASE_URL),
            ("校园风光", "%s/15/list.htm" % BASE_URL),
        ]),
        ("机构设置", "%s/16/list.htm" % BASE_URL, [
            ("管理部门", "%s/2454/list.htm" % BASE_URL),
            ("群团组织", "%s/2455/list.htm" % BASE_URL),
            ("教辅单位", "%s/2456/list.htm" % BASE_URL),
            ("院系设置", "%s/38/list.htm" % BASE_URL),
            ("科研机构", "%s/2457/list.htm" % BASE_URL),
        ]),
        ("招生就业", "%s/2760/list.htm" % BASE_URL, []),
        ("人才引进", "%s/61/list.htm" % BASE_URL, []),
        ("网络课堂", "%s/2768/list.htm" % BASE_URL, []),
    ]
    quick = [
        ("学校要闻", "%s/95/list.htm" % BASE_URL),
        ("校园快讯", "%s/96/list.htm" % BASE_URL),
        ("通知公告", "%s/94/list.htm" % BASE_URL),
        ("学术动态", "%s/xsdt/list.htm" % BASE_URL),
        ("媒体聚焦", "%s/2775/list.htm" % BASE_URL),
        ("专题专栏", "%s/101/list.htm" % BASE_URL),
        ("时政要闻", "%s/szyw/list.htm" % BASE_URL),
        ("学习环境", "%s/2850/list.htm" % BASE_URL),
        ("食宿环境", "%s/2851/list.htm" % BASE_URL),
        ("影像亳院", "%s/2852/list.htm" % BASE_URL),
        ("亳院先锋", "%s/2853/list.htm" % BASE_URL),
        ("多彩亳院", "%s/2854/list.htm" % BASE_URL),
    ]
    subsites = [
        ("招生就业 > 招生信息", "http://www.bzuu.edu.cn/zzxx/", "/zzxx/"),
        ("招生就业 > 就业信息", "http://www.bzuu.edu.cn/jyxx/", "/jyxx/"),
        ("招生就业 > 继续教育", "https://www.bzuu.edu.cn/jxjy/", "/jxjy/"),
        ("国际教育", "http://www.bzuu.edu.cn/gjjyxy", "/gjjyxy/"),
        ("亳文化研究", "http://www.bzuu.edu.cn/bwhyjzx", "/bwhyjzx/"),
        ("信息公开", "http://www.bzuu.edu.cn/zwxxgk", "/zwxxgk/"),
    ]

    log("\n开始爬取主站导航...")
    for nav_name, nav_url, sub_items in nav:
        c = crawl_column(nav_name, nav_url, visited, existing_urls, new_articles)
        if c:
            log("  %s: %d 篇新文章" % (nav_name, c))
        time.sleep(0.5)
        for sub_name, sub_url in sub_items:
            c = crawl_column("%s > %s" % (nav_name, sub_name), sub_url, visited, existing_urls, new_articles)
            if c:
                log("    %s: %d 篇新文章" % (sub_name, c))
            time.sleep(0.5)

    log("\n开始爬取快捷栏目...")
    for name, url in quick:
        c = crawl_column(name, url, visited, existing_urls, new_articles)
        if c:
            log("  %s: %d 篇新文章" % (name, c))
        time.sleep(0.5)

    log("\n开始爬取子站...")
    for name, base_url, prefix_path in subsites:
        log("  %s..." % name)
        html, status = fetch_page(base_url)
        if not html:
            continue
        col_urls = set()
        soup = BeautifulSoup(html, "lxml")
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if re.search(re.escape(prefix_path) + r"\d+/list\.htm", href):
                col_urls.add(urljoin(base_url, href))
        for col_url in sorted(col_urls):
            col_id = re.search(r"/(\d+)/list\.htm", col_url)
            col_name = col_id.group(1) if col_id else "unknown"
            full_name = "%s > col_%s" % (name, col_name)
            c = crawl_column(full_name, col_url, visited, existing_urls, new_articles)
            if c:
                log("    col_%s: %d 篇新文章" % (col_name, c))
            time.sleep(0.3)

    log("\n爬取完成。新文章: %d 篇" % len(new_articles))
    if new_articles:
        log("\n开始导入新文章到 ima 知识库...")
        import_new_articles(new_articles)
        # === 附件补导 ===
        log("\n检查新文章附件...")
        try:
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            from ima_att_helpers import import_article_attachments
            att_ok = att_fail = att_skip = 0
            for art in new_articles:
                ok, fail, skip = import_article_attachments(art)
                att_ok += ok
                att_fail += fail
                att_skip += skip
                time.sleep(0.2)
            log("附件补导汇总: 成功 %d, 失败 %d, 跳过 %d" % (att_ok, att_fail, att_skip))
        except Exception as e:
            log("附件补导异常: %s" % e)
    else:
        log("\n无新文章，跳过导入")
    incremental = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "new_articles_count": len(new_articles),
        "new_articles": new_articles,
        "total_urls_visited": len(visited),
    }
    with open(INCREMENTAL_RESULTS, "w", encoding="utf-8") as f:
        json.dump(incremental, f, ensure_ascii=False, indent=2)
    log("增量结果保存到 %s" % INCREMENTAL_RESULTS)
    log("=" * 60)

def git_push_progress():
    if os.environ.get("GITHUB_ACTIONS") == "true":
        return
    try:
        import subprocess
        repo_dir = os.path.dirname(os.path.abspath(__file__))
        if not os.path.exists(os.path.join(repo_dir, ".git")):
            return
        cwd = os.getcwd()
        os.chdir(repo_dir)
        subprocess.run(["git", "add", "-A"], capture_output=True, timeout=30)
        r = subprocess.run(["git", "diff", "--cached", "--quiet"], capture_output=True, timeout=15)
        if r.returncode != 0:
            subprocess.run(["git", "commit", "-m", "auto: 每日增量进度更新 %s" % time.strftime("%Y-%m-%d")],
                          capture_output=True, timeout=30)
            subprocess.run(["git", "push", "origin", "main"], capture_output=True, timeout=120)
            log("进度已推送至 GitHub")
        os.chdir(cwd)
    except Exception as e:
        log("git push 失败（非致命）: %s" % e)
