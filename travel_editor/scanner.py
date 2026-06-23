"""扫描 input/ 下的素材并探测基本信息。"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List, Optional

from moviepy.editor import AudioFileClip, VideoFileClip
from PIL import Image

from . import config
from .utils import get_logger, is_landscape

log = get_logger()


@dataclass
class Material:
    path: str
    kind: str                 # "video" | "photo"
    width: int = 0
    height: int = 0
    duration: float = 0.0     # 视频时长；照片为 0
    has_audio: bool = False
    orientation: str = ""     # "landscape" | "portrait"
    error: Optional[str] = None

    @property
    def name(self) -> str:
        return os.path.basename(self.path)


@dataclass
class Library:
    videos: List[Material] = field(default_factory=list)
    photos: List[Material] = field(default_factory=list)
    music: List[str] = field(default_factory=list)
    skipped: List[Material] = field(default_factory=list)

    @property
    def has_any(self) -> bool:
        return bool(self.videos or self.photos)


def _list_files(folder: str, exts: set) -> List[str]:
    if not os.path.isdir(folder):
        return []
    out = []
    for fn in sorted(os.listdir(folder)):
        if os.path.splitext(fn)[1].lower() in exts:
            out.append(os.path.join(folder, fn))
    return out


def _probe_video(path: str) -> Material:
    m = Material(path=path, kind="video")
    try:
        with VideoFileClip(path) as clip:
            m.width, m.height = clip.w, clip.h
            m.duration = float(clip.duration or 0.0)
            m.has_audio = clip.audio is not None
        m.orientation = "landscape" if is_landscape(m.width, m.height) else "portrait"
    except Exception as exc:  # noqa: BLE001
        m.error = str(exc)
    return m


def _probe_photo(path: str) -> Material:
    m = Material(path=path, kind="photo")
    try:
        with Image.open(path) as img:
            m.width, m.height = img.size
        m.orientation = "landscape" if is_landscape(m.width, m.height) else "portrait"
    except Exception as exc:  # noqa: BLE001
        m.error = str(exc)
    return m


def scan(paths: config.Paths) -> Library:
    lib = Library()

    for p in _list_files(paths.input_videos, config.VIDEO_EXTS):
        m = _probe_video(p)
        if m.error or m.duration <= 0:
            log.warning("跳过无法读取的视频: %s (%s)", m.name, m.error or "时长为0")
            lib.skipped.append(m)
        else:
            lib.videos.append(m)

    for p in _list_files(paths.input_photos, config.PHOTO_EXTS):
        m = _probe_photo(p)
        if m.error:
            log.warning("跳过无法读取的照片: %s (%s)", m.name, m.error)
            lib.skipped.append(m)
        else:
            lib.photos.append(m)

    for p in _list_files(paths.input_music, config.MUSIC_EXTS):
        # 仅做存在性记录，真正加载在 audio 阶段
        try:
            with AudioFileClip(p) as a:
                _ = a.duration
            lib.music.append(p)
        except Exception as exc:  # noqa: BLE001
            log.warning("跳过无法读取的音乐: %s (%s)", os.path.basename(p), exc)

    log.info("扫描完成: 视频 %d 个, 照片 %d 张, 音乐 %d 个, 跳过 %d 个",
             len(lib.videos), len(lib.photos), len(lib.music), len(lib.skipped))
    return lib
