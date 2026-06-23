"""全局参数配置。

所有可调参数集中在这里，方便用户调整。也可以通过命令行参数覆盖部分配置
（见 make_travel_video.py）。
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List


# ---------------------------------------------------------------------------
# 输出视频规格
# ---------------------------------------------------------------------------
TARGET_W = 1080            # 输出宽度
TARGET_H = 1920            # 输出高度 (9:16 竖屏)
FPS = 30                   # 输出帧率
VIDEO_CODEC = "libx264"    # H.264
AUDIO_CODEC = "aac"
AUDIO_FPS = 44100          # 音频采样率
VIDEO_BITRATE = "8000k"    # 画质，可按需调高/调低


# ---------------------------------------------------------------------------
# 时长控制（单位：秒）
# ---------------------------------------------------------------------------
TARGET_DURATION = 90.0     # 目标总时长
DURATION_TOLERANCE = 5.0   # 允许误差 ±5 秒

VIDEO_SEG_MIN = 2.0        # 视频片段最短
VIDEO_SEG_MAX = 5.0        # 视频片段最长
PHOTO_DUR_MIN = 2.0        # 照片最短展示
PHOTO_DUR_MAX = 3.0        # 照片最长展示（不足时长时可延长到 PHOTO_DUR_EXTENDED）
PHOTO_DUR_EXTENDED = 6.0   # 素材不足时照片可延长到的最大值


# ---------------------------------------------------------------------------
# 转场
# ---------------------------------------------------------------------------
CROSSFADE = 0.6            # 交叉溶解 / 淡入淡出时长
OPENING_FADEIN = 0.8       # 整片开场黑场淡入
ENDING_FADEOUT = 1.2       # 整片结尾黑场淡出


# ---------------------------------------------------------------------------
# 画面适配方式
#   "blur"  -> 模糊背景填充（保留完整画面，推荐，速度快用的是降采样模糊）
#   "crop"  -> 居中裁切铺满（更有冲击力，但会裁掉两侧内容）
# 二者都不会让画面变形。
# ---------------------------------------------------------------------------
VIDEO_FIT_MODE = "blur"
PHOTO_FIT_MODE = "blur"
BLUR_DOWNSCALE = 22        # 模糊背景降采样倍数，越大越模糊、越快
BG_DARKEN = 0.55           # 背景压暗系数 (0-1)，越小越暗，突出前景


# ---------------------------------------------------------------------------
# 照片运镜（Ken Burns 推拉缩放）
# ---------------------------------------------------------------------------
KEN_BURNS_ZOOM = 0.10      # 缩放幅度（10%）


# ---------------------------------------------------------------------------
# 音频
# ---------------------------------------------------------------------------
MUSIC_VOLUME = 0.85        # 背景音乐音量
ENV_VOLUME = 0.18          # 原视频环境声音量（保留较低音量）
MUSIC_FADEIN = 1.0         # 音乐开头淡入
MUSIC_FADEOUT = 2.0        # 音乐结尾淡出


# ---------------------------------------------------------------------------
# 字幕
# ---------------------------------------------------------------------------
SUBTITLE_FONT_SIZE = 58
SUBTITLE_COLOR = (255, 255, 255, 255)       # 白色
SUBTITLE_SHADOW = (0, 0, 0, 150)            # 轻微阴影（半透明黑）
SUBTITLE_SHADOW_OFFSET = (2, 3)
SUBTITLE_Y_RATIO = 0.80    # 字幕中心相对高度（0.80 ≈ 下三分之一，不遮挡主体）
SUBTITLE_FADE = 0.5        # 字幕淡入淡出

# 候选中文字体路径（按顺序探测，找到第一个可用的）。可在命令行用 --font 覆盖。
FONT_CANDIDATES: List[str] = [
    r"C:\Windows\Fonts\msyh.ttc",      # 微软雅黑
    r"C:\Windows\Fonts\msyhbd.ttc",    # 微软雅黑 Bold
    r"C:\Windows\Fonts\simhei.ttf",    # 黑体
    r"C:\Windows\Fonts\simsun.ttc",    # 宋体
    r"C:\Windows\Fonts\STHeiti Medium.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",   # Linux 备用
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/System/Library/Fonts/PingFang.ttc",               # macOS 备用
]

# 叙事字幕文案（简洁、不要太多）。可在命令行用 --title 覆盖开场标题。
# opening 仅用 1 条，middle 会按片段位置稀疏出现，ending 用 1 条。
OPENING_SUBTITLE = "出发 · 一段旅程的开始"
MIDDLE_SUBTITLES: List[str] = [
    "沿途的风景",
    "人间烟火气",
    "遇见的人，遇见的光",
    "慢下来的时光",
]
ENDING_SUBTITLE = "愿这段旅程，被温柔记住"


# ---------------------------------------------------------------------------
# 路径
# ---------------------------------------------------------------------------
@dataclass
class Paths:
    root: str = "."
    input_videos: str = field(init=False)
    input_photos: str = field(init=False)
    input_music: str = field(init=False)
    output_dir: str = field(init=False)

    def __post_init__(self) -> None:
        self.input_videos = os.path.join(self.root, "input", "videos")
        self.input_photos = os.path.join(self.root, "input", "photos")
        self.input_music = os.path.join(self.root, "input", "music")
        self.output_dir = os.path.join(self.root, "output")

    def ensure(self) -> None:
        for p in (self.input_videos, self.input_photos,
                  self.input_music, self.output_dir):
            os.makedirs(p, exist_ok=True)


VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm"}
PHOTO_EXTS = {".jpg", ".jpeg", ".png", ".heic", ".bmp", ".webp"}
MUSIC_EXTS = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg"}

OUTPUT_WITH_MUSIC = "final_travel_video.mp4"
OUTPUT_NO_MUSIC = "final_travel_video_no_music.mp4"
OUTPUT_TIMELINE = "timeline.json"
OUTPUT_REPORT = "material_report.csv"
