# 抖音当天视频自动搬运到B站
import subprocess
import json
import os
from datetime import date
from pathlib import Path
from douyin_core.common.tools import extract_sec_user_id, is_today, is_yesterday
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")
# ========== 配置 ==========
DOUYIN_USER_URL = "https://www.douyin.com/user/MS4wLjABAAAAsFL91bhVsEDoW39ZsExLDP6vhQ901VeWqx_eANoIMjJM4fKuSnka68tqyBHJs87j?from_tab_name=main"  # 替换为目标抖音用户主页链接
DOWNLOAD_DIR = Path("./downloads/douyin_video")
BILI_TID = 138  # B站分区ID，138=搞笑，自行调整
BILI_COPYRIGHT = 2  # 2=转载
BILI_SOURCE = DOUYIN_USER_URL
BILI_TAGS = ["抖音", "搬运"]


def _utf8_env():
    """让子进程强制使用 UTF-8 输出"""
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    return env


# ==========================

def get_today_videos() -> list[dict]:
    """获取目标账号今日发布的视频信息列表"""

    result = subprocess.run(
        [
            "python",
            "douyin_user_info.py",
            extract_sec_user_id(DOUYIN_USER_URL),
            "-o",
            "-"
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="ignore",
        env=_utf8_env()
    )

    if result.returncode != 0:
        print("获取视频信息失败:", result.stderr)
        return []

    # 清理可能的多余输出（避免 stdout 混入日志）
    raw = result.stdout.strip()

    try:
        res = json.loads(raw)
        data = res.get("data", {})
    except json.JSONDecodeError:
        print("JSON解析失败，原始输出如下：")
        print(raw)
        return []
    # 找到视频列表
    all_videos = data.get("aweme_list", [])
    # 获取当前用户的信息
    nickname = all_videos[0].get("author", {}).get("nickname", "未知")
    print(f"正在获取 {nickname} 的视频...")
    today_videos = []
    for v in all_videos:
        # 从 result 中找到 create_time
        create_time = v.get("create_time")
        if isinstance(create_time, (int, float)):
            # if is_yesterday(create_time):
            #     today_videos.append(v)
            if is_today(create_time):
                today_videos.append(v)

        elif isinstance(create_time, str):
            # 兼容字符串时间（兜底）
            if date.today().isoformat() in create_time:
                today_videos.append(v)
    print(f"今日新视频数量: {len(today_videos)}")
    return today_videos


def download_video(video: dict) -> Path | None:
    """下载单个无水印视频，返回本地文件路径"""
    url = video.get("share_url") or video.get("aweme_id")  # 根据实际字段调整
    DOWNLOAD_DIR.mkdir(exist_ok=True)

    result = subprocess.run(
        ["python", "douyin_download.py", "download", url],
        capture_output=True, text=True, encoding="utf-8", errors="ignore", cwd=".", env=_utf8_env()
    )
    if result.returncode != 0:
        print(f"下载失败: {url}\n{result.stderr}")
        return None

    # 找到最新下载的 mp4 文件（简单策略：mtime 最新）
    mp4_files = sorted(DOWNLOAD_DIR.glob("*.mp4"), key=lambda f: f.stat().st_mtime, reverse=True)
    print(f"已下载视频: {mp4_files[0].name}")
    return mp4_files[0] if mp4_files else None


def upload_to_bilibili(video_path: Path, title: str, desc: str):
    """上传视频到B站"""
    tags_args = BILI_TAGS
    print(f"\n正在上传：标题：{title} 来源：{BILI_SOURCE}")
    result = subprocess.run(
        [
            "python", "bilibili_upload.py", "upload",
            "--file", str(video_path),
            "--title", title[:80],  # B站标题限80字
            "--tid", str(BILI_TID),
            "--tags", *tags_args,
            "--desc", desc[:250],
            "--copyright", str(BILI_COPYRIGHT),
            "--source", BILI_SOURCE,
        ],
        capture_output=True, text=True, encoding="utf-8", errors="ignore", env=_utf8_env()
    )
    if result.returncode != 0:
        print(f"上传失败: {video_path.name}\n{result.stderr}")
        return False
    print(f"上传成功: {video_path.name}")
    return True


def main():
    global BILI_SOURCE
    videos = get_today_videos()
    if not videos:
        print("今日无新视频，退出。")
        sys.exit(0)

    for video in videos:
        title = video.get("desc", "抖音视频搬运")
        desc = video.get("desc", "")
        BILI_SOURCE = "https://www.douyin.com/video/" + str(video.get("aweme_id", ""))
        print(f"处理视频: {title}")

        video_path = download_video(video)
        if not video_path:
            continue

        upload_to_bilibili(video_path, title, desc)

        # 上传完成后删除本地文件，节省磁盘
        video_path.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
