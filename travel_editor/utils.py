"""通用工具：日志、字体探测、竖屏适配（裁切 / 模糊背景）、字幕图片生成。"""

from __future__ import annotations

import logging
import os
from typing import List, Optional, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from moviepy.editor import CompositeVideoClip, ImageClip
from moviepy.video.fx.resize import resize as fx_resize
from moviepy.video.fx.crop import crop as fx_crop
from moviepy.video.fx.colorx import colorx as fx_colorx

from . import config


# ---------------------------------------------------------------------------
# 日志
# ---------------------------------------------------------------------------
def get_logger(name: str = "travel_editor") -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("[%(levelname)s] %(message)s")
        )
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


log = get_logger()


# ---------------------------------------------------------------------------
# 字体
# ---------------------------------------------------------------------------
def find_font(custom: Optional[str] = None) -> Optional[str]:
    """返回第一个可用的中文字体路径，找不到则返回 None。"""
    candidates: List[str] = []
    if custom:
        candidates.append(custom)
    candidates.extend(config.FONT_CANDIDATES)
    for path in candidates:
        if path and os.path.isfile(path):
            return path
    return None


def load_font(font_path: Optional[str], size: int) -> Optional[ImageFont.FreeTypeFont]:
    """加载 TrueType 中文字体；找不到则返回 None（此时自动跳过字幕，不报错）。"""
    if font_path and os.path.isfile(font_path):
        try:
            return ImageFont.truetype(font_path, size)
        except Exception as exc:  # noqa: BLE001
            log.warning("加载字体失败 %s: %s", font_path, exc)
    log.warning("未找到中文字体，本次将不渲染字幕。"
                "请用 --font 指定一个中文字体文件 (如 C:\\Windows\\Fonts\\msyh.ttc)。")
    return None


# ---------------------------------------------------------------------------
# 竖屏适配
# ---------------------------------------------------------------------------
def _cover_crop(clip, w: int, h: int):
    """等比缩放到铺满 (w, h)，再居中裁切，画面不变形。"""
    scale = max(w / clip.w, h / clip.h)
    resized = fx_resize(clip, newsize=(round(clip.w * scale),
                                       round(clip.h * scale)))
    return fx_crop(resized, width=w, height=h,
                   x_center=resized.w / 2, y_center=resized.h / 2)


def fit_vertical_crop(clip, w: int = config.TARGET_W, h: int = config.TARGET_H):
    """居中裁切铺满竖屏。"""
    return _cover_crop(clip, w, h)


def fit_vertical_blur(clip, w: int = config.TARGET_W, h: int = config.TARGET_H):
    """模糊背景填充竖屏：完整前景居中，背景为放大模糊的同一画面。"""
    # 背景：先大幅降采样（产生模糊效果，且非常快），再铺满裁切，并压暗。
    small_w = max(2, w // config.BLUR_DOWNSCALE)
    small_h = max(2, h // config.BLUR_DOWNSCALE)
    bg = fx_resize(clip, newsize=(small_w, small_h))
    bg = _cover_crop(bg, w, h)
    bg = fx_colorx(bg, config.BG_DARKEN)

    # 前景：等比缩放到“contain”（完整放进画面），居中。
    scale = min(w / clip.w, h / clip.h)
    fg = fx_resize(clip, newsize=(round(clip.w * scale),
                                  round(clip.h * scale)))

    comp = CompositeVideoClip([bg.set_position("center"),
                               fg.set_position("center")],
                              size=(w, h))
    return comp


def fit_vertical(clip, mode: str):
    """按 mode 适配竖屏。已经是竖屏且比例接近 9:16 时直接裁切铺满。"""
    if mode == "crop":
        return fit_vertical_crop(clip)
    return fit_vertical_blur(clip)


def is_landscape(w: int, h: int) -> bool:
    return w >= h


# ---------------------------------------------------------------------------
# 字幕（用 PIL 生成 RGBA 图片，避免依赖 ImageMagick，Windows 更稳定）
# ---------------------------------------------------------------------------
def _wrap_text(text: str, font: ImageFont.FreeTypeFont, max_w: int) -> List[str]:
    """按最大宽度对中文文本简单换行。"""
    lines: List[str] = []
    line = ""
    for ch in text:
        test = line + ch
        bbox = font.getbbox(test)
        if (bbox[2] - bbox[0]) > max_w and line:
            lines.append(line)
            line = ch
        else:
            line = test
    if line:
        lines.append(line)
    return lines


def make_subtitle_image(text: str,
                        font: ImageFont.FreeTypeFont,
                        canvas_w: int = config.TARGET_W,
                        canvas_h: int = config.TARGET_H) -> np.ndarray:
    """生成与画面等大的透明 RGBA 字幕图（含轻微阴影），返回 numpy 数组。"""
    img = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    max_text_w = int(canvas_w * 0.86)
    lines = _wrap_text(text, font, max_text_w)

    # 计算总高度
    line_heights = []
    line_widths = []
    for ln in lines:
        bbox = font.getbbox(ln)
        line_widths.append(bbox[2] - bbox[0])
        line_heights.append(bbox[3] - bbox[1])
    line_gap = int(max(line_heights) * 0.35) if line_heights else 0
    total_h = sum(line_heights) + line_gap * (len(lines) - 1)

    center_y = int(canvas_h * config.SUBTITLE_Y_RATIO)
    y = center_y - total_h // 2

    sx, sy = config.SUBTITLE_SHADOW_OFFSET
    for i, ln in enumerate(lines):
        x = (canvas_w - line_widths[i]) // 2
        # 阴影
        draw.text((x + sx, y + sy), ln, font=font,
                  fill=config.SUBTITLE_SHADOW)
        # 正文
        draw.text((x, y), ln, font=font, fill=config.SUBTITLE_COLOR)
        y += line_heights[i] + line_gap

    return np.array(img)


def make_subtitle_clip(text: str,
                       duration: float,
                       font: ImageFont.FreeTypeFont):
    """返回一个透明字幕 ImageClip（已设置时长与淡入淡出）。"""
    arr = make_subtitle_image(text, font)
    clip = ImageClip(arr, transparent=True).set_duration(duration)
    fade = min(config.SUBTITLE_FADE, duration / 3.0)
    if fade > 0:
        clip = clip.crossfadein(fade).crossfadeout(fade)
    return clip
