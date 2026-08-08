"""
机器人视频抽帧脚本
把 frontend/public/机器人.mp4 拆成有序图片序列，输出到 public/robot_frames/。

用法示例：
  python extract_frames.py                  # 默认：每 3 帧抽 1 张
  python extract_frames.py --step 1         # 每帧都抽
  python extract_frames.py --interval-sec 0.1   # 按时间：每 0.1 秒抽 1 张
  python extract_frames.py --video 别的.mp4 --out 别的目录

注意：
  - 视频与输出图片均为本地素材，不进 git（见 .gitignore）。
  - 中文路径：直接传绝对路径字符串给 cv2，Windows 下可用。
"""
import argparse
import os
import sys

import cv2


def parse_args():
    p = argparse.ArgumentParser(description="机器人视频抽帧脚本")
    p.add_argument(
        "--video",
        default="frontend/public/机器人.mp4",
        help="视频路径（默认 frontend/public/机器人.mp4）",
    )
    p.add_argument(
        "--out",
        default="public/robot_frames",
        help="输出目录（默认 public/robot_frames）",
    )
    p.add_argument(
        "--step",
        type=int,
        default=3,
        help="按帧间隔抽样：每 step 帧抽 1 张（默认 3）",
    )
    p.add_argument(
        "--interval-sec",
        type=float,
        default=0.0,
        help="按时间间隔抽样：>0 时启用，每 interval-sec 秒抽 1 张",
    )
    p.add_argument(
        "--count",
        type=int,
        default=0,
        help="按目标总张数均匀抽样：>0 时启用（覆盖 step / interval-sec）",
    )
    return p.parse_args()


def main():
    args = parse_args()

    video_path = os.path.abspath(args.video)
    out_dir = os.path.abspath(args.out)

    if not os.path.isfile(video_path):
        print(f"[错误] 视频文件不存在: {video_path}", file=sys.stderr)
        sys.exit(1)

    os.makedirs(out_dir, exist_ok=True)

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"[错误] 无法打开视频（cv2 解码失败）: {video_path}", file=sys.stderr)
        sys.exit(1)

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    duration = total_frames / fps if fps else 0

    print("=== 视频元信息 ===")
    print(f"路径      : {video_path}")
    print(f"总帧数    : {total_frames}")
    print(f"FPS       : {fps:.3f}")
    print(f"分辨率    : {width} x {height}")
    print(f"时长(秒)  : {duration:.2f}")
    print(f"输出目录  : {out_dir}")

    # 决定抽帧策略
    use_count = args.count > 0
    if use_count:
        count = min(args.count, total_frames) if total_frames > 0 else args.count
        interval_frames = max(1, total_frames / count) if total_frames > 0 else 1
        print(f"模式      : 按目标总张数（均匀取 {count} 张，约每 {interval_frames:.2f} 帧抽 1 张）")
    elif args.interval_sec > 0:
        interval_frames = max(1, int(round(args.interval_sec * fps)))
        print(f"模式      : 按时间间隔（每 {args.interval_sec}s ≈ 每 {interval_frames} 帧抽 1 张）")
    else:
        interval_frames = max(1, args.step)
        print(f"模式      : 按帧间隔（每 {interval_frames} 帧抽 1 张）")

    saved = 0
    frame_idx = 0
    next_capture = 0.0  # 下一次该抽的帧位置（浮点，支持非整数均匀间隔）

    while True:
        ok, frame = cap.read()
        if not ok:
            break  # 读到末尾或解码失败

        if frame_idx >= int(round(next_capture)):
            saved += 1
            fname = os.path.join(out_dir, f"frame_{saved:04d}.jpg")
            # 用 imencode 编码到内存，再用内置 open 写文件，
            # 绕开 cv2.imwrite 在 Windows 中文路径下写失败的已知 bug。
            # quality=100：抽帧即为近无损链路，避免二次压缩丢失细节
            ok_write, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 100])
            if ok_write:
                try:
                    with open(fname, "wb") as f:
                        f.write(buf.tobytes())
                except OSError as e:
                    print(f"[警告] 第 {frame_idx} 帧写文件失败: {fname} ({e})", file=sys.stderr)
                    saved -= 1
            else:
                print(f"[警告] 第 {frame_idx} 帧编码失败: {fname}", file=sys.stderr)
                saved -= 1
            next_capture += interval_frames

        frame_idx += 1

        # 简单进度提示（每 10% 打印一次）
        if total_frames > 0 and frame_idx % max(1, total_frames // 10) == 0:
            pct = 100.0 * frame_idx / total_frames
            print(f"  进度 {pct:5.1f}%  ({frame_idx}/{total_frames})  已存 {saved} 张")

    cap.release()

    print("=== 完成 ===")
    print(f"实际读取帧数 : {frame_idx}")
    print(f"保存图片数   : {saved}")
    print(f"输出目录     : {out_dir}")

    if saved == 0:
        print("[警告] 一张都没抽到，检查视频是否可解码或间隔是否过大。", file=sys.stderr)


if __name__ == "__main__":
    main()
