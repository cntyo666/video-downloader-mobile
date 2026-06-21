"""
视频下载器 - 移动端精简版
支持: 抖音/B站/小红书/微博 + yt-dlp 通用
去掉 Playwright 依赖，纯 HTTP 请求
"""
import os
import sys
import re
import json
import time
import shutil
import subprocess
from pathlib import Path
from urllib.parse import urlparse

from flask import Flask, render_template, request, jsonify, Response, stream_with_context
from parsers.douyin import DouyinParser
from parsers.bilibili import BilibiliParser
from parsers.xiaohongshu import XiaohongshuParser
from parsers.weibo import WeiboParser
from parsers.kuaishou import KuaishouParser
from parsers.generic import GenericParser

app = Flask(__name__)


def safe_content_disposition(filename: str) -> str:
    from urllib.parse import quote
    ascii_name = filename.encode('ascii', 'ignore').decode('ascii').strip()
    if not ascii_name:
        ascii_name = 'download'
    encoded = quote(filename)
    return f'attachment; filename="{ascii_name}"; filename*=UTF-8\'\'{encoded}'


PARSERS = [
    DouyinParser(),
    BilibiliParser(),
    XiaohongshuParser(),
    KuaishouParser(),
    WeiboParser(),
    GenericParser(),
]


def get_parser(url: str):
    for p in PARSERS:
        if p.match(url):
            return p
    return GenericParser()


def extract_urls(text: str) -> list:
    pattern = r'https?://[^\s<>"\')\]]+'
    urls = re.findall(pattern, text)
    return list(dict.fromkeys(urls))


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/parse", methods=["POST"])
def parse_url():
    data = request.get_json()
    url = data.get("url", "").strip()
    if not url:
        return jsonify({"error": "请输入链接"}), 400
    try:
        parser = get_parser(url)
        result = parser.parse(url)
        result["parser"] = parser.name
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/batch_parse", methods=["POST"])
def batch_parse():
    data = request.get_json()
    text = data.get("text", "")
    urls = extract_urls(text)
    if not urls:
        return jsonify({"error": "未找到有效链接"}), 400

    results = []
    for url in urls:
        try:
            parser = get_parser(url)
            result = parser.parse(url)
            result["parser"] = parser.name
            result["url"] = url
            results.append(result)
        except Exception as e:
            results.append({"url": url, "error": str(e), "parser": "未知"})
    return jsonify({"results": results, "total": len(results)})


@app.route("/api/download", methods=["POST"])
def download_proxy():
    data = request.get_json()
    media_url = data.get("url", "")
    title = data.get("title", f"video_{int(time.time())}")
    media_type = data.get("type", "video")

    if not media_url:
        return jsonify({"error": "无下载地址"}), 400

    safe_name = re.sub(r'[\\/:*?"<>|\n\r\t]', '_', title)[:80]
    safe_name = re.sub(r'_+', '_', safe_name).strip('_. ')
    if not safe_name:
        safe_name = f"download_{int(time.time())}"
    ext = ".mp4" if media_type == "video" else ".m4a"
    filename = f"{safe_name}{ext}"

    headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
    }

    extra_cookies = data.get("_cookies", "")
    extra_referer = data.get("_referer", "")
    if extra_cookies:
        headers["Cookie"] = extra_cookies
    if extra_referer:
        headers["Referer"] = extra_referer
    if "bilivideo.com" in media_url or "bilibili.com" in media_url:
        headers["Referer"] = "https://www.bilibili.com/"

    try:
        import requests as req
        resp = req.get(media_url, headers=headers, stream=True, timeout=120)
        resp.raise_for_status()

        content_length = resp.headers.get('Content-Length')
        content_type = resp.headers.get('Content-Type', 'application/octet-stream')

        def generate():
            for chunk in resp.iter_content(8192):
                if chunk:
                    yield chunk

        response = Response(stream_with_context(generate()), content_type=content_type)
        response.headers['Content-Disposition'] = safe_content_disposition(filename)
        if content_length:
            response.headers['Content-Length'] = content_length
        return response
    except Exception as e:
        return jsonify({"error": f"下载失败: {str(e)}"}), 500


if __name__ == "__main__":
    import sys, io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    port = int(os.environ.get("PORT", 5000))
    print(f"[启动] 视频下载器 移动端 v1.0")
    print(f"[地址] http://0.0.0.0:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
