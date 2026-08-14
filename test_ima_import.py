#!/usr/bin/env python3
"""测试 ima import_urls API 的最小脚本"""
import json, os, sys, urllib.request

CLIENT_ID = os.environ.get("IMA_CLIENT_ID", "")
API_KEY = os.environ.get("IMA_API_KEY", "")
KB_ID = "8UWnCJWk0DlQ15ppsKOIeyNofz8ZBOJVt7e9Taeu7bg="
BASE = "https://ima.qq.com/openapi/wiki/v1"

# 测试文章 URL（最新发布，不在已有爬取结果中）
TEST_URL = "https://www.bzuu.edu.cn/2026/0812/c95a114822/page.htm"

print("=== ima 导入测试 ===")
print(f"CLIENT_ID: {CLIENT_ID[:5]}...{CLIENT_ID[-5:]}" if CLIENT_ID else "CLIENT_ID: 未设置")
print(f"API_KEY: {API_KEY[:5]}...{API_KEY[-5:]}" if API_KEY else "API_KEY: 未设置")
print(f"测试URL: {TEST_URL}")
print()

payload = {
    "knowledge_base_id": KB_ID,
    "folder_id": "folder_7493563487102220",  # 学校要闻
    "urls": [TEST_URL],
}

req = urllib.request.Request(
    BASE + "/import_urls",
    data=json.dumps(payload).encode(),
    headers={
        "Content-Type": "application/json",
        "ima-openapi-clientid": CLIENT_ID,
        "ima-openapi-apikey": API_KEY,
    },
    method="POST",
)

try:
    with urllib.request.urlopen(req, timeout=120) as r:
        body = json.loads(r.read().decode())
        print("API 响应:")
        print(json.dumps(body, indent=2, ensure_ascii=False))
        if body.get("code") == 0:
            results = body.get("data", {}).get("results", {})
            for url, result in results.items():
                if result.get("ret_code") == 0:
                    print(f"\n✅ 上传成功: {url}")
                else:
                    print(f"\n❌ 上传失败: {url} -> {result}")
        else:
            print(f"\n❌ API 返回错误: {body}")
except urllib.error.HTTPError as e:
    body = e.read().decode(errors="replace")[:1000]
    print(f"\n❌ HTTP {e.code}: {body}")
except Exception as e:
    print(f"\n❌ 异常: {e}")

print()
print("=== 测试结束 ===")
