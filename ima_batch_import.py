#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IMA 知识库批量导入脚本
- 文章：import_urls（每批10个URL）
- 附件：create_media -> COS Upload -> add_knowledge
支持断点续传，进度记录在 ima_import_progress.json
"""
import json
import os
import sys
import time
import urllib.request
import urllib.error

# ============ 配置 ============
KB_ID = "8UWnCJWk0DlQ15ppsKOIeyNofz8ZBOJVt7e9Taeu7bg="
BASE = "https://ima.qq.com/openapi/wiki/v1"
CLIENT_ID = os.environ.get("IMA_CLIENT_ID") or open(os.path.expanduser("~/.config/ima/client_id")).read().strip()
API_KEY = os.environ.get("IMA_API_KEY") or open(os.path.expanduser("~/.config/ima/api_key")).read().strip()

# 栏目 -> folder_id 映射
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

# 媒体类型映射（扩展名 -> media_type）
MEDIA_TYPE = {
    "pdf": 1,
    "doc": 3, "docx": 3,
    "ppt": 4, "pptx": 4,
    "xls": 5, "xlsx": 5, "csv": 5,
    "md": 7, "markdown": 7,
    "png": 9, "jpg": 9, "jpeg": 9, "webp": 9,
    "txt": 13,
    "mp3": 15, "m4a": 15, "wav": 15, "aac": 15,
}
CONTENT_TYPE = {
    "pdf": "application/pdf",
    "doc": "application/msword",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "ppt": "application/vnd.ms-powerpoint",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "xls": "application/vnd.ms-excel",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "csv": "text/csv",
    "md": "text/markdown",
    "markdown": "text/markdown",
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "webp": "image/webp",
    "txt": "text/plain",
    "mp3": "audio/mpeg",
    "m4a": "audio/x-m4a",
    "wav": "audio/wav",
    "aac": "audio/aac",
}

PROGRESS_FILE = os.environ.get("IMPORT_PROGRESS_FILE", "ima_import_progress.json")


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


def download_attachment(url, dest, timeout=60):
    """下载附件到本地"""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            with open(dest, "wb") as f:
                f.write(r.read())
        return True
    except Exception as e:
        return False


def save_progress(progress):
    """保存进度到文件（原子写）"""
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


def import_articles_batch(column, arts):
    """批量导入文章URL，每批10个，每批保存进度（断点续传）"""
    folder_id = FOLDERS.get(column, KB_ID)
    total = len(arts)
    done = 0
    failed = []
    progress = load_progress()
    done_set = set(progress.get("articles_done", []))
    for i in range(0, total, 10):
        batch = arts[i:i + 10]
        urls = [a["url"] for a in batch]
        res = call_api("/import_urls", {
            "knowledge_base_id": KB_ID,
            "folder_id": folder_id,
            "urls": urls,
        }, timeout=120)
        if res.get("code") == 0:
            results = res.get("data", {}).get("results", {})
            for u in urls:
                r = results.get(u, {})
                if r.get("ret_code") != 0:
                    failed.append(u)
                else:
                    done += 1
                    done_set.add(u)
        else:
            # 整批失败：重试3次
            batch_failed = True
            for attempt in range(1, 4):
                print(f"  ⚠️ 批失败 code={res.get('code')} msg={res.get('msg', '')}, 第{attempt}次重试", flush=True)
                time.sleep(3)
                res = call_api("/import_urls", {
                    "knowledge_base_id": KB_ID,
                    "folder_id": folder_id,
                    "urls": urls,
                }, timeout=120)
                if res.get("code") == 0:
                    batch_failed = False
                    results = res.get("data", {}).get("results", {})
                    for u in urls:
                        r = results.get(u, {})
                        if r.get("ret_code") != 0:
                            failed.append(u)
                        else:
                            done += 1
                            done_set.add(u)
                    break
            if batch_failed:
                failed.extend(urls)
        # 每批保存进度
        progress["articles_done"] = list(done_set)
        save_progress(progress)
        print(f"[{column}] 进度 {done}/{total}, 失败 {len(failed)}", flush=True)
        # 每10批短暂暂停，避免限流
        if (i // 10) % 10 == 9:
            time.sleep(1)
    print(f"[{column}] 完成: {done}/{total}, 失败: {len(failed)}", flush=True)
    return failed


def import_attachment(att, folder_id):
    """上传单个附件到知识库"""
    url = att["url"]
    name = att["name"]
    column = att.get("column", "未分类")

    # 解析扩展名
    ext = url.split("?")[0].split(".")[-1].lower()
    if ext not in MEDIA_TYPE:
        print(f"  跳过不支持类型: {ext} {name}", flush=True)
        return None

    media_type = MEDIA_TYPE[ext]
    content_type = CONTENT_TYPE.get(ext, "application/octet-stream")

    # 下载文件
    tmp_path = f"/tmp/ima_att_{int(time.time() * 1000)}_{os.path.basename(url.split('?')[0])}"
    if not download_attachment(url, tmp_path):
        # 尝试带UA重试
        if not download_attachment(url, tmp_path):
            print(f"  下载失败: {name}", flush=True)
            return None

    file_size = os.path.getsize(tmp_path)
    if file_size == 0:
        print(f"  空文件跳过: {name}", flush=True)
        os.remove(tmp_path)
        return None

    # 1. create_media
    res = call_api("/create_media", {
        "file_name": name,
        "file_size": file_size,
        "content_type": content_type,
        "knowledge_base_id": KB_ID,
        "file_ext": ext,
    }, timeout=60)
    if res.get("code") != 0:
        print(f"  create_media失败: {name} -> {res}", flush=True)
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
                ContentType=content_type,
            )
    except Exception as e:
        print(f"  COS上传失败: {name} -> {e}", flush=True)
        os.remove(tmp_path)
        return None

    # 3. add_knowledge
    res = call_api("/add_knowledge", {
        "media_type": media_type,
        "media_id": media_id,
        "title": name,
        "knowledge_base_id": KB_ID,
        "folder_id": folder_id,
        "file_info": {
            "file_name": name,
            "file_size": file_size,
        },
    }, timeout=60)
    os.remove(tmp_path)

    if res.get("code") == 0:
        print(f"  ✅ 附件导入成功: {name}", flush=True)
        return media_id
    else:
        print(f"  ❌ add_knowledge失败: {name} -> {res}", flush=True)
        return None


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "articles"
    col_filter = sys.argv[2] if len(sys.argv) > 2 else None
    ext_filter = sys.argv[3] if len(sys.argv) > 3 else None

    # 读取进度（断点续传）
    progress = {}
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE) as f:
            progress = json.load(f)

    if mode == "articles":
        with open(os.environ.get("MAIN_ARTICLES_FILE", "main_articles.json")) as f:
            arts = json.load(f)
        if col_filter:
            arts = [a for a in arts if a["column"] == col_filter]
        # 过滤已导入
        progress = load_progress()
        done_set = set(progress.get("articles_done", []))
        pending = [a for a in arts if a["url"] not in done_set]
        print(f"[文章] 待导入: {len(pending)} (已完成 {len(done_set)})", flush=True)
        # 按栏目分组导入（每组用各自 folder_id）
        from collections import defaultdict
        groups = defaultdict(list)
        for a in pending:
            groups[a["column"]].append(a)
        total_failed = 0
        for column in FOLDERS:
            group = groups.get(column)
            if not group:
                continue
            print(f"========== 开始栏目 [{column}] {len(group)}篇 ==========", flush=True)
            failed = import_articles_batch(column, group)
            total_failed += len(failed)
        # 不在 FOLDERS 中的栏目（兜底处理，不应发生）
        for column, group in groups.items():
            if column not in FOLDERS:
                print(f"⚠️ 未映射栏目 [{column}] {len(group)}篇，跳过", flush=True)
                total_failed += len(group)
        print(f"[文章] 全部完成! 失败待重试: {total_failed}", flush=True)

    elif mode == "attachments":
        with open(os.environ.get("MAIN_ATTACHMENTS_FILE", "main_attachments.json")) as f:
            atts = json.load(f)
        if col_filter:
            atts = [a for a in atts if a.get("column") == col_filter]
        if ext_filter:
            exts = set(ext_filter.split(","))
            atts = [a for a in atts if a["url"].split("?")[0].split(".")[-1].lower() in exts]
        # 过滤已导入
        progress = load_progress()
        done_set = set(progress.get("atts_done", []))
        pending = [a for a in atts if a["url"] not in done_set]
        print(f"[附件] 待导入: {len(pending)} (已完成 {len(done_set)})", flush=True)

        ok = 0
        for att in pending:
            folder_id = FOLDERS.get(att.get("column"), KB_ID)
            media_id = import_attachment(att, folder_id)
            if media_id:
                ok += 1
                done_set.add(att["url"])
            else:
                print(f"  跳过失败附件: {att.get('name')}", flush=True)
            # 每10个保存一次进度
            if ok > 0 and ok % 10 == 0:
                progress["atts_done"] = list(done_set)
                save_progress(progress)
            time.sleep(0.5)

        progress["atts_done"] = list(done_set)
        save_progress(progress)
        print(f"[附件] 完成: {ok}/{len(pending)}", flush=True)


if __name__ == "__main__":
    main()