"""把 SegmentPlan 渲染成 MoviePy 片段，并拼接成完整画面（含转场、字幕）。"""

from __future__ import annotations

from typing import List

from moviepy.editor import (CompositeVideoClip, ImageClip, VideoFileClip,
                            concatenate_videoclips)

from . import config
from .builder import SegmentPlan
from .utils import fit_vertical, get_logger, make_subtitle_clip

log = get_logger()


def _ken_burns(clip, duration: float, zoom_in: bool):
    """对（已适配竖屏的）画面施加轻微推拉缩放，避免照片静止。"""
    z = config.KEN_BURNS_ZOOM

    def scale(t):
        p = t / duration if duration > 0 else 0.0
        return (1.0 + z * p) if zoom_in else (1.0 + z * (1.0 - p))

    zoomed = clip.resize(scale)
    return CompositeVideoClip([zoomed.set_position("center")],
                              size=(config.TARGET_W, config.TARGET_H))


def _build_video_segment(plan: SegmentPlan):
    src = VideoFileClip(plan.material.path)
    start = max(0.0, plan.source_start)
    end = min(src.duration, start + plan.duration)
    if end - start < 0.1:               # 源太短，退而用整段
        start, end = 0.0, src.duration
    sub = src.subclip(start, end)
    audio = sub.audio                   # 先保留原始环境声
    visual = fit_vertical(sub, plan.fit_mode)
    visual = visual.set_duration(sub.duration).set_audio(audio)
    return visual


def _build_photo_segment(plan: SegmentPlan):
    img = ImageClip(plan.material.path).set_duration(plan.duration)
    fitted = fit_vertical(img, plan.fit_mode).set_duration(plan.duration)
    return _ken_burns(fitted, plan.duration, plan.zoom_in).set_duration(plan.duration)


def build_segment_clip(plan: SegmentPlan, font):
    """渲染单个片段：适配竖屏 + 运镜 + 字幕。"""
    if plan.kind == "video":
        visual = _build_video_segment(plan)
    else:
        visual = _build_photo_segment(plan)

    visual = visual.set_fps(config.FPS)

    if plan.subtitle and font is not None:
        sub_clip = make_subtitle_clip(plan.subtitle, visual.duration, font)
        audio = visual.audio
        visual = CompositeVideoClip([visual, sub_clip.set_position("center")],
                                    size=(config.TARGET_W, config.TARGET_H))
        visual = visual.set_audio(audio).set_duration(plan.duration)
    return visual


def build_movie(plans: List[SegmentPlan], font):
    """拼接所有片段：交叉溶解转场 + 整片淡入淡出。"""
    clips = []
    for i, plan in enumerate(plans):
        clip = build_segment_clip(plan, font)
        if i > 0:
            clip = clip.crossfadein(config.CROSSFADE)
        clips.append(clip)
        log.info("  片段 %02d/%d  %-7s %.2fs  %s%s",
                 i + 1, len(plans), plan.kind, plan.duration,
                 plan.material.name, "  [复用]" if plan.repeated else "")

    movie = concatenate_videoclips(clips, method="compose",
                                   padding=-config.CROSSFADE)
    movie = movie.fadein(config.OPENING_FADEIN).fadeout(config.ENDING_FADEOUT)
    movie = movie.set_fps(config.FPS)
    return movie
