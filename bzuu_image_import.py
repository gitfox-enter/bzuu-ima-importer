#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
亳州学院全站文章图片导入 ima 知识库
- 遍历 main_articles.json 所有文章
- 爬取每个文章页面，提取正文中的图片 URL
- 按栏目分发到 ima 各文件夹
- 用文章标题命名图片文件
- 不去重，每次都上传
- 进度记录在 ima_import_progress.json 的 images_done 字段
"""
import json, os, sys, time, re, urllib.request, urllib.error
from collections import defaultdict

# ============ 配置 ============
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

MEDIA_TYPE = {"png": 9, "jpg": 9, "jpeg": 9, "webp": 9, "gif": 9}
CONTENT_TYPE = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "webp": "image/webp",
    "gif": "image/gif",
}

MAIN_ARTICLES = os.environ.get("MAIN_ARTICLES_FILE", "main_articles.json")
PROGRESS_FILE = os.environ.get("IMPORT_PROGRESS_FILE", "ima_import_progress.json")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


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
    except Exception as e:
        return {"code": -1, "error": str(e)}


def fetch_page(url, timeout=30):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", "replace")
    except Exception as e:
        print(f"    抓取失败: {url} -> {e}", flush=True)
        return ""


def extract_title_and_images(html):
    title = re.search(r"<h1[^>]*>([^<]+)</h1>", html)
    title = title.group(1).strip() if title else ""

    # 提取正文区域
    content_match = re.search(
        r'<div[^>]*class="[^"]*(?:wp_articlecontent|article-content|entry-content|post-content)[^"]*"[^>]*>(.*?)</div>',
        html, re.DOTALL | re.I
    )
    content = content_match.group(1) if content_match else html

    # 提取图片
    raw_imgs = re.findall(r'src=["\']([^"\']+)["\']', content)
    images = []
    for src in raw_imgs:
        if not src or src.startswith("data:") or "template" in src:
            continue
        if src.startswith("//"):
            src = "https:" + src
        elif src.startswith("/"):
            src = "https://www.bzuu.edu.cn" + src
        if "bzuu.edu.cn" in src or "/_upload/" in src:
            ext = src.split("?")[0].split(".")[-1].lower()
            if ext in MEDIA_TYPE:
                images.append(src)
    return title, images


def safe_filename(s, maxlen=50):
    s = re.sub(r'[\\/*?:"<>|]', "_", s)
    s = re.sub(r"\s+", "_", s).strip("_")
    return s[:maxlen]


def download_file(url, dest, timeout=60):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            with open(dest, "wb") as f:
                f.write(r.read())
        return os.path.getsize(dest) > 0
    except Exception:
        return False


def upload_image(image_url, folder_id, article_title, seq):
    ext = image_url.split("?")[0].split(".")[-1].lower()
    if ext not in MEDIA_TYPE:
        return None

    safe_title = safe_filename(article_title, 50)
    filename = f"{safe_title}_{seq:03d}.{ext}"
    tmp_path = f"/tmp/ima_img_{int(time.time() * 1000)}_{seq}_{ext}"

    if not download_file(image_url, tmp_path):
        print(f"    下载失败: {image_url}", flush=True)
        return None

    file_size = os.path.getsize(tmp_path)

    # 1. create_media
    res = call_api("/create_media", {
        "file_name": filename,
        "file_size": file_size,
        "content_type": CONTENT_TYPE.get(ext, "image/jpeg"),
        "knowledge_base_id": KB_ID,
        "file_ext": ext,
    }, timeout=60)
    if res.get("code") != 0:
        print(f"    create_media失败: {filename} -> {res.get('msg', str(res)[:80])}", flush=True)
        os.remove(tmp_path)
        return None

    data = res["data"]
    media_id = data["media_id"]
    cred = data["cos_credential"]

    # 2. COS 上传
    try:
        from qcloud_cos import CosConfig, CosS3Client
        config = CosConfig(
            Region=cred["region"],
            SecretId=cred["secret_id"],
            SecretKey=cred["secret_key"],
            Token=cred["token"],
        )
        client = CosS3Client(config)
        with open(tmp_path, "rb") as fp:
            client.put_object(
                Bucket=cred["bucket_name"],
                Body=fp,
                Key=cred["cos_key"],
                ContentType=CONTENT_TYPE.get(ext, "image/jpeg"),
            )
    except Exception as e:
        print(f"    COS上传失败: {filename} -> {e}", flush=True)
        os.remove(tmp_path)
        return None

    # 3. add_knowledge
    res = call_api("/add_knowledge", {
        "media_type": 9,
        "media_id": media_id,
        "title": filename,
        "knowledge_base_id": KB_ID,
        "folder_id": folder_id,
        "file_info": {"file_name": filename, "file_size": file_size},
    }, timeout=60)

    os.remove(tmp_path)

    if res.get("code") == 0:
        print(f"    上传成功: {filename} -> {media_id}", flush=True)
        return media_id
    else:
        print(f"    add_knowledge失败: {filename} -> {res.get('msg', str(res)[:80])}", flush=True)
        return None


def save_progress(progress):
    tmp = PROGRESS_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(progress, f, ensure_ascii=False)
    os.replace(tmp, PROGRESS_FILE)


def load_progress():
    if os.path.exists(PROGRESS_FILE):
        try:
            with open(PROGRESS_FILE) as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def main():
    progress = load_progress()
    images_done = set(progress.get("images_done", []))

    if not os.path.exists(MAIN_ARTICLES):
        print(f"文章列表不存在: {MAIN_ARTICLES}")
        sys.exit(1)

    with open(MAIN_ARTICLES) as f:
        arts = json.load(f)
    print(f"全站文章总数: {len(arts)}", flush=True)

    processed = 0
    uploaded = 0
    errors = 0

    for a in arts:
        column = a.get("column", "未分类")
        url = a.get("url", "")
        folder_id = FOLDERS.get(column)
        if not url or not folder_id:
            continue

        processed += 1
        print(f"[{processed}/{len(arts)}] {column} | {url[:60]}", flush=True)

        html = fetch_page(url)
        if not html:
            errors += 1
            time.sleep(1)
            continue

        title, images = extract_title_and_images(html)
        if not images:
            time.sleep(0.3)
            continue

        print(f"  文章: {title[:40]} | {len(images)} 张图片", flush=True)

        for i, img_url in enumerate(images, 1):
            media_id = upload_image(img_url, folder_id, title, i)
            if media_id:
                uploaded += 1
                key = f"{url}|{img_url}"
                images_done.add(key)
            else:
                errors += 1

            if uploaded > 0 and uploaded % 10 == 0:
                progress["images_done"] = list(images_done)
                save_progress(progress)
                print(f"  [进度] 已上传 {uploaded} 张", flush=True)

            time.sleep(0.8)

        time.sleep(0.5)

    progress["images_done"] = list(images_done)
    save_progress(progress)

    print(f"\n========== 完成 ==========", flush=True)
    print(f"处理文章: {processed}", flush=True)
    print(f"实际上传: {uploaded}", flush=True)
    print(f"失败次数: {errors}", flush=True)
    print(f"images_done: {len(images_done)} 条", flush=True)


if __name__ == "__main__":
    main()
