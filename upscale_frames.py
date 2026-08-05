"""
封面机器人抽帧图 AI 超分脚本（Real-ESRGAN ncnn-vulkan 版）

把 robot_frames 下的 720p 抽帧图，用 Real-ESRGAN 先做 x4 AI 超分（5K），
再用 Pillow LANCZOS 高质量缩回 2K（2560x1440），覆盖写回同名文件。
前端零改动即可受益（路径/帧数/TOTAL 不变）。

为什么是 "x4 超分 + 下采样到 2K" 而不是直接 x2：
  - 你下载的 20210901 老版 ncnn exe 的 -s 参数只支持 1 和 4，不支持 2。
  - 而 "x4 超分后再缩到 2K" 与 "原生 x2" 效果完全一致（都是 x4 模型先放大再缩回）。
  - 这样既拿到 AI 补细节的锐化增益，又把文件压回 2K 量级，预加载不拖慢。

断点续跑：
  - 已是 2K（高度 >= target_h）的图自动跳过，可反复运行只补未完成的部分。
  - 每处理一张立即 flush 进度日志，进程被中断后重跑即可续上。

用法：
  python upscale_frames.py
  python upscale_frames.py --in frontend/public/robot_frames --scale-out 1440
  python upscale_frames.py --exe "D:/.../realesrgan-ncnn-vulkan.exe"

注意：
  - 本地一次性预处理，产物不进 git（见 .gitignore）。
  - 需要 Vulkan 支持（独显/核显驱动通常自带）。若报 vulkan 相关错误，需安装 Vulkan 运行时。
"""
import argparse
import glob
import os
import subprocess
import sys

from PIL import Image

# 默认 exe 路径：指向你手动下载解压的 ncnn 版目录
DEFAULT_EXE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "realesrgan-ncnn-vulkan-20210901-windows",
    "realesrgan-ncnn-vulkan.exe",
)
DEFAULT_IN = os.path.join("frontend", "public", "robot_frames")
DEFAULT_MODEL = "realesrgan-x4plus"  # 老版自带的 x4 模型（默认，偏真实照片、爱加噪点）
# anime 模型（realesrgan-x4plus-anime，针对干净渲染/插画图训练，去噪、保锐利边）
# 适合封面 3D 渲染机器人，可缓解默认模型造成的"糊糊一层"雾感。


def find_exe(exe_arg: str) -> str:
    """探测可用的 ncnn exe；找不到则报错退出。"""
    candidates = []
    if exe_arg:
        candidates.append(exe_arg)
    candidates.append(DEFAULT_EXE)
    base = os.path.dirname(os.path.abspath(__file__))
    candidates.append(
        os.path.join(base, "realesrgan-ncnn-vulkan-20210901-windows", "realesrgan-ncnn-vulkan.exe")
    )
    for c in candidates:
        if c and os.path.isfile(c):
            return os.path.abspath(c)
    print("[错误] 找不到 realesrgan-ncnn-vulkan.exe。", file=sys.stderr)
    print("        请确认已将 ncnn 版 zip 解压到项目目录，或用 --exe 指定 exe 路径。", file=sys.stderr)
    sys.exit(1)


def log(msg: str, f_log):
    """打印并即时 flush 到日志文件，避免后台运行时日志缓冲丢失。"""
    print(msg, flush=True)
    if f_log:
        f_log.write(msg + "\n")
        f_log.flush()


def upscale_one(exe: str, in_path: str, tmp_path: str, timeout: int, model: str) -> bool:
    """调用 ncnn exe 把单张图 x4 超分（输出 png 临时文件）。"""
    cmd = [exe, "-i", in_path, "-o", tmp_path, "-s", "4", "-n", model]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return False
    if proc.returncode != 0:
        return False
    return os.path.isfile(tmp_path)


def downscale_to_2k(tmp_path: str, out_path: str, target_h: int, quality: int) -> bool:
    """把 x4 超分出的大图高质量缩到 2K（按高度 target_h 等比），写回高质量 jpg。"""
    try:
        im = Image.open(tmp_path).convert("RGB")
        w, h = im.size
        if h > target_h:
            scale = target_h / float(h)
            new_w = max(1, int(round(w * scale)))
            im = im.resize((new_w, target_h), Image.LANCZOS)
        im.save(out_path, "JPEG", quality=quality, subsampling=0, optimize=True)
        return True
    except Exception:  # noqa: BLE001
        return False


