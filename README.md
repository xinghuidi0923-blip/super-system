# 自动旅游短片生成器 🎬

把你的旅游视频和照片，一键剪成一部约 **90 秒、9:16 竖屏**的旅行纪念短片，
适合发朋友圈和小红书。

- ✅ 输出 1080×1920、H.264、MP4
- ✅ 横屏素材自动适配竖屏（模糊背景填充 / 居中裁切，**画面不变形**）
- ✅ 照片自动加轻微推拉缩放（Ken Burns），不静止
- ✅ 旅行叙事节奏：开场 → 风景/美食/人物 → 回忆感结尾
- ✅ 简洁高级的白色中文字幕（带轻微阴影，不遮挡主体）
- ✅ 自动加背景音乐（开头淡入、结尾淡出），原视频环境声保留较低音量
- ✅ 自然转场（淡入淡出 / 交叉溶解），不花哨
- ✅ 素材不足时自动延长照片或复用高质量素材补足时长
- ✅ 同时输出 **带音乐版** 和 **无音乐版**，外加时间线与素材报告

---

## 一、安装

需要 **Python 3.8 ~ 3.11**（建议 3.10）。

```bash
# 1. 进入项目目录
cd super-system

# 2.（推荐）创建虚拟环境
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS / Linux:
# source .venv/bin/activate

# 3. 安装依赖（会自动下载 ffmpeg，无需手动装）
pip install -r requirements.txt
```

> 不需要单独安装 FFmpeg —— `imageio-ffmpeg` 会自动下载并管理它。

---

## 二、放素材

把文件分别放进这三个文件夹（脚本首次运行也会自动创建）：

```
input/
├── videos/   ← 旅游视频（.mp4 .mov .m4v .avi .mkv .webm）
├── photos/   ← 照片（.jpg .jpeg .png .heic .bmp .webp）
└── music/    ← 背景音乐，可选（.mp3 .wav .m4a .aac .flac .ogg）
```

> 你原来放在 `C:\Users\admin\Desktop\旅游\剪辑完成` 的素材，
> 按视频 / 照片 / 音乐分别复制到上面三个文件夹即可。
> 文件名会影响出现顺序（按文件名排序），可用 `01_`、`02_` 前缀控制顺序。

---

## 三、运行

```bash
python make_travel_video.py
```

常用参数：

```bash
# 自定义开场标题
python make_travel_video.py --title "我的夏日旅行"

# 改目标时长（秒）
python make_travel_video.py --target 90

# 横屏素材改用“居中裁切”铺满（默认是“模糊背景填充”）
python make_travel_video.py --fit crop

# 指定中文字体（字幕变方块时用）
python make_travel_video.py --font "C:\Windows\Fonts\msyh.ttc"

# 固定随机种子，便于复现同一种剪辑
python make_travel_video.py --seed 42
```

运行结束后，输出在 `output/` 目录：

| 文件 | 说明 |
|------|------|
| `final_travel_video.mp4` | 成片（带背景音乐 + 低音量环境声）|
| `final_travel_video_no_music.mp4` | 成片（仅低音量环境声，无背景音乐）|
| `timeline.json` | 完整时间线（每段来源、时长、字幕、转场）|
| `material_report.csv` | 素材使用报告（用 Excel 打开，含未使用/跳过的素材）|

---

## 四、调整参数

绝大多数效果都在 **`travel_editor/config.py`** 里集中配置，按需修改即可：

