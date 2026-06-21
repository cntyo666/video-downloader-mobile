"""
视频下载器 - 移动端精简版 v2
支持: 回森/快手/抖音/B站/小红书/微博 + yt-dlp 通用
智能路由：自动识别平台 → 对应解析器 → 降级通用
"""
import os
import re
import time
from flask import Flask, render_template, request, jsonify, Response, stream_with_context
from parsers.huison import HuisonParser
from parsers.douyin import DouyinParser
from parsers.kuaishou import KuaishouParser
from parsers.bilibili import BilibiliParser
from parsers.xiaohongshu import XiaohongshuParser
from parsers.weibo import WeiboParser
from parsers.generic import GenericParser

app = Flask(__name__)


def safe_content_disposition(filename: str) -> str:
    from urllib.parse import quote
    ascii_name = filename.encode('ascii', 'ignore').decode('ascii').strip()
    if not ascii_name:
        ascii_name = 'download'
    encoded = quote(filename)
    return f'attachment; filename="{ascii_name}"; filename*=UTF-8\'\'{encoded}'


# ── 解析器注册（按优先级排序）──
PARSERS = [
    HuisonParser(),     # 回森
    DouyinParser(),     # 抖音/TikTok
    KuaishouParser(),   # 快手
    BilibiliParser(),   # B站
    XiaohongshuParser(),# 小红书
    WeiboParser(),      # 微博
]
GENERIC = GenericParser()


# ── 智能平台检测 ──────────────────────────────────────
PLATFORM_PATTERNS = [
    # (正则匹配, 解析器名称, 中文名)
    (r'(viviv\.com|getkwai\.com)', 'huison', '回森'),
    (r'(douyin\.com|iesdouyin\.com|v\.douyin\.com)', 'douyin', '抖音'),
    (r'(tiktok\.com|vm\.tiktok\.com)', 'douyin', 'TikTok'),
    (r'(kuaishou\.com|gifshow\.com|chenzhongtech\.com)', 'kuaishou', '快手'),
    (r'(bilibili\.com|b23\.tv|bilivideo\.com)', 'bilibili', 'B站'),
    (r'(xiaohongshu\.com|xhslink\.com|xhs\.com)', 'xiaohongshu', '小红书'),
    (r'(weibo\.com|weibo\.cn|m\.weibo\.com)', 'weibo', '微博'),
]

PARSER_MAP = {
    'huison': HuisonParser,
    'douyin': DouyinParser,
    'kuaishou': KuaishouParser,
    'bilibili': BilibiliParser,
    'xiaohongshu': XiaohongshuParser,
    'weibo': WeiboParser,
}


def detect_platform(url: str) -> tuple:
    """检测 URL 对应的平台，返回 (platform_key, platform_name)"""
    for pattern, key, name in PLATFORM_PATTERNS:
        if re.search(pattern, url, re.I):
            return key, name
    return None, None


def parse_with_fallback(url: str) -> dict:
    """
    智能解析流程：
    1. 检测平台 → 用对应解析器
    2. 失败 → 遍历其他解析器
    3. 全失败 → yt-dlp 兜底
    """
    platform_key, platform_name = detect_platform(url)
    errors = []

    # Step 1: 优先用检测到的平台解析器
    if platform_key and platform_key in PARSER_MAP:
        parser = PARSER_MAP[platform_key]()
        try:
            result = parser.parse(url)
            result["parser"] = parser.name
            return result
        except Exception as e:
            errors.append(f"{parser.name}: {str(e)}")

    # Step 2: 遍历所有解析器
    for parser in PARSERS:
        if platform_key and parser.name == platform_name:
            continue  # 已经试过了
        if parser.match(url):
            try:
                result = parser.parse(url)
                result["parser"] = parser.name
                return result
            except Exception as e:
                errors.append(f"{parser.name}: {str(e)}")

    # Step 3: yt-dlp 兜底
    try:
        result = GENERIC.parse(url)
        result["parser"] = GENERIC.name
        return result
    except Exception as e:
        errors.append(f"通用: {str(e)}")

    # 全部失败
    raise RuntimeError("解析失败:\n" + "\n".join(errors))


def extract_urls(text: str) -> list:
    pattern = r'https?://[^\s<>"\')\]]+'
    urls = re.findall(pattern, text)
    return list(dict.fromkeys(urls))


# ── 路由 ──────────────────────────────────────────────

@app.route("/api/config")
def app_config():
    """APP 启动时拉取配置（热更新入口）"""
    return jsonify({
        "version": 2,
        "min_app_version": "1.0",
        "server_url": "https://video-downloader-mobile.onrender.com",
        "features": {
            "huison": True,
            "douyin": True,
            "kuaishou": True,
            "bilibili": True,
            "xiaohongshu": True,
            "weibo": True,
        },
        "notice": "",
    })


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
        result = parse_with_fallback(url)
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
            result = parse_with_fallback(url)
            result["url"] = url
            results.append(result)
        except Exception as e:
            results.append({"url": url, "error": str(e), "parser": "未知"})
    return jsonify({"results": results, "total": len(results)})


@app.route("/api/download", methods=["POST"])
def download_proxy():
    # 支持 JSON 和 form 两种提交方式
    if request.is_json:
        data = request.get_json()
    else:
        data = request.form
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
    print(f"[启动] 视频下载器 移动端 v2.0")
    print(f"[地址] http://0.0.0.0:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
