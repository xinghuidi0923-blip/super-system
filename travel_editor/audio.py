"""背景音乐与原视频环境声的混音处理。"""

from __future__ import annotations

from typing import List, Optional

from moviepy.editor import (AudioFileClip, CompositeAudioClip,
                            concatenate_audioclips)
from moviepy.audio.fx.audio_fadein import audio_fadein
from moviepy.audio.fx.audio_fadeout import audio_fadeout
from moviepy.audio.fx.volumex import volumex

from . import config
from .utils import get_logger

log = get_logger()


def lower_env_audio(movie):
    """把原视频环境声降到较低音量；无音轨时返回 None。"""
    if movie.audio is None:
        return None
    return volumex(movie.audio, config.ENV_VOLUME)


def _loop_to(audio, duration: float):
    """把音乐循环 / 裁切到目标时长。"""
    if audio.duration >= duration:
        return audio.subclip(0, duration)
    times = int(duration // audio.duration) + 1
    looped = concatenate_audioclips([audio] * times)
    return looped.subclip(0, duration)


def build_music(music_paths: List[str], duration: float):
    """加载第一首音乐，循环/裁切到时长，并做淡入淡出。无音乐返回 None。"""
    if not music_paths:
        return None
    path = music_paths[0]
    try:
        music = AudioFileClip(path)
    except Exception as exc:  # noqa: BLE001
        log.warning("背景音乐加载失败 %s: %s", path, exc)
        return None
    music = _loop_to(music, duration)
    music = volumex(music, config.MUSIC_VOLUME)
    music = audio_fadein(music, config.MUSIC_FADEIN)
    music = audio_fadeout(music, config.MUSIC_FADEOUT)
    log.info("背景音乐: %s", path)
    return music


def mix_with_music(env_audio, music):
    """混合环境声与背景音乐。"""
    tracks = [t for t in (env_audio, music) if t is not None]
    if not tracks:
        return None
    if len(tracks) == 1:
        return tracks[0]
    comp = CompositeAudioClip(tracks)
    comp.fps = max((getattr(t, "fps", 0) or 0 for t in tracks),
                   default=config.AUDIO_FPS) or config.AUDIO_FPS
    return comp
