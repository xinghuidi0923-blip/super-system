#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""自动旅游短片生成器 —— 命令行入口。

用法（在项目根目录）:
    python make_travel_video.py
    python make_travel_video.py --title "我的夏日旅行" --target 90 --seed 42
    python make_travel_video.py --fit crop          # 用居中裁切代替模糊背景

把素材放进:
    input/videos   旅游视频
    input/photos   照片
    input/music    背景音乐（可选）

输出在 output/ 目录:
    final_travel_video.mp4            带背景音乐
    final_travel_video_no_music.mp4   仅环境声、无背景音乐
    timeline.json                     时间线
    material_report.csv               素材使用报告
"""

from __future__ import annotations

import argparse
import random
import sys

from travel_editor import config
from travel_editor.builder import build_timeline, timeline_duration
from travel_editor.clips import build_movie
from travel_editor.render import render_all
from travel_editor.scanner import scan
from travel_editor.utils import find_font, get_logger, load_font

log = get_logger()


def parse_args(argv=None):
    p = argparse.ArgumentParser(
        description="自动把旅游素材剪成约90秒的9:16竖屏纪念短片。")
    p.add_argument("--root", default=".", help="项目根目录（含 input/ 与 output/）")
    p.add_argument("--title", default=None, help="开场标题字幕")
    p.add_argument("--target", type=float, default=config.TARGET_DURATION,
                   help="目标时长（秒），默认 90")
    p.add_argument("--fit", choices=["blur", "crop"], default=None,
                   help="横屏素材竖屏适配方式：blur=模糊背景(默认), crop=居中裁切")
    p.add_argument("--font", default=None, help="中文字体文件路径 (如 msyh.ttc)")
    p.add_argument("--seed", type=int, default=None, help="随机种子，便于复现")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)

    config.TARGET_DURATION = args.target
    if args.fit:
        config.VIDEO_FIT_MODE = args.fit
        config.PHOTO_FIT_MODE = args.fit

    rng = random.Random(args.seed)

    paths = config.Paths(root=args.root)
    paths.ensure()

    font_path = find_font(args.font)
    if font_path:
        log.info("使用字体: %s", font_path)
    font = load_font(font_path, config.SUBTITLE_FONT_SIZE)

    log.info("扫描素材 ...")
    lib = scan(paths)
    if not lib.has_any:
        log.error("没有找到可用素材。请把视频放进 %s，照片放进 %s。",
                  paths.input_videos, paths.input_photos)
        return 1

    log.info("编排时间线 ...")
    plans = build_timeline(lib, rng, title=args.title)
    log.info("预计成片时长: 约 %.1f 秒", timeline_duration(plans))

    log.info("渲染画面 ...")
    movie = build_movie(plans, font)

    render_all(movie, plans, lib, paths)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        log.warning("已取消。")
        sys.exit(130)
    except Exception as exc:  # noqa: BLE001
        log.error("生成失败: %s", exc)
        raise
