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
KB_ID = "OcnmLagVzsZ9JEUQTSKXBZCbhYML0l_LEmcEhjOtQ6M="
BASE = "https://ima.qq.com/openapi/wiki/v1"
CLIENT_ID = os.environ.get("IMA_CLIENT_ID") or open(os.path.expanduser("~/.config/ima/client_id")).read().strip()
API_KEY = os.environ.get("IMA_API_KEY") or open(os.path.expanduser("~/.config/ima/api_key")).read().strip()

# 栏目 -> folder_id 映射
FOLDERS = {
    "学校要闻": "folder_7496797081597468",
    "校园快讯": "folder_7496797081576566",
    "通知公告": "folder_7496797081578945",
    "亳院先锋": "folder_7496797081599483",
    "学术动态": "folder_7496797081597045",
    "人才引进": "folder_7496797081578778",
    "学习环境": "folder_7496797081598269",
    "媒体聚焦": "folder_7496797081575512",
    "食宿环境": "folder_7496797081598893",
    "影像亳院": "folder_7496797081597300",
    "招生就业": "folder_7496797081597235",
    "亳文化研究": "folder_7496797081597503",
    "国际教育": "folder_7496797081576232",
    "信息公开": "folder_7496797081598664",
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
                    for a in batch:
                        if a["url"] == u:
                            import_article_images(a, folder_id)
                            break
        else:
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
                            for a in batch:
                                if a["url"] == u:
                                    import_article_images(a, folder_id)
                                    break
                    break
            if batch_failed:
                failed.extend(urls)
        progress["articles_done"] = list(done_set)
        save_progress(progress)
        print(f"[{column}] 进度 {done}/{total}, 失败 {len(failed)}", flush=True)
        if (i // 10) % 10 == 9:
            time.sleep(1)
    print(f"[{column}] 完成: {done}/{total}, 失败: {len(failed)}", flush=True)
    return failed


def import_attachment(att, folder_id):
    """上传单个附件到知识库"""
    url = att["url"]
    name = att["name"]
    column = att.get("column", "未分类")

    ext = url.split("?")[0].split(".")[-1].lower()
    if ext not in MEDIA_TYPE:
        print(f"  跳过不支持类型: {ext} {name}", flush=True)
        return None

    media_type = MEDIA_TYPE[ext]
    content_type = CONTENT_TYPE.get(ext, "application/octet-stream")

    tmp_path = f"/tmp/ima_att_{int(time.time() * 1000)}_{os.path.basename(url.split('?')[0])}"
    if not download_attachment(url, tmp_path):
        if not download_attachment(url, tmp_path):
            print(f"  下载失败: {name}", flush=True)
            return None

    file_size = os.path.getsize(tmp_path)
    if file_size == 0:
        print(f"  空文件跳过: {name}", flush=True)
        os.remove(tmp_path)
        return None

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


def import_article_images(article, folder_id):
    """导入文章中的图片到知识库"""
    images = article.get("images", [])
    if not images:
        return 0
    ok = 0
    for img_url in images:
        if not img_url:
            continue
        name = os.path.basename(img_url.split("?")[0])
        if not name:
            name = f"image_{int(time.time() * 1000)}.jpg"
        ext = name.split(".")[-1].lower() if "." in name else "jpg"
        if ext not in MEDIA_TYPE or MEDIA_TYPE[ext] != 9:
            continue
        content_type = CONTENT_TYPE.get(ext, "image/jpeg")
        tmp_path = f"/tmp/ima_img_{int(time.time() * 1000)}_{name}"
        if not download_attachment(img_url, tmp_path):
            print(f"  [图片] 下载失败: {img_url}", flush=True)
            continue
        file_size = os.path.getsize(tmp_path)
        if file_size == 0:
            os.remove(tmp_path)
            continue
        res = call_api("/create_media", {
            "file_name": name, "file_size": file_size, "content_type": content_type,
            "knowledge_base_id": KB_ID, "file_ext": ext,
        }, timeout=60)
        if res.get("code") != 0:
            print(f"  [图片] create_media失败: {name} -> {res}", flush=True)
            os.remove(tmp_path)
            continue
        data = res["data"]
        media_id = data["media_id"]
        cred = data["cos_credential"]
        try:
            from qcloud_cos import CosConfig, CosS3Client
            config = CosConfig(Region=cred["region"], SecretId=cred["secret_id"], SecretKey=cred["secret_key"], Token=cred["token"])
            client = CosS3Client(config)
            with open(tmp_path, "rb") as fp:
                client.put_object(Bucket=cred["bucket_name"], Body=fp, Key=cred["cos_key"], ContentType=content_type)
        except Exception as e:
            print(f"  [图片] COS上传失败: {name} -> {e}", flush=True)
            os.remove(tmp_path)
            continue
        res = call_api("/add_knowledge", {
            "media_type": 9, "media_id": media_id, "title": name,
            "knowledge_base_id": KB_ID, "folder_id": folder_id,
            "file_info": {"file_name": name, "file_size": file_size},
        }, timeout=60)
        os.remove(tmp_path)
        if res.get("code") == 0:
            ok += 1
            print(f"  ✅ [图片] 导入成功: {name}", flush=True)
        else:
            print(f"  ❌ [图片] add_knowledge失败: {name} -> {res}", flush=True)
    if ok:
        print(f"  [图片] 文章 {article.get('url', '')[:60]}... 导入图片 {ok}/{len(images)}", flush=True)
    return ok


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "articles"
    col_filter = sys.argv[2] if len(sys.argv) > 2 else None
    ext_filter = sys.argv[3] if len(sys.argv) > 3 else None

    progress = {}
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE) as f:
            progress = json.load(f)

    if mode == "articles":
        with open(os.environ.get("MAIN_ARTICLES_FILE", "main_articles.json")) as f:
            arts = json.load(f)
        if col_filter:
            arts = [a for a in arts if a["column"] == col_filter]
        progress = load_progress()
        done_set = set(progress.get("articles_done", []))
        pending = [a for a in arts if a["url"] not in done_set]
        print(f"[文章] 待导入: {len(pending)} (已完成 {len(done_set)})", flush=True)
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
            if ok > 0 and ok % 10 == 0:
                progress["atts_done"] = list(done_set)
                save_progress(progress)
            time.sleep(0.5)

        progress["atts_done"] = list(done_set)
        save_progress(progress)
        print(f"[附件] 完成: {ok}/{len(pending)}", flush=True)

    elif mode == "images":
        with open(os.environ.get("MAIN_ARTICLES_FILE", "main_articles.json")) as f:
            arts = json.load(f)
        if col_filter:
            arts = [a for a in arts if a["column"] == col_filter]
        arts = [a for a in arts if a.get("images")]
        print(f"[图片] 待处理文章数: {len(arts)}", flush=True)
        progress = load_progress()
        done_set = set(progress.get("images_done", []))
        pending = [a for a in arts if a["url"] not in done_set]
        print(f"[图片] 待补导: {len(pending)} (已完成 {len(done_set)})", flush=True)
        total_ok = 0
        total_skip = 0
        for idx, a in enumerate(pending):
            folder_id = FOLDERS.get(a["column"], KB_ID)
            ok = import_article_images(a, folder_id)
            if ok:
                total_ok += ok
                done_set.add(a["url"])
            else:
                total_skip += 1
            if (idx + 1) % 10 == 0:
                progress["images_done"] = list(done_set)
                save_progress(progress)
                print(f"[图片] 进度 {idx+1}/{len(pending)}, 图片导入 {total_ok} 张", flush=True)
            time.sleep(0.3)
        progress["images_done"] = list(done_set)
        save_progress(progress)
        print(f"[图片] 完成: 共导入 {total_ok} 张图片, 跳过 {total_skip} 篇", flush=True)


if __name__ == "__main__":
    main()