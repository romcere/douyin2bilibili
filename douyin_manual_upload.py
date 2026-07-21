# -*- coding: utf-8 -*-
"""
抖音人工筛选搬运到 B 站。

流程：用户先输入需要返回的视频数量；程序按页抓取并实时过滤，达到指定数量后立即停止；
已上传视频仍会显示，并在列表中标记；随后由用户选择视频、下载并上传到 B 站。

运行：python crawler_suite/douyin_manual_upload.py
"""

import json
import os
import subprocess
import sys
import time
import unicodedata
from datetime import datetime
from pathlib import Path

from douyin_core.common.tools import extract_sec_user_id

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

# 配置
DOUYIN_USER_URL = "https://www.douyin.com/user/MS4wLjABAAAAsFL91bhVsEDoW39ZsExLDP6vhQ901VeWqx_eANoIMjJM4fKuSnka68tqyBHJs87j"
PAGE_SIZE = 50
DOWNLOAD_DIR = Path("./downloads/douyin_video")

BILI_TID = 138
BILI_COPYRIGHT = 2
BILI_TAGS = ["抖音", "搬运"]

TITLE_INCLUDE_KEYWORDS = []
TITLE_EXCLUDE_KEYWORDS = ["途游斗地主"]

SCRIPTS_DIR = Path("./crawler_suite")
DOUYIN_USER_INFO_SCRIPT = SCRIPTS_DIR / "douyin_user_info.py"
DOUYIN_DOWNLOAD_SCRIPT = SCRIPTS_DIR / "douyin_download.py"
BILIBILI_UPLOAD_SCRIPT = SCRIPTS_DIR / "bilibili_upload.py"

STATE_FILE = Path("./state/uploaded.json")

# 终端表格列宽
# 列宽按照终端实际显示宽度计算，而不是 Python 字符数量
TABLE_COLUMNS = [
    ("编号", 6),
    ("视频ID", 22),
    ("标题", 42),
    ("发布时间", 18),
    ("点赞", 12),
    ("播放", 12),
    ("上传状态", 10),
]


def _utf8_env():
    """设置子进程 UTF-8 环境和项目 PYTHONPATH。"""
    env = os.environ.copy()
    env.update(
        {
            "PYTHONIOENCODING": "utf-8",
            "LANG": "en_US.UTF-8",
            "LC_ALL": "en_US.UTF-8",
        }
    )

    project_root = str(Path(__file__).resolve().parent.parent)
    old_python_path = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = (
        f"{project_root}{os.pathsep}{old_python_path}"
        if old_python_path
        else project_root
    )

    return env


def run_subprocess(command):
    """统一执行子进程。"""
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="ignore",
        env=_utf8_env(),
    )


def load_uploaded_ids():
    """加载已上传的视频 ID，仅用于标记，不用于过滤。"""
    if not STATE_FILE.exists():
        return set()

    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        return {
            str(item)
            for item in data.get("uploaded_ids", [])
        }
    except (OSError, json.JSONDecodeError, TypeError):
        print("[警告] 上传记录读取失败，将按空记录继续运行。")
        return set()


def save_uploaded_id(aweme_id, uploaded_ids):
    """上传成功后保存视频 ID。"""
    uploaded_ids.add(str(aweme_id))
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)

    content = json.dumps(
        {"uploaded_ids": sorted(uploaded_ids)},
        ensure_ascii=False,
        indent=2,
    )

    STATE_FILE.write_text(content, encoding="utf-8")


def input_video_count():
    """获取用户希望返回并展示的视频数量。"""
    while True:
        value = input(
            "\n请输入需要返回并展示的视频数量："
        ).strip()

        if value.isdigit() and int(value) > 0:
            return int(value)

        print("请输入大于 0 的整数。")


