#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
压缩包(rar/zip)处理脚本：
1. 从 main_attachments.json 筛选 rar/zip 附件
2. 下载到本地 /tmp/archives/
3. 解压（zip用zipfile，rar用unrar命令）
4. 递归找出所有解压文件，按扩展名映射 media_type
5. 走 create_media -> COS put_object -> add_knowledge 上传到对应栏目
支持断点续传，进度记录在 /root/ima_archive_progress.json
"""
import json
import os
import sys
import time
import shutil
import subprocess
import urllib.request
import urllib.error
import zipfile

KB_ID = "OcnmLagVzsZ9JEUQTSKXBZCbhYML0l_LEmcEhjOtQ6M="
BASE = "https://ima.qq.com/openapi/wiki/v1"
CLIENT_ID = os.environ.get("IMA_CLIENT_ID") or open(os.path.expanduser("~/.config/ima/client_id")).read().strip()
API_KEY = os.environ.get("IMA_API_KEY") or open(os.path.expanduser("~/.config/ima/api_key")).read().strip()

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

PROGRESS_FILE = os.environ.get("ARCHIVE_PROGRESS_FILE", "ima_archive_progress.json")
ALLOWED_SUBDIRS = set(MEDIA_TYPE.keys())


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
        body = e.read().decode(errors="replace")[:800]
        return {"code": e.code, "error": body}
    except Exception as e:
        return {"error": str(e)}


def download(url, dest, timeout=120):
    """下载文件，带UA和重试"""
    for attempt in range(2):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = r.read()
            if len(data) < 100:
                print(f"    下载内容过小({len(data)}B)，可能失败")
                return False
            with open(dest, "wb") as f:
                f.write(data)
            return True
        except Exception as e:
            print(f"    下载失败 attempt {attempt+1}: {e}")
            time.sleep(2)
    return False


def extract_archive(archive_path, extract_dir):
    """解压压缩包，返回文件列表"""
    files = []
    ext = archive_path.rsplit(".", 1)[-1].lower() if "." in archive_path else ""
    try:
        if ext == "zip":
            # 用系统 unzip 处理中文编码（-O gbk），比 Python zipfile 正确处理 GBK 文件名
            r = subprocess.Popen(["unzip", "-O", "gbk", "-o", archive_path, "-d", extract_dir],
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            out, err = r.communicate(timeout=300)
            if r.returncode != 0:
                print(f"    unzip 解压失败: {err.decode(errors='replace')[:200]}")
                # fallback: 用 Python zipfile 试一次
                print(f"    尝试 Python zipfile fallback...")
                try:
                    with zipfile.ZipFile(archive_path) as z:
                        z.extractall(extract_dir)
                except Exception as e2:
                    print(f"    fallback 也失败: {e2}")
                    return []
        elif ext == "rar":
            # Python 3.6 不支持 capture_output，用 Popen 兼容
            r = subprocess.Popen(["/usr/local/bin/unrar", "x", "-o+", archive_path, extract_dir + "/"],
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            out, err = r.communicate(timeout=300)
            if r.returncode != 0:
                print(f"    unrar 解压失败: {err.decode(errors='replace')[:200]}")
                return []
        else:
            print(f"    未知压缩格式: {ext}")
            return []
    except Exception as e:
        print(f"    解压异常: {e}")
        return []
    # 递归收集文件
    for root_dir, dirs, fnames in os.walk(extract_dir):
        for fn in fnames:
            fp = os.path.join(root_dir, fn)
            if os.path.isfile(fp):
                files.append(fp)
    return files


def upload_file(file_path, title, folder_id, column_name):
    """上传单个文件到ima"""
    if not os.path.exists(file_path):
        return False, "文件不存在"
    fsize = os.path.getsize(file_path)
    if fsize < 10:
        return False, "文件为空"
    fext = file_path.rsplit(".", 1)[-1].lower() if "." in file_path else ""
    # 去掉可能的查询参数
    fext = fext.split("?")[0]
    if fext not in MEDIA_TYPE:
        return False, f"不支持类型:{fext}"
    media_type = MEDIA_TYPE[fext]
    content_type = CONTENT_TYPE.get(fext, "application/octet-stream")
    fname = os.path.basename(file_path)

    # 1. create_media 拿凭证
    r1 = call_api("/create_media", {
        "file_name": fname,
        "file_size": fsize,
        "content_type": content_type,
        "knowledge_base_id": KB_ID,
        "file_ext": fext,
    })
    if r1.get("code") != 0:
        return False, f"create_media失败: {json.dumps(r1, ensure_ascii=False)[:300]}"
    data = r1["data"]
    media_id = data["media_id"]
    cred = data["cos_credential"]
    # 2. COS put_object
    try:
        from qcloud_cos import CosConfig, CosS3Client
        config = CosConfig(
            Region=cred["region"],
            SecretId=cred["secret_id"],
            SecretKey=cred["secret_key"],
            Token=cred["token"],
            Scheme="https",
        )
        client = CosS3Client(config)
        with open(file_path, "rb") as fp:
            client.put_object(
                Bucket=cred["bucket_name"],
                Body=fp,
                Key=cred["cos_key"],
                ContentType=content_type,
            )
    except Exception as e:
        return False, f"COS上传失败: {e}"
    # 3. add_knowledge
    r2 = call_api("/add_knowledge", {
        "media_type": media_type,
        "media_id": media_id,
        "title": title,
        "knowledge_base_id": KB_ID,
        "folder_id": folder_id,
        "file_info": {"file_name": fname, "file_size": fsize},
    })
    if r2.get("code") != 0:
        return False, f"add_knowledge失败: {json.dumps(r2, ensure_ascii=False)[:300]}"
    return True, media_id


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
            pass
    return {"archives_done": {}, "files_done": []}


def main():
    progress = load_progress()
    with open(os.environ.get("MAIN_ATTACHMENTS_FILE", "main_attachments.json")) as f:
        atts = json.load(f)
    compressed = [a for a in atts if a["url"].lower().rstrip(".").endswith(".rar") or a["url"].lower().rstrip(".").endswith(".zip")]
    print(f"压缩包总数: {len(compressed)}")
    print(f"已处理: {len(progress['archives_done'])}")

    work_dir = "/tmp/archives"
    os.makedirs(work_dir, exist_ok=True)

    for i, att in enumerate(compressed, 1):
        url = att["url"]
        name = att["name"]
        column = att["column"]
        folder_id = FOLDERS.get(column)
        if not folder_id:
            print(f"[{i}/{len(compressed)}] 跳过(无folder): {name}")
            continue
        if url in progress["archives_done"]:
            print(f"[{i}/{len(compressed)}] 已完成: {name}")
            continue

        ext = url.rsplit(".", 1)[-1].lower().split("?")[0] if "." in url else "?"
        print(f"[{i}/{len(compressed)}] 处理 {ext}: {name} ({column})")
        archive_path = os.path.join(work_dir, f"arc_{i}.{ext}")
        if not download(url, archive_path):
            print(f"    下载失败，跳过")
            progress["archives_done"][url] = {"status": "download_fail", "name": name}
            save_progress(progress)
            continue

        extract_dir = os.path.join(work_dir, f"arc_{i}_extract")
        if os.path.exists(extract_dir):
            shutil.rmtree(extract_dir)
        os.makedirs(extract_dir)

        files = extract_archive(archive_path, extract_dir)
        if not files:
            print(f"    解压无文件，跳过")
            progress["archives_done"][url] = {"status": "extract_fail", "name": name}
            save_progress(progress)
            continue

        ok = 0
        fail = 0
        for fp in files:
            fext = fp.rsplit(".", 1)[-1].lower().split("?")[0] if "." in fp else ""
            rel = os.path.relpath(fp, extract_dir)
            # 标题用 压缩包名_相对路径
            title = f"{name}_{rel}" if rel != os.path.basename(fp) else f"{name}_{os.path.basename(fp)}"
            if title in progress["files_done"]:
                ok += 1
                continue
            if fext not in MEDIA_TYPE:
                print(f"    跳过不支持类型 {fext}: {rel}")
                fail += 1
                continue
            success, msg = upload_file(fp, title, folder_id, column)
            if success:
                ok += 1
                progress["files_done"].append(title)
                print(f"    OK: {title[:80]}")
            else:
                fail += 1
                print(f"    FAIL: {title[:60]} -> {msg[:120]}")
            time.sleep(0.5)

        print(f"    压缩包 {name}: 成功{ok} 失败{fail}")
        progress["archives_done"][url] = {"status": "done", "name": name, "ok": ok, "fail": fail}
        save_progress(progress)
        # 清理
        try:
            os.remove(archive_path)
            shutil.rmtree(extract_dir)
        except Exception:
            pass

    print("=== 全部压缩包处理完成 ===")
    with open(os.environ.get("ARCHIVE_RESULT_FILE", "ima_archive_result.json"), "w") as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()