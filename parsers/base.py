"""基础解析器接口"""
import os
import re
import time
import requests


class BaseParser:
    """视频解析器基类"""
    name = "base"
    domains = []

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }

    def match(self, url: str) -> bool:
        """判断是否能处理该 URL"""
        return any(d in url for d in self.domains)

    def parse(self, url: str) -> dict:
        """
        解析链接，返回:
        {
            "title": "标题",
            "video_url": "视频直链(可能为None)",
            "audio_url": "音频直链(可能为None)",
            "cover_url": "封面URL(可选)",
            "platform": "平台名",
            "author": "作者(可选)",
        }
        """
        raise NotImplementedError

    @staticmethod
    def safe_filename(name: str, max_len: int = 80) -> str:
        """生成安全文件名"""
        name = re.sub(r'[\\/:*?"<>|\n\r\t]', '_', name)
        name = re.sub(r'_+', '_', name).strip('_. ')
        return name[:max_len] if name else f"video_{int(time.time())}"

    @staticmethod
    def download_file(url: str, save_path: str, headers: dict = None, chunk_size: int = 8192) -> str:
        """下载文件到本地"""
        h = {**BaseParser.HEADERS, **(headers or {})}
        resp = requests.get(url, headers=h, stream=True, timeout=60)
        resp.raise_for_status()
        with open(save_path, 'wb') as f:
            for chunk in resp.iter_content(chunk_size):
                if chunk:
                    f.write(chunk)
        return save_path
