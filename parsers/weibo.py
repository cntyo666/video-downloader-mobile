"""微博解析器"""
import re
import requests
from .base import BaseParser


class WeiboParser(BaseParser):
    name = "微博"
    domains = ["weibo.com", "m.weibo.cn"]

    def parse(self, url: str) -> dict:
        headers = {**self.HEADERS, "Referer": "https://weibo.com/"}
        resp = requests.get(url, headers=headers, timeout=15)
        html = resp.text

        data = {"platform": "微博"}

        # 标题
        title_m = re.search(r'<title[^>]*>(.*?)</title>', html, re.S)
        if title_m:
            data["title"] = title_m.group(1).strip()

        # 视频 URL
        video_patterns = [
            r'"stream_url"\s*:\s*"(https?://[^"]+)"',
            r'"stream_url_hd"\s*:\s*"(https?://[^"]+)"',
            r'"url"\s*:\s*"(https?://[^"]*\.mp4[^"]*)"',
            r'data-src="(https?://[^"]*\.mp4[^"]*)"',
        ]
        for p in video_patterns:
            m = re.search(p, html)
            if m:
                data["video_url"] = m.group(1).replace('\\/', '/')
                break

        return data
