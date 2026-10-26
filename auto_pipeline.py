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

# 标题关键词过滤（留空列表则不过滤）
TITLE_INCLUDE_KEYWORDS = []  # 标题必须包含其中一个
TITLE_EXCLUDE_KEYWORDS = ["途游斗地主"]  # 标题不能包含其中任何一个

# 脚本路径配置（如果移动了这些文件，在这里修改）
SCRIPTS_DIR = Path("./crawler_suite")  # 改成你实际的目录
DOUYIN_USER_INFO_SCRIPT  = SCRIPTS_DIR / "douyin_user_info.py"
DOUYIN_DOWNLOAD_SCRIPT   = SCRIPTS_DIR / "douyin_download.py"
BILIBILI_UPLOAD_SCRIPT   = SCRIPTS_DIR / "bilibili_upload.py"

# 状态文件路径，记录已上传的 aweme_id，防止重复投稿
STATE_FILE = Path("./state/uploaded.json")
# ==========================


def _utf8_env():
    """让子进程强制使用 UTF-8 输出，并注入项目根路径"""
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["LANG"] = "en_US.UTF-8"
    env["LC_ALL"] = "en_US.UTF-8"

    # 将项目根目录加入 PYTHONPATH，让子进程能找到 douyin_core
    project_root = str(Path(__file__).parent)
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = f"{project_root}{os.pathsep}{existing}" if existing else project_root

    return env


# ---------- 状态管理 ----------

def load_uploaded_ids() -> set:
    """读取已上传的 aweme_id 集合"""
    if not STATE_FILE.exists():
        return set()
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        return set(data.get("uploaded_ids", []))
    except (json.JSONDecodeError, KeyError):
        print(f"[警告] 状态文件损坏，重置为空: {STATE_FILE}")
        return set()


def save_uploaded_id(aweme_id: str, uploaded_ids: set):
    """追加一条已上传记录并写回文件，上传成功后立即调用，防止中途崩溃丢失记录"""
    uploaded_ids.add(aweme_id)
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(
        json.dumps({"uploaded_ids": sorted(uploaded_ids)}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[状态] 已记录 aweme_id: {aweme_id}")


# ==========================

# 获取今日视频信息
def get_today_videos() -> list[dict]:
    """获取目标账号今日发布的视频信息列表"""

    result = subprocess.run(
        [sys.executable,DOUYIN_USER_INFO_SCRIPT,extract_sec_user_id(DOUYIN_USER_URL),
         "-o",
         "-"],
        capture_output=True,text=True,encoding="utf-8",errors="ignore",env=_utf8_env()
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
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

    result = subprocess.run(
        [sys.executable, DOUYIN_DOWNLOAD_SCRIPT, "download", url],
        capture_output=True, text=True, encoding="utf-8", errors="ignore", env=_utf8_env()
    )
    if result.returncode != 0:
        print(f"下载失败: {url}\n{result.stderr}")
        return None

    # 找到最新下载的 mp4 文件（简单策略：mtime 最新）
    mp4_files = sorted(DOWNLOAD_DIR.glob("*.mp4"), key=lambda f: f.stat().st_mtime, reverse=True)
    print(f"已下载视频: {mp4_files[0].name}")
    return mp4_files[0] if mp4_files else None


# 上传视频
def upload_to_bilibili(video_path: Path, title: str, desc: str, source: str) -> bool:
    """上传视频到B站"""
    tags_args = BILI_TAGS
    print(f"\n正在上传：标题：{title} 来源：{source}")
    result = subprocess.run(
        [
            sys.executable, BILIBILI_UPLOAD_SCRIPT, "upload",
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
    # 读取历史已上传记录，用于去重
    uploaded_ids = load_uploaded_ids()
    print(f"[状态] 历史已上传视频数: {len(uploaded_ids)}")

    videos = get_today_videos()
    if not videos:
        print("今日无新视频，退出。")
        sys.exit(0)

    # 去重：跳过已上传的视频
    new_videos = []
    for v in videos:
        aweme_id = v.get("aweme_id", "")
        if aweme_id in uploaded_ids:
            print(f"[跳过] 已上传过: 「{v.get('desc', aweme_id)}」")
        else:
            new_videos.append(v)

    if not new_videos:
        print("今日视频均已上传，退出。")
        sys.exit(0)

    # 关键词过滤
    if TITLE_INCLUDE_KEYWORDS:
        filtered = []
        for v in new_videos:
            desc = v.get("desc", "")
            matched = [kw for kw in TITLE_INCLUDE_KEYWORDS if kw in desc]
            if matched:
                filtered.append(v)
            else:
                print(f"[跳过] 「{desc}」— 不含包含关键词: {TITLE_INCLUDE_KEYWORDS}")
        new_videos = filtered
    if TITLE_EXCLUDE_KEYWORDS:
        filtered = []
        for v in new_videos:
            desc = v.get("desc", "")
            matched = [kw for kw in TITLE_EXCLUDE_KEYWORDS if kw in desc]
            if matched:
                print(f"[跳过] 「{desc}」— 含排除关键词: {matched}")
            else:
                filtered.append(v)
        new_videos = filtered

    print(f"过滤后视频数量: {len(new_videos)}")

    success_count = 0
    fail_count = 0

    for i, video in enumerate(new_videos):
        title = video.get("desc", "抖音视频搬运") or "抖音视频搬运"
        desc = video.get("desc", "")
        desc += "\n\n本视频通过 douyin2bilibili 自动上传，如有错误请联系作者 https://github.com/romcere/douyin2bilibili"
        aweme_id = video.get("aweme_id", "")
        source = f"https://www.douyin.com/video/{aweme_id}" if aweme_id else BILI_SOURCE
        print(f"\n[{i+1}/{len(new_videos)}] 处理视频: {title}")

        video_path = download_video(video)
        if not video_path:
            fail_count += 1
            continue

        ok = upload_to_bilibili(video_path, title, desc, source)
        if ok and aweme_id:
            # 上传成功后立即写入状态，防止中途崩溃导致重复上传
            save_uploaded_id(aweme_id, uploaded_ids)
            success_count += 1
        else:
            fail_count += 1

        # 上传后等待1分钟，最后一个视频不用等
        if i < len(new_videos) - 1:
            print("等待 60 秒后继续下一个视频...")
            time.sleep(60)

    print(f"\n========== 完成 ==========")
    print(f"成功: {success_count}  失败: {fail_count}")

if __name__ == "__main__":
    main()