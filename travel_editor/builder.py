"""把素材编排成有旅行叙事感的时间线，并把总时长控制在目标范围内。

本模块只产出“计划” (SegmentPlan) ，不真正渲染视频帧；渲染在 clips.py 完成。
这样可以先把节奏 / 时长算准，再统一渲染。
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import List, Optional

from . import config
from .scanner import Library, Material
from .utils import get_logger

log = get_logger()


@dataclass
class SegmentPlan:
    index: int
    material: Material
    kind: str                       # "video" | "photo"
    duration: float
    fit_mode: str
    role: str                       # "opening" | "middle" | "ending"
    source_start: float = 0.0       # 视频在源文件中的起点
    subtitle: Optional[str] = None
    repeated: bool = False          # 是否为重复使用的素材
    zoom_in: bool = True            # 照片运镜方向


# ---------------------------------------------------------------------------
def _rand_video_dur(rng: random.Random, src_dur: float) -> float:
    hi = min(config.VIDEO_SEG_MAX, max(config.VIDEO_SEG_MIN, src_dur))
    lo = min(config.VIDEO_SEG_MIN, hi)
    return round(rng.uniform(lo, hi), 2)


def _pick_video_start(rng: random.Random, src_dur: float, seg_dur: float,
                      avoid: Optional[float] = None) -> float:
    """在源视频里选一个起点，尽量避开开头一点点；avoid 用于重复使用时换片段。"""
    head = min(0.3, max(0.0, src_dur - seg_dur))
    latest = max(head, src_dur - seg_dur)
    if latest <= head:
        return round(head, 2)
    start = rng.uniform(head, latest)
    if avoid is not None and abs(start - avoid) < seg_dur:
        # 尽量挪到另一半，减少重复感
        start = head if avoid > (head + latest) / 2 else latest
    return round(start, 2)


def timeline_duration(segs: List[SegmentPlan]) -> float:
    """考虑交叉溶解重叠后的最终成片时长。"""
    if not segs:
        return 0.0
    total = sum(s.duration for s in segs)
    total -= config.CROSSFADE * (len(segs) - 1)
    return max(0.0, round(total, 2))


# ---------------------------------------------------------------------------
def _build_initial(lib: Library, rng: random.Random) -> List[SegmentPlan]:
    videos = list(lib.videos)
    photos = list(lib.photos)
    rng.shuffle(videos)
    rng.shuffle(photos)

    # 选开场（优先视频，抓人）与结尾（优先视频，回忆感）
    opening_mat = videos.pop(0) if videos else (photos.pop(0) if photos else None)
    ending_mat = None
    if videos:
        ending_mat = videos.pop()
    elif photos:
        ending_mat = photos.pop()

    # 中间：视频与照片交替，营造节奏
    middle: List[Material] = []
    vi, pi = 0, 0
    while vi < len(videos) or pi < len(photos):
        if vi < len(videos):
            middle.append(videos[vi]); vi += 1
        if pi < len(photos):
            middle.append(photos[pi]); pi += 1

    ordered: List[tuple] = []
    if opening_mat:
        ordered.append((opening_mat, "opening"))
    ordered.extend((m, "middle") for m in middle)
    if ending_mat:
        ordered.append((ending_mat, "ending"))

    segs: List[SegmentPlan] = []
    for i, (mat, role) in enumerate(ordered):
        if mat.kind == "video":
            dur = _rand_video_dur(rng, mat.duration)
            start = _pick_video_start(rng, mat.duration, dur)
            fit = config.VIDEO_FIT_MODE if mat.orientation == "landscape" else "crop"
            segs.append(SegmentPlan(index=i, material=mat, kind="video",
                                    duration=dur, fit_mode=fit, role=role,
                                    source_start=start))
        else:
            dur = round(rng.uniform(config.PHOTO_DUR_MIN, config.PHOTO_DUR_MAX), 2)
            fit = config.PHOTO_FIT_MODE if mat.orientation == "landscape" else "crop"
            segs.append(SegmentPlan(index=i, material=mat, kind="photo",
                                    duration=dur, fit_mode=fit, role=role,
                                    zoom_in=bool(rng.getrandbits(1))))
    return segs


def _assign_subtitles(segs: List[SegmentPlan], title: Optional[str]) -> None:
    if not segs:
        return
    segs[0].subtitle = title or config.OPENING_SUBTITLE
    segs[0].role = "opening" if segs[0].role != "ending" else segs[0].role
    if len(segs) > 1:
        segs[-1].subtitle = config.ENDING_SUBTITLE

    middle = [s for s in segs if s.role == "middle"]
    if not middle or not config.MIDDLE_SUBTITLES:
        return
    # 稀疏分布中间字幕
    n_sub = min(len(config.MIDDLE_SUBTITLES), max(1, len(middle) // 3))
    if n_sub == 0:
        return
    step = max(1, len(middle) // (n_sub + 1))
    for k in range(n_sub):
        idx = min(len(middle) - 1, step * (k + 1))
        middle[idx].subtitle = config.MIDDLE_SUBTITLES[k]


def _extend_photos(segs: List[SegmentPlan], need: float) -> float:
    """延长照片展示时间来补足时长，返回仍缺多少秒。"""
    photos = [s for s in segs if s.kind == "photo"
              and s.duration < config.PHOTO_DUR_EXTENDED]
    for s in photos:
        if need <= 0:
            break
        room = config.PHOTO_DUR_EXTENDED - s.duration
        add = min(room, need)
        s.duration = round(s.duration + add, 2)
        need -= add
    return round(need, 2)


def _repeat_materials(segs: List[SegmentPlan], lib: Library,
                      rng: random.Random, need: float) -> float:
    """重复使用高质量素材来补足时长，插入到中部，避免与相邻重复。"""
    quality = sorted(lib.videos + lib.photos,
                     key=lambda m: (m.width * m.height, m.duration),
                     reverse=True)
    if not quality:
        return need

    guard = 0
    while need > 0 and guard < 200:
        guard += 1
        mat = quality[guard % len(quality)]
        # 找一个不与左右相邻同源的插入位置（中部）
        insert_at = len(segs) // 2 + rng.randint(-1, 1)
        insert_at = max(1, min(len(segs) - 1, insert_at))
        left = segs[insert_at - 1].material.path if insert_at - 1 >= 0 else None
        right = segs[insert_at].material.path if insert_at < len(segs) else None
        if mat.path in (left, right):
            continue

        if mat.kind == "video":
            dur = _rand_video_dur(rng, mat.duration)
            start = _pick_video_start(rng, mat.duration, dur, avoid=0.0)
            fit = config.VIDEO_FIT_MODE if mat.orientation == "landscape" else "crop"
            seg = SegmentPlan(index=-1, material=mat, kind="video", duration=dur,
                              fit_mode=fit, role="middle", source_start=start,
                              repeated=True)
        else:
            dur = round(rng.uniform(config.PHOTO_DUR_MIN, config.PHOTO_DUR_EXTENDED), 2)
            fit = config.PHOTO_FIT_MODE if mat.orientation == "landscape" else "crop"
            seg = SegmentPlan(index=-1, material=mat, kind="photo", duration=dur,
                              fit_mode=fit, role="middle",
                              zoom_in=bool(rng.getrandbits(1)), repeated=True)
        segs.insert(insert_at, seg)
        # 插入一段，净增加 = dur - crossfade
        need -= max(0.1, dur - config.CROSSFADE)
    return round(need, 2)


def _shrink(segs: List[SegmentPlan], over: float) -> float:
    """超时：先压缩各片段到下限，再丢弃部分中间片段。"""
    # 1) 压缩时长
    for s in segs:
        if over <= 0:
            break
        floor = config.VIDEO_SEG_MIN if s.kind == "video" else config.PHOTO_DUR_MIN
        room = s.duration - floor
        if room > 0:
            cut = min(room, over)
            s.duration = round(s.duration - cut, 2)
            over -= cut
    # 2) 丢弃中间片段（保留开场与结尾）
    while over > 0 and len(segs) > 2:
        middle_idx = [i for i, s in enumerate(segs) if s.role == "middle"]
        if not middle_idx:
            break
        drop = middle_idx[len(middle_idx) // 2]
        removed = segs.pop(drop)
        over -= max(0.1, removed.duration - config.CROSSFADE)
    return round(over, 2)


def build_timeline(lib: Library, rng: random.Random,
                   title: Optional[str] = None) -> List[SegmentPlan]:
    if not lib.has_any:
        raise RuntimeError("input/videos 与 input/photos 均无可用素材，无法生成视频。")

    segs = _build_initial(lib, rng)
    target = config.TARGET_DURATION
    tol = config.DURATION_TOLERANCE

    cur = timeline_duration(segs)
    log.info("初始时间线: %d 段, 约 %.1f 秒 (目标 %.0f±%.0f)",
             len(segs), cur, target, tol)

    if cur < target - tol:
        need = target - cur
        need = _extend_photos(segs, need)
        if need > 0:
            need = _repeat_materials(segs, lib, rng, need)
        log.info("素材不足，已延长照片/复用素材补足 (剩余缺口 %.1f 秒)", max(0, need))
    elif cur > target + tol:
        over = cur - target
        over = _shrink(segs, over)
        log.info("素材偏多，已压缩/删减片段 (剩余超出 %.1f 秒)", max(0, over))

    # 重新编号 + 分配字幕
    for i, s in enumerate(segs):
        s.index = i
    _assign_subtitles(segs, title)

    final = timeline_duration(segs)
    log.info("最终时间线: %d 段, 约 %.1f 秒", len(segs), final)
    if abs(final - target) > tol:
        log.warning("成片时长 %.1f 秒超出目标范围，可能是素材太少或太多。", final)
    return segs
