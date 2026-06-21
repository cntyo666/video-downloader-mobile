"""通用解析器 (yt-dlp 兜底)"""
import subprocess
import json
import shutil
from .base import BaseParser


class GenericParser(BaseParser):
    name = "通用(yt-dlp)"
    domains = []  # 兜底，匹配所有

    def match(self, url: str) -> bool:
        # 作为兜底，始终返回 True
        return True

    def parse(self, url: str) -> dict:
        ytdlp = shutil.which("yt-dlp")
        if not ytdlp:
            raise RuntimeError("yt-dlp 未安装，请运行: pip install yt-dlp")

        # 获取视频信息
        cmd = [ytdlp, "--dump-json", "--no-download", url]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60, encoding='utf-8', errors='replace')
        if result.returncode != 0:
            raise RuntimeError(f"yt-dlp 解析失败: {result.stderr[:500]}")

        info = json.loads(result.stdout)

        return {
            "title": info.get("title", ""),
            "video_url": info.get("url") or self._best_format_url(info),
            "audio_url": None,
            "cover_url": info.get("thumbnail"),
            "platform": info.get("extractor", "未知"),
            "author": info.get("uploader", ""),
        }

    def _best_format_url(self, info: dict) -> str:
        formats = info.get("formats", [])
        if not formats:
            return ""
        # 选最高质量的
        best = max(formats, key=lambda f: f.get("height", 0) or 0)
        return best.get("url", "")