def filter_videos(videos, seen_ids):
    """
    过滤：
    1. 分页重复视频
    2. 没有视频 ID 的数据
    3. 标题不符合规则的视频

    已上传视频不会被过滤。
    """
    result = []

    for video in videos:
        aweme_id = str(
            video.get("aweme_id") or ""
        ).strip()

        title = str(
            video.get("desc") or ""
        )

        if not aweme_id or aweme_id in seen_ids:
            continue

        seen_ids.add(aweme_id)

        if TITLE_INCLUDE_KEYWORDS and not any(
            word in title
            for word in TITLE_INCLUDE_KEYWORDS
        ):
            continue

        if TITLE_EXCLUDE_KEYWORDS and any(
            word in title
            for word in TITLE_EXCLUDE_KEYWORDS
        ):
            continue

        result.append(video)

    return result


def get_required_videos(required_count):
    """按页抓取，找到指定数量的可展示视频后立即停止。"""
    sec_user_id = extract_sec_user_id(
        DOUYIN_USER_URL
    )

    print(f"\n目标用户 ID：\n{sec_user_id}")
    print(f"目标展示视频数量：{required_count}")

    display_videos = []
    seen_ids = set()
    cursor = 0
    page_number = 1

    while len(display_videos) < required_count:
        print(
            f"\n正在抓取第 {page_number} 页，"
            f"当前已找到 "
            f"{len(display_videos)}/{required_count} "
            f"条可展示视频..."
        )

        command = [
            sys.executable,
            str(DOUYIN_USER_INFO_SCRIPT),
            sec_user_id,
            "-c",
            str(PAGE_SIZE),
            "-m",
            str(cursor),
            "-o",
            "-",
        ]

        result = run_subprocess(command)

        if result.returncode != 0:
            print("抓取失败：")
            print(
                result.stderr.strip()
                or "子进程未返回错误信息。"
            )
            break

        try:
            response = json.loads(result.stdout)
        except json.JSONDecodeError:
            print("JSON 解析失败，原始输出如下：")
            print(result.stdout)
            break

        data = response.get("data") or {}
        page_videos = data.get("aweme_list") or []

        if not page_videos:
            print("没有获取到更多视频。")
            break

        filtered = filter_videos(
            page_videos,
            seen_ids,
        )

        remaining_count = (
            required_count - len(display_videos)
        )

        display_videos.extend(
            filtered[:remaining_count]
        )

        print(f"本页原始视频：{len(page_videos)} 条")
        print(f"本页符合标题条件：{len(filtered)} 条")
        print(f"累计可展示：{len(display_videos)} 条")

        if len(display_videos) >= required_count:
            print("已达到用户指定数量，停止继续抓取。")
            break

        has_more = bool(
            data.get("has_more", 0)
        )

        next_cursor = data.get("max_cursor")

        if not has_more:
            print("该用户已没有更多作品。")
            break

        if (
            next_cursor in (None, "")
            or str(next_cursor) == str(cursor)
        ):
            print(
                "分页游标无效或未变化，"
                "停止抓取以避免死循环。"
            )
            break

        cursor = next_cursor
        page_number += 1
        time.sleep(1)

    return display_videos


def display_width(text):
    """计算字符串在常见终端中的实际显示宽度。"""
    width = 0

    for char in str(text):
        if unicodedata.combining(char):
            continue

        if unicodedata.east_asian_width(char) in {"W", "F"}:
            width += 2
        else:
            width += 1

    return width


def truncate_display(text, max_width, suffix="..."):
    """
    按终端实际显示宽度截断字符串。

    中文通常占两个显示宽度，英文和数字通常占一个显示宽度。
    """
    text = (
        str(text)
        .replace("\r", " ")
        .replace("\n", " ")
        .replace("\t", " ")
        .strip()
    )

    if display_width(text) <= max_width:
        return text

    suffix_width = display_width(suffix)
    target_width = max(
        0,
        max_width - suffix_width,
    )

    result = []
    current_width = 0

    for char in text:
        if unicodedata.combining(char):
            char_width = 0
        elif unicodedata.east_asian_width(char) in {"W", "F"}:
            char_width = 2
        else:
            char_width = 1

        if current_width + char_width > target_width:
            break

        result.append(char)
        current_width += char_width

    return "".join(result) + suffix


