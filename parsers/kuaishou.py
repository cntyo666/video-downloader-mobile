"""快手解析器 — 纯 HTTP 版（通过移动端页面提取视频）"""
import re
import json
import requests
from .base import BaseParser


class KuaishouParser(BaseParser):
    name = "快手"
    domains = ["kuaishou.com", "gifshow.com", "v.kuaishou.com", "v.m.chenzhongtech.com"]

    def parse(self, url: str) -> dict:
        real_url = self._follow_redirect(url)
        photo_id = self._extract_id(real_url)

        if not photo_id:
            # 尝试从原始 URL 提取
            photo_id = self._extract_id(url)

        if photo_id:
            result = self._parse_mobile(photo_id)
            if result.get("video_url"):
                return result

        # 降级：PC 页面静态提取
        result = self._parse_static(real_url)
        if result.get("video_url"):
            return result

        raise RuntimeError("无法解析该快手链接，可能需要登录或视频已删除")

    def _parse_mobile(self, photo_id: str) -> dict:
        """通过移动端分享页面提取视频"""
        mobile_url = f'https://v.m.chenzhongtech.com/fw/photo/{photo_id}'
        headers = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                          "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 "
                          "Mobile/15E148 Safari/604.1",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }
        try:
            resp = requests.get(mobile_url, headers=headers, timeout=15, allow_redirects=True)
            html = resp.text
            return self._extract_from_mobile_html(html)
        except Exception:
            return {}

    def _extract_from_mobile_html(self, html: str) -> dict:
        """从移动端 HTML 提取视频信息"""
        data = {"platform": "快手"}

        # 标题
        title_m = re.search(r'<title[^>]*>(.*?)</title>', html)
        if title_m:
            title = title_m.group(1).strip()
            title = re.sub(r'\s*[-|].*$', '', title).strip()
            if title:
                data["title"] = title

        # 作者
        author_m = re.search(r'"authorName"\s*:\s*"(.*?)"', html)
        if author_m:
            data["author"] = author_m.group(1)

        # 封面
        cover_m = re.search(r'"coverUrl"\s*:\s*"(https?://[^"]+)"', html)
        if not cover_m:
            cover_m = re.search(r'"webpCoverUrl"\s*:\s*"(https?://[^"]+)"', html)
        if cover_m:
            data["cover_url"] = cover_m.group(1).replace("\\u002F", "/")

        # 视频 URL — 优先从 JSON 字段提取
        video_url = None
        for pattern in [
            r'"playUrl"\s*:\s*"(https?://[^"]+)"',
            r'"videoUrl"\s*:\s*"(https?://[^"]+)"',
            r'"photoUrl"\s*:\s*"(https?://[^"]+)"',
            r'"mainMvUrl"\s*:\s*"(https?://[^"]+)"',
        ]:
            m = re.search(pattern, html)
            if m:
                video_url = m.group(1).replace("\\u002F", "/")
                break

        # 降级：直接找 mp4 链接（排除 blob:）
        if not video_url:
            mp4_urls = [u for u in re.findall(r'(https?://[^"\s]+\.mp4[^"\s]*)', html) if not u.startswith('blob:')]
            if mp4_urls:
                # 优先选高清版（UltraV5 > HighV5 > 默认）
                for u in mp4_urls:
                    if "UltraV5" in u:
                        video_url = u
                        break
                if not video_url:
                    for u in mp4_urls:
                        if "HighV5" in u:
                            video_url = u
                            break
                if not video_url:
                    video_url = mp4_urls[0]

        if video_url:
            data["video_url"] = video_url

        return data

    def _parse_static(self, url: str) -> dict:
        """PC 页面静态提取"""
        headers = {**self.HEADERS, "Referer": "https://www.kuaishou.com/"}
        try:
            resp = requests.get(url, headers=headers, timeout=15)
            html = resp.text
        except Exception:
            return {}

        data = {"platform": "快手"}

        title_m = re.search(r'<title[^>]*>(.*?)</title>', html, re.S)
        if title_m:
            t = title_m.group(1).strip().replace(" - 快手", "").strip()
            if t:
                data["title"] = t

        nd = re.search(r'id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
        if nd:
            try:
                props = json.loads(nd.group(1)).get("props", {}).get("pageProps", {})
                photo = props.get("photo", {})
                if photo:
                    data["title"] = data.get("title") or photo.get("caption", "")
                    data["author"] = photo.get("userName", "")
                    cover = photo.get("coverUrl", photo.get("webpCoverUrl", ""))
                    if cover:
                        data["cover_url"] = cover.replace("\\u002F", "/")
                    for key in ["playUrl", "videoUrl", "photoUrl"]:
                        v = photo.get(key)
                        if v:
                            data["video_url"] = v.replace("\\u002F", "/")
                            break
            except Exception:
                pass

        if not data.get("video_url"):
            for p in [r'"playUrl"\s*:\s*"(https?://[^"]+)"',
                      r'"videoUrl"\s*:\s*"(https?://[^"]+)"']:
                m = re.search(p, html)
                if m:
                    data["video_url"] = m.group(1).replace("\\u002F", "/").replace("\\/", "/")
                    break

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

    def _extract_id(self, url: str) -> str:
        m = re.search(r"/short-video/(\w+)", url) or re.search(r"/photo/(\w+)", url)
        return m.group(1) if m else ""