| 参数 | 含义 |
|------|------|
| `TARGET_DURATION` | 目标时长（默认 90 秒）|
| `DURATION_TOLERANCE` | 允许误差（默认 ±5 秒）|
| `VIDEO_SEG_MIN/MAX` | 每段视频截取时长（2–5 秒）|
| `PHOTO_DUR_MIN/MAX` | 每张照片展示时长（2–3 秒）|
| `CROSSFADE` | 转场时长（交叉溶解）|
| `VIDEO_FIT_MODE` / `PHOTO_FIT_MODE` | `blur`（模糊背景）或 `crop`（居中裁切）|
| `BG_DARKEN` | 模糊背景压暗程度 |
| `KEN_BURNS_ZOOM` | 照片推拉缩放幅度 |
| `MUSIC_VOLUME` / `ENV_VOLUME` | 背景音乐 / 环境声音量 |
| `MUSIC_FADEIN` / `MUSIC_FADEOUT` | 音乐淡入 / 淡出时长 |
| `SUBTITLE_FONT_SIZE` / `SUBTITLE_Y_RATIO` | 字幕大小 / 竖直位置 |
| `OPENING_SUBTITLE` / `MIDDLE_SUBTITLES` / `ENDING_SUBTITLE` | 字幕文案 |
| `VIDEO_BITRATE` | 输出码率（画质）|

---

## 五、项目结构

```
super-system/
├── make_travel_video.py      # 命令行入口
├── travel_editor/
│   ├── config.py             # 所有可调参数
│   ├── utils.py              # 字体 / 竖屏适配 / 模糊 / 字幕图片
│   ├── scanner.py            # 扫描 input/ 并探测素材信息
│   ├── clips.py              # 片段渲染（适配/运镜/字幕/转场）
│   ├── builder.py            # 叙事编排 + 90秒时长控制
│   ├── audio.py              # 背景音乐 + 环境声混音
│   └── render.py             # 输出 MP4 / timeline.json / report.csv
├── input/{videos,photos,music}/
├── output/
├── requirements.txt
└── README.md
```

工作流程：`scan` 扫描素材 → `build_timeline` 编排顺序并把时长卡到约 90 秒
→ `build_movie` 渲染画面与转场 → `audio` 混音 → `render_all` 导出文件。

---

## 六、常见报错与处理

**1. `AttributeError: module 'PIL.Image' has no attribute 'ANTIALIAS'`**
Pillow 10+ 删除了 `ANTIALIAS`，与 moviepy 1.0.3 冲突。
解决：`pip install "Pillow<10"`（`requirements.txt` 已固定）。

**2. numpy 相关报错（如 `np.float` 已弃用）**
numpy 2.x 与 moviepy 1.0.3 不兼容。
解决：`pip install "numpy<2"`（`requirements.txt` 已固定）。

**3. 字幕显示成方块 □□□**
没找到中文字体。用 `--font` 指定一个中文字体文件，例如：
`python make_travel_video.py --font "C:\Windows\Fonts\msyh.ttc"`。

**4. `OSError: MoviePy error: ffmpeg ...` 或找不到 ffmpeg**
通常是 `imageio-ffmpeg` 没装好。重装：`pip install -U imageio-ffmpeg`。

**5. `.heic` 照片读不了**
部分系统不支持 HEIC。先转成 JPG，或安装 `pip install pillow-heif`
并在使用前 `from pillow_heif import register_heif_opener; register_heif_opener()`。

**6. 渲染很慢 / 内存占用高**
- 横屏视频较多时，把 `--fit crop` 用居中裁切（比模糊背景快）。
- 降低 `VIDEO_BITRATE`，或先把超大 4K 素材压到 1080p 再放进来。

**7. 成片时长不在 90±5 秒**
素材太少会偏短、太多会偏长。脚本会自动延长照片/复用素材或删减片段；
如仍不满意，可调 `config.py` 里的 `TARGET_DURATION` 或多放一些素材。

**8. 视频没有声音**
- 带音乐版需要 `input/music` 里有音乐文件。
- 无音乐版只保留原视频环境声；若原视频本身静音则没有声音。

---

## 七、设计取舍说明

- **稳定优先**：字幕用 Pillow 直接画成图片再叠加，**不依赖 ImageMagick**，
  避免 Windows 上 moviepy `TextClip` 的常见报错。
- **不变形**：竖屏适配只用「等比缩放 + 居中裁切」或「等比缩放 + 模糊背景」，
  绝不拉伸。
- **模糊背景用降采样实现**：先大幅缩小再放大，速度远快于逐帧高斯模糊，
  对长视频也能稳定快速出片。
