"""快手解析器 — 纯 HTTP 版（无 Playwright）"""
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

        # 方式1: 通过移动端页面提取 __NEXT_DATA__
        result = self._parse_mobile_page(real_url)
        if result.get("video_url"):
            return result

        # 方式2: 通过 PC 页面静态提取
        result = self._parse_static(real_url)
        if result.get("video_url"):
            return result

        # 方式3: 尝试快手 API
        if photo_id:
            result = self._parse_api(photo_id)
            if result.get("video_url"):
                return result

        raise RuntimeError("无法解析该快手链接，可能需要登录或视频已删除")

    def _parse_mobile_page(self, url: str) -> dict:
        """用移动端 UA 请求，提取 __NEXT_DATA__ 中的视频信息"""
        headers = {
            **self.HEADERS,
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                          "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
            "Referer": "https://www.kuaishou.com/",
        }
        try:
            resp = requests.get(url, headers=headers, timeout=15, allow_redirects=True)
            html = resp.text
            return self._extract_from_html(html)
        except Exception:
            return {}

    def _parse_static(self, url: str) -> dict:
        headers = {**self.HEADERS, "Referer": "https://www.kuaishou.com/"}
        try:
            resp = requests.get(url, headers=headers, timeout=15)
            return self._extract_from_html(resp.text)
        except Exception:
            return {}

    def _extract_from_html(self, html: str) -> dict:
        data = {"platform": "快手"}

        # 提取 __NEXT_DATA__
        m = re.search(r'id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
        if m:
            try:
                nd = json.loads(m.group(1))
                props = nd.get("props", {}).get("pageProps", {})
                photo = props.get("photo", props.get("videoInfo", {}))
                if photo:
                    data["title"] = photo.get("caption", photo.get("title", ""))
                    data["author"] = photo.get("userName", photo.get("author", ""))
                    cover = photo.get("coverUrl", photo.get("webpCoverUrl", ""))
                    if cover:
                        data["cover_url"] = cover.replace("\\u002F", "/")
                    for key in ["playUrl", "videoUrl", "webp_video_url", "photoUrl"]:
                        v = photo.get(key)
                        if v:
                            data["video_url"] = v.replace("\\u002F", "/")
                            break
                    return data
            except Exception:
                pass

        # 正则提取
        title_m = re.search(r'<title[^>]*>(.*?)</title>', html, re.S)
        if title_m:
            t = title_m.group(1).strip().replace(" - 快手", "").strip()
            if t:
                data["title"] = t

        for p in [r'"playUrl"\s*:\s*"(https?://[^"]+)"',
                  r'"videoUrl"\s*:\s*"(https?://[^"]+)"',
                  r'"photoUrl"\s*:\s*"(https?://[^"]+)"']:
            vm = re.search(p, html)
            if vm:
                data["video_url"] = vm.group(1).replace("\\u002F", "/").replace("\\/", "/")
                break

        cover_m = re.search(r'"coverUrl"\s*:\s*"(https?://[^"]+)"', html)
        if cover_m:
            data["cover_url"] = cover_m.group(1).replace("\\u002F", "/")
        author_m = re.search(r'"userName"\s*:\s*"(.*?)"', html)
        if author_m:
            data["author"] = author_m.group(1)

        return data

    def _parse_api(self, photo_id: str) -> dict:
        """尝试通过快手内部 API 获取视频信息"""
        api_url = "https://www.kuaishou.com/graphql"
        headers = {
            **self.HEADERS,
            "Content-Type": "application/json",
            "Referer": f"https://www.kuaishou.com/short-video/{photo_id}",
            "Origin": "https://www.kuaishou.com",
        }
        payload = {
            "operationName": "visionVideoDetail",
            "variables": {"photoId": photo_id, "page": "detail"},
            "query": "query visionVideoDetail($photoId: String, $type: String, $page: String) {"
                     "visionVideoDetail(photoId: $photoId, type: $type, page: $page) {"
                     "photo { id caption photoUrl coverUrl animatedCoverUrl duration "
                     "author { id name headerUrl } "
                     "videoUrl webpCoverUrl } } }"
        }
        try:
            resp = requests.post(api_url, json=payload, headers=headers, timeout=15)
            result = resp.json()
            photo = result.get("data", {}).get("visionVideoDetail", {}).get("photo", {})
            if photo:
                data = {
                    "platform": "快手",
                    "title": photo.get("caption", ""),
                    "author": photo.get("author", {}).get("name", ""),
                    "cover_url": photo.get("coverUrl", photo.get("webpCoverUrl", "")),
                }
                video_url = photo.get("videoUrl") or photo.get("photoUrl")
                if video_url:
                    data["video_url"] = video_url
                return data
        except Exception:
            pass
        return {}

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
