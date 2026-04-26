# 抖音当天视频自动搬运到B站
import subprocess
import json
import os
from datetime import date
from pathlib import Path
from douyin_core.common.tools import extract_sec_user_id, is_today, is_yesterday
import sys
import time
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")
# ========== 配置 ==========
DOUYIN_USER_URL = "https://www.douyin.com/user/MS4wLjABAAAAsFL91bhVsEDoW39ZsExLDP6vhQ901VeWqx_eANoIMjJM4fKuSnka68tqyBHJs87j?from_tab_name=main"  # 替换为目标抖音用户主页链接

DOWNLOAD_DIR = Path("./downloads/douyin_video") # 视频下载目录（该路径配置来自 crawler_suite/douyin_download.py ，此处仅作print作用）
BILI_TID = 138  # B站分区ID，138=搞笑，自行调整
BILI_COPYRIGHT = 2  # 2=转载
BILI_SOURCE = DOUYIN_USER_URL # 转载来源
BILI_TAGS = ["抖音", "搬运"] # 默认标签

# 脚本路径配置（如果移动了这些文件，在这里修改）
SCRIPTS_DIR = Path("./crawler_suite")  # 改成你实际的目录
DOUYIN_USER_INFO_SCRIPT  = SCRIPTS_DIR / "douyin_user_info.py"
DOUYIN_DOWNLOAD_SCRIPT   = SCRIPTS_DIR / "douyin_download.py"
BILIBILI_UPLOAD_SCRIPT   = SCRIPTS_DIR / "bilibili_upload.py"

def _utf8_env():
    """让子进程强制使用 UTF-8 输出"""
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    return env
# ==========================

# 获取今日视频信息
def get_today_videos() -> list[dict]:
    """获取目标账号今日发布的视频信息列表"""

    result = subprocess.run(
        [
            "python",
            DOUYIN_USER_INFO_SCRIPT,
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
# 下载视频
def download_video(video: dict) -> Path | None:
    """下载单个无水印视频，返回本地文件路径"""
    url = video.get("share_url") or video.get("aweme_id")  # 根据实际字段调整
    DOWNLOAD_DIR.mkdir(exist_ok=True)

    result = subprocess.run(
        ["python", DOUYIN_DOWNLOAD_SCRIPT, "download", url],
        capture_output=True, text=True, encoding="utf-8", errors="ignore", cwd=".", env=_utf8_env()
    )
    if result.returncode != 0:
        print(f"下载失败: {url}\n{result.stderr}")
        return None

    # 找到最新下载的 mp4 文件（简单策略：mtime 最新）
    mp4_files = sorted(DOWNLOAD_DIR.glob("*.mp4"), key=lambda f: f.stat().st_mtime, reverse=True)
    print(f"已下载视频: {mp4_files[0].name}")
    return mp4_files[0] if mp4_files else None
# 上传视频
def upload_to_bilibili(video_path: Path, title: str, desc: str, source: str):
    """上传视频到B站"""
    tags_args = BILI_TAGS
    print(f"\n正在上传：标题：{title} 来源：{source}")
    result = subprocess.run(
        [
            "python", BILIBILI_UPLOAD_SCRIPT, "upload",
            "--file", str(video_path),
            "--title", title[:80],  # B站标题限80字
            "--tid", str(BILI_TID),
            "--tags", *tags_args,
            "--desc", desc[:250],
            "--copyright", str(BILI_COPYRIGHT),
            "--source", source,
        ],
        capture_output=True, text=True, encoding="utf-8", errors="ignore", env=_utf8_env()
    )
    if result.returncode != 0:
        print(f"上传失败: {video_path.name}\n{result.stderr}")
        return False
    print(f"上传成功: {video_path.name}")
    return True

def main():
    videos = get_today_videos()
    if not videos:
        print("今日无新视频，退出。")
        sys.exit(0)

    for i,video in enumerate(videos):
        title = video.get("desc", "抖音视频搬运")
        desc = video.get("desc", "")
        aweme_id = video.get("aweme_id")
        source = f"https://www.douyin.com/video/{aweme_id}" if aweme_id else BILI_SOURCE
        print(f"处理视频: {title}")

        video_path = download_video(video)
        if not video_path:
            continue
        upload_to_bilibili(video_path, title, desc, source)
        # 上传后等待1分钟，最后一个视频不用等
        if i < len(videos) - 1:
            print("等待 60 秒后继续下一个视频...")
            time.sleep(60)

if __name__ == "__main__":
    main()