def pad_display(text, width, align="left"):
    """按照终端实际显示宽度补充空格。"""
    text = truncate_display(text, width)
    padding = max(
        0,
        width - display_width(text),
    )

    if align == "right":
        return " " * padding + text

    if align == "center":
        left_padding = padding // 2
        right_padding = padding - left_padding

        return (
            " " * left_padding
            + text
            + " " * right_padding
        )

    return text + " " * padding


def format_number(value):
    """把数字转换为带千位分隔符的文本。"""
    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return str(value or 0)


def show_videos(videos, uploaded_ids):
    """
    展示视频列表。

    列：
    1. 编号
    2. 视频 ID
    3. 标题
    4. 发布时间
    5. 点赞
    6. 播放
    7. 上传状态
    """
    separator_width = (
        sum(width for _, width in TABLE_COLUMNS)
        + len(TABLE_COLUMNS)
        - 1
    )

    separator = "-" * separator_width

    header = " ".join(
        pad_display(name, width)
        for name, width in TABLE_COLUMNS
    )

    print("\n" + separator)
    print(header)
    print(separator)

    for index, video in enumerate(
        videos,
        start=1,
    ):
        aweme_id = str(
            video.get("aweme_id") or ""
        )

        title = str(
            video.get("desc") or ""
        )

        create_time = (
            video.get("create_time") or 0
        )

        publish_time = (
            datetime.fromtimestamp(create_time).strftime(
                "%Y-%m-%d %H:%M"
            )
            if create_time
            else ""
        )

        statistics = (
            video.get("statistics") or {}
        )

        status = (
            "已上传"
            if aweme_id in uploaded_ids
            else "未上传"
        )

        row = [
            pad_display(
                index,
                TABLE_COLUMNS[0][1],
                "right",
            ),
            pad_display(
                aweme_id,
                TABLE_COLUMNS[1][1],
            ),
            pad_display(
                title,
                TABLE_COLUMNS[2][1],
            ),
            pad_display(
                publish_time,
                TABLE_COLUMNS[3][1],
            ),
            pad_display(
                format_number(
                    statistics.get(
                        "digg_count",
                        0,
                    )
                ),
                TABLE_COLUMNS[4][1],
                "right",
            ),
            pad_display(
                format_number(
                    statistics.get(
                        "play_count",
                        0,
                    )
                ),
                TABLE_COLUMNS[5][1],
                "right",
            ),
            pad_display(
                status,
                TABLE_COLUMNS[6][1],
            ),
        ]

        print(" ".join(row))

    print(separator)

    uploaded_count = sum(
        str(video.get("aweme_id") or "")
        in uploaded_ids
        for video in videos
    )

    print(
        f"共展示 {len(videos)} 条，"
        f"其中已上传 {uploaded_count} 条。"
    )


def select_videos(videos, uploaded_ids):
    """
    支持输入：

    1
    1,3,5
    all

    已上传视频仍然允许重新选择和上传。
    """
    while True:
        choice = input(
            "\n请输入上传编号，例如 1、1,3,5 或 all："
            "\n选择："
        ).strip()

        if choice.lower() == "all":
            selected = videos
        else:
            try:
                indexes = [
                    int(item.strip()) - 1
                    for item in choice.split(",")
                ]

                if not indexes or any(
                    index < 0
                    or index >= len(videos)
                    for index in indexes
                ):
                    raise ValueError

                selected = []
                selected_indexes = set()

                for index in indexes:
                    if index in selected_indexes:
                        continue

                    selected.append(videos[index])
                    selected_indexes.add(index)

            except ValueError:
                print("选择无效，请输入有效编号。")
                continue

        repeated = [
            video
            for video in selected
            if str(video.get("aweme_id") or "")
            in uploaded_ids
        ]

        if repeated:
            print(
                f"\n[提示] 本次选择中有 "
                f"{len(repeated)} 条视频已上传过，"
                f"仍将按你的选择重新上传："
            )

            for video in repeated:
                aweme_id = str(
                    video.get("aweme_id") or ""
                )

                title = truncate_display(
                    video.get("desc") or "",
                    60,
                )

                print(
                    f"- {aweme_id}  {title}"
                )

        return selected


