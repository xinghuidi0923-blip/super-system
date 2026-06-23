"""渲染最终视频并导出 timeline.json 与 material_report.csv。"""

from __future__ import annotations

import csv
import json
import os
import subprocess
from typing import List

from imageio_ffmpeg import get_ffmpeg_exe

from . import config
from .audio import build_music, lower_env_audio, mix_with_music
from .builder import SegmentPlan
from .scanner import Library
from .utils import get_logger

log = get_logger()


def _segment_starts(plans: List[SegmentPlan]) -> List[float]:
    """计算每个片段在成片中的起始时间（考虑交叉溶解重叠）。"""
    starts = []
    t = 0.0
    for i, p in enumerate(plans):
        starts.append(round(t, 2))
        t += p.duration - (config.CROSSFADE if i < len(plans) - 1 else 0.0)
    return starts


def export_timeline(plans: List[SegmentPlan], out_path: str,
                    total_duration: float) -> None:
    starts = _segment_starts(plans)
    data = {
        "output": {
            "width": config.TARGET_W,
            "height": config.TARGET_H,
            "fps": config.FPS,
            "duration": round(total_duration, 2),
            "crossfade": config.CROSSFADE,
        },
        "segments": [],
    }
    for p, st in zip(plans, starts):
        data["segments"].append({
            "index": p.index,
            "role": p.role,
            "kind": p.kind,
            "file": p.material.name,
            "source_start": round(p.source_start, 2),
            "start_in_video": st,
            "duration": round(p.duration, 2),
            "fit_mode": p.fit_mode,
            "subtitle": p.subtitle,
            "transition": "crossfade" if p.index > 0 else "fadein",
            "repeated": p.repeated,
            "ken_burns": ("zoom_in" if p.zoom_in else "zoom_out")
            if p.kind == "photo" else None,
        })
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    log.info("已导出 %s", out_path)


def export_report(plans: List[SegmentPlan], lib: Library,
                  out_path: str) -> None:
    used = {p.material.path for p in plans}
    # utf-8-sig 让 Excel 正确识别中文
    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["序号", "文件名", "类型", "原始分辨率", "方向",
                    "源时长(秒)", "成片时长(秒)", "适配方式", "字幕", "是否复用"])
        for p in plans:
            m = p.material
            w.writerow([p.index, m.name, m.kind, f"{m.width}x{m.height}",
                        m.orientation, round(m.duration, 2),
                        round(p.duration, 2), p.fit_mode,
                        p.subtitle or "", "是" if p.repeated else "否"])
        # 未使用 / 跳过的素材
        for m in lib.videos + lib.photos:
            if m.path not in used:
                w.writerow(["-", m.name, m.kind, f"{m.width}x{m.height}",
                            m.orientation, round(m.duration, 2), 0, "-", "",
                            "未使用"])
        for m in lib.skipped:
            w.writerow(["-", m.name, m.kind, f"{m.width}x{m.height}",
                        m.orientation, round(m.duration, 2), 0, "-", "",
                        f"跳过: {m.error}"])
    log.info("已导出 %s", out_path)


def _write_visual(clip, out_path: str) -> None:
    """只渲染画面（不含音频），整片只渲染这一次。"""
    log.info("正在渲染画面 %s ...", os.path.basename(out_path))
    clip.without_audio().write_videofile(
        out_path,
        fps=config.FPS,
        codec=config.VIDEO_CODEC,
        bitrate=config.VIDEO_BITRATE,
        threads=os.cpu_count() or 4,
        preset="medium",
        audio=False,
        logger="bar",
    )


def _write_audio(audio, out_path: str) -> bool:
    if audio is None:
        return False
    # CompositeAudioClip 不会自动带 fps，需显式指定，否则 write_audiofile 报错
    fps = getattr(audio, "fps", None) or config.AUDIO_FPS
    audio.write_audiofile(out_path, fps=fps, codec=config.AUDIO_CODEC,
                          logger=None)
    return True


def _mux(visual_path: str, audio_path, out_path: str) -> None:
    """用 ffmpeg 把已渲染的画面与某条音轨合并（视频流直接拷贝，秒级完成）。"""
    ffmpeg = get_ffmpeg_exe()
    if audio_path:
        cmd = [ffmpeg, "-y", "-i", visual_path, "-i", audio_path,
               "-map", "0:v:0", "-map", "1:a:0",
               "-c:v", "copy", "-c:a", config.AUDIO_CODEC, "-b:a", "192k",
               "-shortest", out_path]
    else:
        cmd = [ffmpeg, "-y", "-i", visual_path, "-c", "copy", out_path]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL)
    log.info("已输出 %s", os.path.basename(out_path))


def render_all(movie, plans: List[SegmentPlan], lib: Library,
               paths: config.Paths) -> None:
    """渲染画面一次，再分别合成「带音乐」与「无音乐」两个版本，并导出报表。"""
    out_dir = paths.output_dir
    os.makedirs(out_dir, exist_ok=True)
    duration = movie.duration

    env_audio = lower_env_audio(movie)
    music = build_music(lib.music, duration)
    full_audio = mix_with_music(env_audio, music)

    visual_path = os.path.join(out_dir, "_visual.mp4")
    env_path = os.path.join(out_dir, "_env_audio.m4a")
    full_path = os.path.join(out_dir, "_full_audio.m4a")
    temp_files = [visual_path]

    # 1) 画面只渲染一次
    _write_visual(movie, visual_path)

    # 2) 生成两条音轨
    has_env = _write_audio(env_audio, env_path)
    has_full = _write_audio(full_audio, full_path)
    if has_env:
        temp_files.append(env_path)
    if has_full:
        temp_files.append(full_path)

    # 3) 合并（视频流直接拷贝）
    _mux(visual_path, env_path if has_env else None,
         os.path.join(out_dir, config.OUTPUT_NO_MUSIC))
    _mux(visual_path, full_path if has_full else None,
         os.path.join(out_dir, config.OUTPUT_WITH_MUSIC))

    # 4) 报表
    export_timeline(plans, os.path.join(out_dir, config.OUTPUT_TIMELINE), duration)
    export_report(plans, lib, os.path.join(out_dir, config.OUTPUT_REPORT))

    # 5) 清理临时文件
    for f in temp_files:
        try:
            os.remove(f)
        except OSError:
            pass

    log.info("全部完成！输出目录: %s", os.path.abspath(out_dir))
