"""小红书解析器"""
import re
import requests
from .base import BaseParser


class XiaohongshuParser(BaseParser):
    name = "小红书"
    domains = ["xiaohongshu.com", "xhslink.com"]

    def parse(self, url: str) -> dict:
        real_url = self._follow_redirect(url)
        headers = {
            **self.HEADERS,
            "Referer": "https://www.xiaohongshu.com/",
        }
        resp = requests.get(real_url, headers=headers, timeout=15)
        html = resp.text

        data = {"platform": "小红书"}

        # 标题
        title_m = re.search(r'<title[^>]*>(.*?)</title>', html, re.S)
        if title_m:
            t = title_m.group(1).strip().replace(' - 小红书', '').strip()
            if t:
                data["title"] = t

        # 视频 URL
        video_patterns = [
            r'"originVideoKey"\s*:\s*"(https?://[^"]+)"',
            r'"video"\s*:\s*\{[^}]*"url"\s*:\s*"(https?://[^"]+)"',
            r'"url"\s*:\s*"(https?://[^"]*\.mp4[^"]*)"',
            r'"media"\s*:\s*\{[^}]*"stream"\s*:\s*\{[^}]*"h264"\s*:\s*\[?\{[^}]*"url"\s*:\s*"(https?://[^"]+)"',
        ]
        for p in video_patterns:
            m = re.search(p, html)
            if m:
                data["video_url"] = m.group(1).replace('\\u002F', '/').replace('\\/', '/')
                break

        # 封面
        cover_m = re.search(r'"imageList"\s*:\s*\[.*?"url"\s*:\s*"(https?://[^"]+)"', html)
        if cover_m:
            data["cover_url"] = cover_m.group(1)

        # 作者
        author_m = re.search(r'"nickname"\s*:\s*"(.*?)"', html)
        if author_m:
            data["author"] = author_m.group(1)

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
