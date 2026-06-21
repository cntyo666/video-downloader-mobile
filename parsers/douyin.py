"""抖音/TikTok 解析器"""
import re
import requests
from .base import BaseParser


class DouyinParser(BaseParser):
    name = "抖音"
    domains = ["douyin.com", "iesdouyin.com", "tiktok.com", "vm.tiktok.com", "v.douyin.com"]

    def parse(self, url: str) -> dict:
        # 跟踪重定向获取真实 URL
        real_url = self._follow_redirect(url)
        video_id = self._extract_id(real_url)
        if not video_id:
            raise ValueError(f"无法从 URL 提取视频 ID: {real_url}")

        # 获取页面数据
        return self._fetch_video_data(real_url, video_id)

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
        patterns = [
            r'/video/(\d+)',
            r'/note/(\d+)',
            r'video/(\d+)',
            r'itemId=(\d+)',
        ]
        for p in patterns:
            m = re.search(p, url)
            if m:
                return m.group(1)
        return ""

    def _fetch_video_data(self, url: str, video_id: str) -> dict:
        # 尝试多种方式获取无水印视频
        methods = [
            self._method_share_page,
            self._method_web_api,
        ]
        for method in methods:
            try:
                result = method(url, video_id)
                if result and result.get("video_url"):
                    return result
            except Exception:
                continue

        # fallback: 返回基本信息
        return {
            "title": f"抖音_{video_id}",
            "video_url": None,
            "audio_url": None,
            "cover_url": None,
            "platform": "抖音",
        }

    def _method_share_page(self, url: str, video_id: str) -> dict:
        """通过分享页获取数据"""
        share_url = f"https://www.iesdouyin.com/share/video/{video_id}/"
        headers = {**self.HEADERS, "Referer": "https://www.douyin.com/"}
        resp = requests.get(share_url, headers=headers, timeout=15)
        html = resp.text

        data = {"platform": "抖音"}

        # 提取标题
        title_m = re.search(r'<title[^>]*>(.*?)</title>', html, re.S)
        if title_m:
            data["title"] = title_m.group(1).strip().replace(' - 抖音', '').strip()

        # 提取视频 URL（无水印）
        video_patterns = [
            r'"playApi"\s*:\s*"(https?://[^"]+)"',
            r'"play_addr"\s*:\s*\{[^}]*"url_list"\s*:\s*\["(https?://[^"]+)"',
            r'"download_addr"\s*:\s*\{[^}]*"url_list"\s*:\s*\["(https?://[^"]+)"',
            r'src="(https?://[^"]*\.mp4[^"]*)"',
        ]
        for p in video_patterns:
            m = re.search(p, html)
            if m:
                data["video_url"] = m.group(1).replace('\\u002F', '/').replace('\\/', '/')
                break

        # 封面
        cover_m = re.search(r'"cover"\s*:\s*\{[^}]*"url_list"\s*:\s*\["(https?://[^"]+)"', html)
        if cover_m:
            data["cover_url"] = cover_m.group(1).replace('\\u002F', '/').replace('\\/', '/')

        return data

    def _method_web_api(self, url: str, video_id: str) -> dict:
        """通过 Web API 获取"""
        api_url = f"https://www.douyin.com/aweme/v1/web/aweme/detail/?aweme_id={video_id}"
        headers = {
            **self.HEADERS,
            "Referer": "https://www.douyin.com/",
            "Cookie": "msToken=xxx",
        }
        resp = requests.get(api_url, headers=headers, timeout=15)
        if resp.status_code != 200:
            return {}

        data = resp.json()
        detail = data.get("aweme_detail", {})
        if not detail:
            return {}

        result = {
            "title": detail.get("desc", ""),
            "platform": "抖音",
            "author": detail.get("author", {}).get("nickname", ""),
        }

        # 视频 URL
        video = detail.get("video", {})
        play_addr = video.get("play_addr", {})
        url_list = play_addr.get("url_list", [])
        if url_list:
            result["video_url"] = url_list[0]

        # 封面
        cover = video.get("cover", {})
        cover_list = cover.get("url_list", [])
        if cover_list:
            result["cover_url"] = cover_list[0]

        return result
