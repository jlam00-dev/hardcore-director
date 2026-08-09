---
name: video-reverse-engineer
description: 对广告/短视频进行结构化拆解，输出镜头语言、色彩、节奏、音频的完整分析报告，用于学习竞品手法、建立案例库、AI生成时做风格参考。触发词：「反推」「拆解视频」「分析广告」「视频反推」「学习这个视频」「竞品分析」「拉片」。
---

# Video Reverse Engineer（视频反推技能）

> 给一个广告视频 → 输出结构化的完整拆解报告
> 用途：学习竞品手法、建立案例库、AI生成时做风格参考

## TL;DR 快速执行

```
1. 确认视频路径 + 分析深度（见启动检查点）
2. 运行 analyze.py 或直接在 Codex 中粘贴路径
3. 输出：色彩分析 + 镜头节奏 + 音频特征 + 六维度判断
4. 存入用户指定的参照案例库目录
```

## 核心能力

1. **镜头检测** — PySceneDetect AdaptiveDetector，比帧差法更准（可检测淡入淡出）
2. **智能关键帧** — 每个镜头自动选视觉最丰富的帧，而非均匀采样
3. **HDR暗帧校正** — 自动修正HLG/PQ/HDR编码导致的黑帧问题
4. **色彩分析** — K-Means提取主色调 + 光影风格判断
5. **镜头节奏分析** — 镜头时长分布图谱
6. **音频特征提取** — BGM有无、动态范围、风格判断
7. **结构化输出** — 自动生成Markdown拆解报告

## 依赖

```bash
pip install opencv-python-headless numpy Pillow scikit-image scipy wavio scikit-learn scenedetect mlx-whisper
brew install ffmpeg
```

## 技术升级

v1.0 → v2.0 升级内容：
- **PySceneDetect AdaptiveDetector** 替换 naive 帧差法（镜头边界更准）
- **智能最佳帧选择**（亮度+边缘综合评分）替换均匀采样
- **HDR暗帧自动校正**（解决香奈儿5号这类暗调广告的黑帧问题）
- **采样去重机制**（0.1秒去重，避免相近帧重复）

v2.1 升级内容：
- **长视频自动缩放**：根据时长自动调整采样间隔（15秒→0.5s间隔，1小时→10s间隔）
- **暗调镜头保护**：低亮度镜头直接保留首帧，不再被评分算法过滤
- **新增参数**：`--min-frames`（默认20）和 `--max-frames`（默认200）控制采样范围
- **mlx-whisper音频转录**：Apple Silicon本地转录，口播文字+分段时间戳（需安装mlx-whisper）

## 进阶参考（可集成）