def main():
    p = argparse.ArgumentParser(description="机器人抽帧图 AI 超分（x4 超分 + 下采样到 2K，断点续跑）")
    p.add_argument("--in", dest="in_dir", default=DEFAULT_IN, help="输入目录（默认 frontend/public/robot_frames）")
    p.add_argument("--exe", default="", help="realesrgan-ncnn-vulkan.exe 路径")
    p.add_argument("--scale-out", dest="target_h", type=int, default=1440, help="输出高度（默认 1440 → 2560x1440 2K）")
    p.add_argument("--quality", type=int, default=95, help="输出 jpg 质量（默认 95）")
    p.add_argument("--timeout", type=int, default=600, help="单张超分超时秒数（默认 600）")
    p.add_argument("--model", default=DEFAULT_MODEL, help="超分模型名（默认 realesrgan-x4plus，可选 realesrgan-x4plus-anime）")
    p.add_argument("--only", default="", help="仅重跑指定帧，逗号分隔文件名，如 frame_0001.jpg,frame_0020.jpg（绕过尺寸跳过逻辑）")
    args = p.parse_args()

    in_dir = os.path.abspath(args.in_dir)
    if not os.path.isdir(in_dir):
        print(f"[错误] 输入目录不存在: {in_dir}", file=sys.stderr)
        sys.exit(1)

    exe = find_exe(args.exe)
    log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "upscale_log.txt")
    f_log = open(log_path, "a", encoding="utf-8")

    log(f"=== 启动 === exe={exe} model={args.model}", f_log)
    log(f"输入={in_dir} 输出=2K({int(round(2560/1440*args.target_h))}x{args.target_h}) quality={args.quality}", f_log)

    files = sorted(glob.glob(os.path.join(in_dir, "frame_*.jpg")))
    if not files:
        log("[错误] 没找到 frame_*.jpg", f_log)
        f_log.close()
        sys.exit(1)

    # --only 指定时：todo 直接取这些文件，强制重跑（绕过尺寸跳过逻辑），便于样张对比
    if args.only.strip():
        wanted = {os.path.basename(x.strip()) for x in args.only.split(",") if x.strip()}
        todo = [f for f in files if os.path.basename(f) in wanted]
        skipped = 0
        if not todo:
            log(f"[错误] --only 指定的帧都不在目录内: {sorted(wanted)}", f_log)
            f_log.close()
            sys.exit(1)
        log(f"--only 模式：强制重跑 {len(todo)} 张（{[os.path.basename(f) for f in todo]}）\n", f_log)
    else:
        # 断点续跑：跳过已是 2K 的图
        todo = []
        skipped = 0
        for f in files:
            try:
                if Image.open(f).size[1] >= args.target_h:
                    skipped += 1
                    continue
            except Exception:
                pass
            todo.append(f)
        log(f"共 {len(files)} 张，已 2K 跳过 {skipped} 张，待处理 {len(todo)} 张\n", f_log)

    tmp_path = os.path.join(in_dir, "_upscale_tmp.png")
    ok_count = 0
    fail = []
    for idx, f in enumerate(todo, 1):
        base = os.path.basename(f)
        if not upscale_one(exe, f, tmp_path, args.timeout, args.model):
            fail.append(base)
            log(f"  [FAIL] {base} 超分失败/超时", f_log)
            if os.path.isfile(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
            continue
        if downscale_to_2k(tmp_path, f, args.target_h, args.quality):
            ok_count += 1
        else:
            fail.append(base)
            log(f"  [FAIL] {base} 下采样失败", f_log)
        if os.path.isfile(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
        if idx % 5 == 0 or idx == len(todo):
            log(f"  进度 {idx}/{len(todo)} 成功 {ok_count}", f_log)

    log(f"\n=== 完成 === 本批成功 {ok_count}/{len(todo)} 张", f_log)
    if fail:
        log(f"失败 {len(fail)} 张: {fail}", f_log)
    # 抽查首图
    if files:
        with Image.open(files[0]) as chk:
            log(f"抽查 {os.path.basename(files[0])} 尺寸: {chk.size}", f_log)
    f_log.close()


if __name__ == "__main__":
    main()
