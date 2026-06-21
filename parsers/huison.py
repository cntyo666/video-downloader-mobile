"""回森解析器 — 纯 HTTP 版（通过移动端页面提取视频/音频）"""
import re
import json
import requests
from urllib.parse import urlparse, parse_qs, unquote
from .base import BaseParser


class HuisonParser(BaseParser):
    name = "回森"
    domains = ["viviv.com", "getkwai.com", "h5.getkwai.com"]

    def parse(self, url: str) -> dict:
        redirect_url = self._follow_redirect(url)
        params = self._extract_params(redirect_url)

        # 方式1: 移动端页面提取
        result = self._parse_mobile_page(redirect_url, params)
        if result.get("video_url") or result.get("audio_url"):
            return result

        # 方式2: PC 页面静态提取
        result = self._parse_static_page(redirect_url, params)
        if result.get("video_url") or result.get("audio_url"):
            return result

        # 方式3: 从参数中提取音频 URL
        if params.get("audioUrl"):
            return {
                "platform": "回森",
                "title": f"回森_{params.get('itemId', '未知')}",
                "audio_url": params["audioUrl"],
                "video_url": None,
            }

        raise RuntimeError("无法解析该回森链接")

    def _parse_mobile_page(self, url: str, params: dict) -> dict:
        """移动端页面解析"""
        headers = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                          "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 "
                          "Mobile/15E148 Safari/604.1",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }
        try:
            resp = requests.get(url, headers=headers, timeout=15, allow_redirects=True)
            html = resp.text
            return self._extract_from_html(html, params)
        except Exception:
            return {}

    def _parse_static_page(self, url: str, params: dict) -> dict:
        """PC 页面解析"""
        try:
            resp = requests.get(url, headers=self.HEADERS, timeout=15)
            html = resp.text
            return self._extract_from_html(html, params)
        except Exception:
            return {}

    def _extract_from_html(self, html: str, params: dict) -> dict:
        data = {"platform": "回森"}

        # 标题
        title_m = re.search(r'<title[^>]*>(.*?)</title>', html, re.S)
        if title_m:
            title = title_m.group(1).strip()
            title = re.sub(r'\s*[-|]\s*(作品分享\s*[-|]\s*)?回森.*$', '', title).strip()
            if title:
                data["title"] = title
        if not data.get("title"):
            data["title"] = f"回森_{params.get('itemId', '未知')}"

        # 从 URL 参数提取音频
        if params.get("audioUrl"):
            data["audio_url"] = params["audioUrl"]

        # 从 HTML 提取视频 URL
        video_patterns = [
            r'"videoUrl"\s*:\s*"(https?://[^"]+)"',
            r'"playUrl"\s*:\s*"(https?://[^"]+)"',
            r'"video_url"\s*:\s*"(https?://[^"]+)"',
            r'"src"\s*:\s*"(https?://[^"]*\.mp4[^"]*)"',
            r'src="(https?://[^"]*\.mp4[^"]*)"',
            r'"url"\s*:\s*"(https?://[^"]*\.mp4[^"]*)"',
        ]
        for p in video_patterns:
            m = re.search(p, html)
            if m:
                data["video_url"] = m.group(1).replace('\\u002F', '/')
                break

        # 从 HTML 提取音频 URL
        if not data.get("audio_url"):
            audio_patterns = [
                r'"audioUrl"\s*:\s*"(https?://[^"]+)"',
                r'"audio_url"\s*:\s*"(https?://[^"]+)"',
                r'"src"\s*:\s*"(https?://[^"]*\.m4a[^"]*)"',
                r'src="(https?://[^"]*\.m4a[^"]*)"',
            ]
            for p in audio_patterns:
                m = re.search(p, html)
                if m:
                    data["audio_url"] = m.group(1).replace('\\u002F', '/')
                    break

        # 作者
        author_m = re.search(r'"userName"\s*:\s*"(.*?)"', html)
        if not author_m:
            author_m = re.search(r'"nickname"\s*:\s*"(.*?)"', html)
        if author_m:
            data["author"] = author_m.group(1)

        # 封面
        cover_m = re.search(r'"coverUrl"\s*:\s*"(https?://[^"]+)"', html)
        if not cover_m:
            cover_m = re.search(r'"cover"\s*:\s*"(https?://[^"]+)"', html)
        if cover_m:
            data["cover_url"] = cover_m.group(1).replace('\\u002F', '/')

        return data

    def _follow_redirect(self, url: str) -> str:
        try:
            resp = requests.head(url, headers=self.HEADERS, allow_redirects=False, timeout=10)
            loc = resp.headers.get("Location", "")
            if loc:
                return loc
        except Exception:
            pass
        try:
            resp = requests.get(url, headers=self.HEADERS, allow_redirects=True, timeout=10)
            return resp.url
        except Exception:
            return url

    def _extract_params(self, url: str) -> dict:
        parsed = urlparse(url)
        qs = parse_qs(parsed.query)
        result = {}
        for key in ["itemId", "audioUrl", "fromId", "cid"]:
            if key in qs:
                val = qs[key][0]
                if key == "audioUrl":
                    val = unquote(val)
                result[key] = val
        return result
