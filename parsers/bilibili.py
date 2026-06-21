"""B站解析器"""
import re
import requests
from .base import BaseParser


class BilibiliParser(BaseParser):
    name = "B站"
    domains = ["bilibili.com", "b23.tv"]

    def parse(self, url: str) -> dict:
        real_url = self._follow_redirect(url)
        bvid = self._extract_bvid(real_url)
        if not bvid:
            raise ValueError(f"无法提取 BV号: {real_url}")

        # 获取视频信息
        api_url = f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}"
        headers = {**self.HEADERS, "Referer": "https://www.bilibili.com/"}
        resp = requests.get(api_url, headers=headers, timeout=15)
        data = resp.json()

        if data.get("code") != 0:
            raise ValueError(f"B站 API 错误: {data.get('message', 'unknown')}")

        info = data["data"]
        result = {
            "title": info.get("title", f"B站_{bvid}"),
            "video_url": None,
            "audio_url": None,
            "cover_url": info.get("pic", ""),
            "platform": "B站",
            "author": info.get("owner", {}).get("name", ""),
        }

        # 获取视频流地址
        cid = info.get("cid")
        if cid:
            play_api = f"https://api.bilibili.com/x/player/playurl?bvid={bvid}&cid={cid}&qn=80&fnval=16"
            resp2 = requests.get(play_api, headers=headers, timeout=15)
            play_data = resp2.json()
            if play_data.get("code") == 0:
                dash = play_data.get("data", {}).get("dash")
                if dash:
                    # 取第一个视频流
                    videos = dash.get("video", [])
                    if videos:
                        result["video_url"] = videos[0].get("baseUrl") or videos[0].get("base_url")
                    audios = dash.get("audio", [])
                    if audios:
                        result["audio_url"] = audios[0].get("baseUrl") or audios[0].get("base_url")
                else:
                    # 普通模式
                    durl = play_data.get("data", {}).get("durl", [])
                    if durl:
                        result["video_url"] = durl[0].get("url", "")

        return result

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

    def _extract_bvid(self, url: str) -> str:
        m = re.search(r'(BV\w{10})', url)
        return m.group(1) if m else ""