def download_video(video):
    """调用 douyin_download.py 下载视频。"""
    aweme_id = str(
        video.get("aweme_id") or ""
    )

    title = str(
        video.get("desc") or "无标题视频"
    )

    url = (
        f"https://www.douyin.com/video/"
        f"{aweme_id}"
    )

    print(f"\n正在下载：\n{title}")

    DOWNLOAD_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    download_started_at = time.time()

    result = run_subprocess(
        [
            sys.executable,
            str(DOUYIN_DOWNLOAD_SCRIPT),
            "download",
            url,
        ]
    )

    if result.returncode != 0:
        print("下载失败：")
        print(
            result.stderr.strip()
            or "子进程未返回错误信息。"
        )
        return None

    files = sorted(
        (
            file
            for file in DOWNLOAD_DIR.glob("*.mp4")
            if file.stat().st_mtime
            >= download_started_at - 2
        ),
        key=lambda file: file.stat().st_mtime,
        reverse=True,
    )

    if not files:
        print(
            "下载脚本执行成功，"
            "但未找到本次新生成的 MP4 文件。"
        )
        return None

    return files[0]


def upload_to_bilibili(video_path, video):
    """调用 bilibili_upload.py 上传视频。"""
    title = (
        str(
            video.get("desc") or "抖音搬运"
        ).strip()
        or "抖音搬运"
    )

    aweme_id = str(
        video.get("aweme_id") or ""
    )

    source = (
        f"https://www.douyin.com/video/"
        f"{aweme_id}"
    )

    desc = (
        f"{title}\n\n"
        f"本视频由自动搬运工具上传"
    )

    print(f"\n正在上传 B 站：\n{title}")

    command = [
        sys.executable,
        str(BILIBILI_UPLOAD_SCRIPT),
        "upload",
        "--file",
        str(video_path),
        "--title",
        title[:80],
        "--tid",
        str(BILI_TID),
        "--tags",
        *BILI_TAGS,
        "--desc",
        desc[:250],
        "--copyright",
        str(BILI_COPYRIGHT),
        "--source",
        source,
    ]

    result = run_subprocess(command)

    if result.returncode != 0:
        print("上传失败：")
        print(
            result.stderr.strip()
            or "子进程未返回错误信息。"
        )
        return False

    if result.stdout.strip():
        print(result.stdout.strip())

    return True


def main():
    required_count = input_video_count()
    uploaded_ids = load_uploaded_ids()

    videos = get_required_videos(
        required_count
    )

    print(
        f"\n最终找到可展示视频："
        f"{len(videos)} 条"
    )

    if not videos:
        print("没有符合条件的可展示视频。")
        return

    if len(videos) < required_count:
        print(
            f"提示：要求 {required_count} 条，"
            f"但实际只找到 {len(videos)} 条"
            f"符合条件的视频。"
        )

    show_videos(
        videos,
        uploaded_ids,
    )

    selected_videos = select_videos(
        videos,
        uploaded_ids,
    )

    print(
        f"\n已选择 "
        f"{len(selected_videos)} 条视频。"
    )

    for index, video in enumerate(
        selected_videos,
        start=1,
    ):
        aweme_id = str(
            video.get("aweme_id") or ""
        )

        status = (
            "已上传过，将重新上传"
            if aweme_id in uploaded_ids
            else "未上传"
        )

        print("\n" + "=" * 60)

        print(
            f"正在处理 "
            f"{index}/{len(selected_videos)}"
            f"｜视频 ID：{aweme_id}"
            f"｜状态：{status}"
        )

        print(
            str(video.get("desc") or "")
        )

        file_path = download_video(video)

        if not file_path:
            print("下载失败，跳过当前视频。")
            continue

        success = upload_to_bilibili(
            file_path,
            video,
        )

        if success:
            save_uploaded_id(
                aweme_id,
                uploaded_ids,
            )

            print(
                "上传成功，已更新上传记录。"
            )
        else:
            print(
                "上传失败，未更新上传记录。"
            )

        if index < len(selected_videos):
            print(
                "等待 10 秒后继续处理下一条视频..."
            )
            time.sleep(10)

    print("\n全部处理完成。")


if __name__ == "__main__":
    main()