| 仓库 | Stars | 用途 |
|------|------|------|
| [PySceneDetect](https://github.com/Breakthrough/PySceneDetect) | 8.7k | 镜头边界检测（已集成） |
| [Katna](https://github.com/keplerlab/Katna) | 1.1k | ML智能关键帧提取 |
| [VideoContext-Engine](https://github.com/dolphin-creator/VideoContext-Engine) | 新 | Whisper ASR + Qwen3-VL全流程（需GPU） |

## 启动检查点

激活后，先确认以下信息再开始分析：

1. **视频来源**：本地文件路径 or 需要下载？
2. **分析深度**：快速拆解（色彩+节奏）or 完整报告（含音频+构图）？
3. **输出用途**：学习竞品 / 建案例库 / AI生成参考？

> 确认后再执行，避免跑完才发现方向不对。

## 使用方式

### 方式一：命令行快速分析

```bash
python "$CODEX_HOME/skills/video-reverse-engineer/analyze.py" \
  "/path/to/video.mp4" \
  --frames 30 \
  --min-frames 20 \
  --max-frames 200 \
  --transcribe \
  --output "/path/to/output_dir"
```

**帧数自动缩放规则（未指定 --frames 时）：**
| 视频时长 | 采样间隔 | 最大帧数 |
|---------|---------|---------|
| ≤30s | 0.5s | 20-60 |
| 30s-3min | 2s | 60 |
| 3-10min | 5s | 60-120 |
| >10min | 10s | 上限200 |

> 长视频建议配合 `--min-frames 50 --max-frames 200` 使用

### 方式二：在 Codex 中调用

```
分析这个广告的视频文件：
/path/to/video.mp4

请输出完整的拆解报告，格式参考：
参照案例库/广告拆解模板.md
```

## 分析流程

### Step 1：场景检测 + 帧提取

```python
import cv2
import os
import numpy as np

def extract_key_frames(video_path, num_frames=30, output_dir=None):
    """均匀采样 + 场景变化点结合"""
    cap = cv2.VideoCapture(video_path)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)

    # 方法A：均匀采样
    uniform_indices = np.linspace(0, total_frames-1, num_frames, dtype=int)

    # 方法B：场景变化检测（对比连续帧差异）
    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
    prev_frame = None
    scene_changes = []
    frame_idx = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        if prev_frame is not None:
            diff = np.mean(np.abs(gray.astype(float) - prev_frame.astype(float)))
            if diff > 30:  # 场景突变阈值
                scene_changes.append(frame_idx)

        prev_frame = gray
        frame_idx += 1

    cap.release()

    # 合并两种采样：均匀采样为主，场景变化点补充
    combined_indices = sorted(set(uniform_indices.tolist() + scene_changes))[:num_frames]

    # 提取帧
    frames = []
    cap = cv2.VideoCapture(video_path)
    for idx in combined_indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ret, frame = cap.read()
        if ret:
            # HDR处理：如果帧偏暗，尝试提亮
            frame_bright = correct_dark_frame(frame)
            frames.append((idx/fps, frame_bright))
    cap.release()

    return frames
```

### Step 2：HDR/暗帧自动修正

```python
def correct_dark_frame(frame, target_luminance=128):
    """处理HDR或摄影机直出导致的暗帧"""
    # 转换到LAB色彩空间
    lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
    l_channel = lab[:,:,0]

    mean_l = np.mean(l_channel)
    if mean_l < 50:  # 帧明显过暗
        # 全局亮度调整
        gain = target_luminance / mean_l
        gain = min(gain, 4.0)  # 防止过度放大
        lab[:,:,0] = np.clip(l_channel * gain, 0, 255).astype(np.uint8)
        # 对比度增强
        lab[:,:,0] = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8)).apply(lab[:,:,0])
        frame = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
    return frame
```

### Step 3：色彩分析

```python
def analyze_color_palette(frames, k=5):
    """K-Means提取主色调"""
    from sklearn.cluster import KMeans

    all_pixels = []
    for _, frame in frames:
        # 缩小加速
        small = cv2.resize(frame, (100, 100))
        all_pixels.append(small.reshape(-1, 3))

    pixels = np.vstack(all_pixels).astype(np.float32)

    # K-Means
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 10, 1.0)
    _, labels, centers = cv2.kmeans(pixels, k, None, criteria, 10, cv2.KMEANS_RANDOM_CENTERS)

    # 按频次排序
    counts = np.bincount(labels.flatten())
    order = np.argsort(counts)[::-1]
    palette = [centers[i].astype(int).tolist() for i in order]

    # 颜色名称
    color_names = []
    for rgb in palette:
        color_names.append(rgb_to_color_name(rgb))

    return palette, color_names

def rgb_to_color_name(rgb):
    """RGB转颜色名称（简化版）"""
    r, g, b = rgb
    if max(rgb) < 50:
        return "黑色"
    if max(rgb) < 100:
        return "深灰"
    if r > 200 and g > 200 and b > 200:
        return "白色"
    if r > 150 and g < 100 and b < 100:
        return "正红"
    if r > 180 and g > 100 and b < 80:
        return "橙红"
    if r > 150 and g > 150 and b < 100:
        return "暖黄"
    if g > 150 and r < 100 and b < 100:
        return "翠绿"
    if b > 150 and r < 100 and g < 100:
        return "深蓝"
    if r > 180 and g > 180 and b > 180:
        return "浅粉"
    if r > 150 and g > 120 and b > 80:
        return "大地色"
    if r < 100 and g < 100 and b > 150:
        return "藏青"
    if r > 200 and g > 200 and b < 150:
        return "香槟金"
    return "灰调"
```

### Step 4：景别 + 构图分析

```python
def analyze_shot_composition(frame):
    """分析单帧的景别和构图"""
    h, w = frame.shape[:2]

    # 简化景别判断（基于画面中主体的占比）
    # 需要先用边缘检测或人物检测定位主体
    # 这里用色彩对比度粗估

    # 构图法则检测
    third_h = h // 3
    third_w = w // 3

    composition = {
        "has_centered": False,
        "has_rule_of_thirds": False,
        "has_symmetry": False,
        "dominant_area": "unknown"
    }

    # 对称性检测
    left = frame[:, :w//2]
    right = frame[:, w//2:]
    if np.mean(np.abs(left.astype(float) - right.astype(float))) < 20:
        composition["has_symmetry"] = True

    return composition
```

### Step 5：音频分析

```python
def analyze_audio(video_path):
    """提取音频特征（无需语音识别）"""
    import subprocess

    # 提取音频到临时文件
    audio_path = "/tmp/analysis_audio.wav"
    subprocess.run([
        "ffmpeg", "-y", "-i", video_path,
        "-vn", "-acodec", "pcm_s16le",
        "-ar", "22050", audio_path
    ], capture_output=True)

    # 读取音频
    import wavio
    audio = wavio.read(audio_path)
    samples = audio.data

    # 计算响度分布
    rms = np.sqrt(np.mean(samples**2, axis=0 if len(samples.shape) > 1 else 0))
    peak = np.max(np.abs(samples))

    # 粗略判断：是否有明显旋律（音乐 vs 纯音效）
    # 通过频谱简单判断
    from scipy.fft import fft
    spectrum = np.abs(fft(samples[:len(samples)//10].flatten()))
    low_freq_energy = np.mean(spectrum[:100])
    high_freq_energy = np.mean(spectrum[100:1000])

    has_music = high_freq_energy > low_freq_energy * 0.3

    return {
        "has_music": bool(has_music),
        "dynamic_range": float(20 * np.log10(peak / (rms + 1e-10))),
        "estimated_genre": "upbeat" if high_freq_energy > low_freq_energy else "ambient"
    }
```

### Step 6：镜头时长分析

```python
def analyze_shot_rhythm(video_path, scene_threshold=30):
    """分析镜头时长分布"""
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)

    shots = []
    prev_frame = None
    shot_start = 0
    frame_idx = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        if prev_frame is not None:
            diff = np.mean(np.abs(gray.astype(float) - prev_frame.astype(float)))
            if diff > scene_threshold:
                duration = (frame_idx - shot_start) / fps
                shots.append({"start": shot_start/fps, "duration": duration})
                shot_start = frame_idx
        prev_frame = gray
        frame_idx += 1

    # 最后一段
    shots.append({"start": shot_start/fps, "duration": (frame_idx - shot_start)/fps})
    cap.release()

    durations = [s["duration"] for s in shots]
    return {
        "shot_count": len(shots),
        "avg_duration": np.mean(durations),
        "min_duration": np.min(durations),
        "max_duration": np.max(durations),
        "shots": shots
    }
```

### Step 7：生成完整报告

```python
def generate_breakdown_report(video_path, output_path=None):
    """生成完整拆解报告"""
    print(f"正在分析：{video_path}")

    # 1. 提取帧
    print("Step 1/6：提取关键帧...")
    frames = extract_key_frames(video_path, num_frames=30)

    # 2. 色彩分析
    print("Step 2/6：分析色彩...")
    palette, color_names = analyze_color_palette(frames)

    # 3. 镜头节奏
    print("Step 3/6：分析镜头节奏...")
    rhythm = analyze_shot_rhythm(video_path)

    # 4. 音频
    print("Step 4/6：分析音频...")
    audio = analyze_audio(video_path)

    # 5. 生成报告
    print("Step 5/6：生成结构化报告...")
    report = f"""# 广告反推拆解报告

> 来源：{video_path}
> 生成：{datetime.now().strftime('%Y-%m-%d %H:%M')}

## 基本信息

- **视频时长**：{1/frames[-1][0] if frames else 'unknown'}秒（估计）
- **镜头数量**：{rhythm['shot_count']}个
- **平均镜头时长**：{rhythm['avg_duration']:.2f}秒

## 色彩分析

### 主色调
| 排名 | 颜色 | RGB | 色块 |
|------|------|-----|------|
"""

    for i, (rgb, name) in enumerate(zip(palette, color_names)):
        r, g, b = rgb
        report += f"| {i+1} | {name} | RGB({r},{g},{b}) | <span style='background:rgb({r},{g},{b})'>&nbsp;&nbsp;&nbsp;</span> |\n"

    report += f"""
### 光影风格
- **亮度**：{'暗调' if np.mean([f[1][:,:,0] for _, f in frames]) < 100 else '明调'}
- **对比度**：{'高对比' if np.std([f[1] for _, f in frames]) > 50 else '柔和'}
- **色调**：{'冷调' if np.mean(frames[-1][1][:,:,2]) > np.mean(frames[-1][1][:,:,0]) else '暖调'}

## 镜头节奏

- **总镜头数**：{rhythm['shot_count']}
- **平均时长**：{rhythm['avg_duration']:.2f}秒
- **最短镜头**：{rhythm['min_duration']:.2f}秒
- **最长镜头**：{rhythm['max_duration']:.2f}秒

### 镜头时长分布
"""

    for shot in rhythm['shots'][:15]:
        bar = "█" * max(1, int(shot['duration'] * 10))
        report += f"- {shot['start']:.1f}s - {shot['duration']:.2f}s {bar}\n"

    report += f"""
## 音频特征

- **BGM类型**：{'有音乐' if audio['has_music'] else '无音乐/纯音效'}
- **动态范围**：{audio['dynamic_range']:.1f} dB
- **估计风格**：{audio.get('estimated_genre', 'unknown')}

## 镜头语言推测

"""

    # 根据数据推测镜头类型
    if rhythm['avg_duration'] > 3:
        report += "- 以**长镜头**为主 → 诗意、沉浸、情绪留白\n"
    elif rhythm['avg_duration'] > 1.5:
        report += "- 以**中等镜头**为主 → 叙事平衡、节奏稳健\n"
    else:
        report += "- 以**短镜头**为主 → 快节奏、冲击力强\n"

    if audio['has_music']:
        report += "- 有BGM → 情绪渲染是核心叙事手段\n"
    else:
        report += "- 无BGM → 依赖画面和音效叙事\n"

    report += """
## 六维度初步判断

| 维度 | 是否体现 | 推测方式 |
|------|---------|---------|
| 痛点 | 待确认 | 需看完整视频 |
| 场景 | | |
| 对比 | | |
| 产品 | | |
| 体验 | | |
| 价值 | | |

## 拆解结论

> 视频素材已提取，关键分析需结合视觉复核。
> 建议将帧保存下来逐帧对照：
"""

    for ts, frame in frames[:20]:
        report += f"- {ts:.1f}s：需人工标注\n"

    return report
```

## 帧提取失败排查

| 问题 | 原因 | 解决方案 |
|------|------|---------|
| 全黑帧 | HDR（HLG/PQ）编码 | 用 `ffmpeg -i input -vf "zscale=t=linear:npl=100,eq=brightness=0.1:contrast=1.2,zscale=t=bt709,tonemap=tonemap=hable" output` |
| 全黑帧 | 杜比视界（Dolby Vision） | 当前无法处理，需转码：`ffmpeg -i input -dv false -hdr10 false output` |
| 色彩失真 | 色彩空间转换错误 | 强制BT.709：`ffmpeg -i input -vf "scale=out_color_matrix=bt709" output` |
| 画面正常但分析不对 | 分析脚本问题 | 检查帧索引是否正确、色彩空间是否匹配 |

## 局限性

- **无法提取音频文字/BGM歌词** — 需要 Whisper API 或人工听写
- **无法自动识别产品名称/品牌** — 需要人工标注
- **景别判断基于比例，非AI识别** — 结果为估算
- **创意意图/情绪判断** — 需要人工复核，结合上下文

## 文件结构

```
skills/video-reverse-engineer/
├── SKILL.md           # 本文件
├── analyze.py         # 命令行分析脚本
└── requirements.txt   # pip依赖
```
