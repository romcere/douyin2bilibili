# ==============================================================================
# Copyright (C) 2021 Evil0ctal
#
# This file is part of the Douyin_TikTok_Download_API project.
#
# This project is licensed under the Apache License 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at:
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ==============================================================================
# Modifications by Romcere, 2026
#
# Changes made:
# - 新增 get_douyin_headers() 方法，该方法遵循 Apache 2.0 许可证
# - 将该文件重构为独立方法模块，移除 FastAPI 依赖
# - 新增 CLI 支持：info / download 两种模式
# ==============================================================================
"""
抖音视频解析与下载工具
基于 Douyin_TikTok_Download_API 项目封装的 CLI 工具，支持 抖音 内容解析与下载

使用方法:
  1. 手动配置`config/douyin_config.yaml`文件中的抖音`cookie`

  2. 获取精简视频信息
       python -m crawler_suite.douyin_download info <视频链接>

  3. 下载无水印视频（默认）
       python -m crawler_suite.douyin_download download <视频链接>

"""
import os
import json
import zipfile
import asyncio
import argparse
import sys
import subprocess
from pathlib import Path
import aiofiles
import httpx
from douyin_core.web_crawler import DouyinWebCrawler
from config.settings import CONFIG as SETTINGS_CONFIG

config = SETTINGS_CONFIG
USER_INFO_PATH = Path(__file__).resolve().parent / "output" / "user_info.json"
MIN_DURATION_TOLERANCE_SECONDS = 3.0
DURATION_TOLERANCE_RATIO = 0.01

# 直接运行时使用的配置区
# command 可选值：info / download
RUN_CONFIG = {
    "command": "download",
    "url": "https://www.douyin.com/video/7664531280838642978",
    "info_minimal": True,
    "info_output": "config/douyin_info.json",
    "download_with_watermark": False,
    "download_no_prefix": False,
    "download_switch": config["API"].get("Download_Switch", True),
    "download_file_prefix": config["API"].get("Download_File_Prefix", ""),
    "download_path": config["API"].get("Download_Path", "downloads"),
}


# ── 流式下载 ──────────────────────────────────────────────────────────────────
async def fetch_data_stream(url: str, headers: dict = None, file_path: str = None) -> bool:
    headers = (
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/91.0.4472.124 Safari/537.36"
            )
        }
        if headers is None
        else headers.get("headers")
    )
    async with httpx.AsyncClient() as client:
        async with client.stream("GET", url, headers=headers) as response:
            response.raise_for_status()
            async with aiofiles.open(file_path, "wb") as out_file:
                async for chunk in response.aiter_bytes():
                    await out_file.write(chunk)
    return True


def get_expected_duration_seconds(aweme_id: str) -> float:
    """从 user_info.json 读取当前作品的 aweme.duration（毫秒）并转换为秒。"""
    try:
        content = json.loads(USER_INFO_PATH.read_text(encoding="utf-8"))
        aweme_list = content["data"]["aweme_list"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise RuntimeError(f"无法读取用户作品时长文件 {USER_INFO_PATH}: {exc}") from exc

    for aweme in aweme_list:
        if str(aweme.get("aweme_id")) != str(aweme_id):
            continue

        try:
            duration_ms = float(aweme["duration"])
        except (KeyError, TypeError, ValueError) as exc:
            raise RuntimeError(f"作品 {aweme_id} 缺少有效 duration") from exc

        if duration_ms <= 0:
            raise RuntimeError(f"作品 {aweme_id} 的 duration 无效: {duration_ms}")
        return duration_ms / 1000.0

    raise RuntimeError(f"user_info.json 中未找到作品 {aweme_id}")


def get_local_video_duration_seconds(file_path: str) -> float:
    """使用 ffprobe 读取本地 MP4 实际时长。"""
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                file_path,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("未找到 ffprobe，无法校验视频时长") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("ffprobe 读取视频时长超时") from exc

    if result.returncode != 0:
        raise RuntimeError(f"ffprobe 无法解析视频: {result.stderr.strip()}")

    try:
        duration = float(result.stdout.strip())
    except ValueError as exc:
        raise RuntimeError(f"ffprobe 未返回有效时长: {result.stdout!r}") from exc

    if duration <= 0:
        raise RuntimeError(f"ffprobe 返回无效时长: {duration}")
    return duration


def is_duration_complete(expected_seconds: float, actual_seconds: float) -> bool:
    """允许少量容器/时间基误差，但拒绝明显短于接口时长的视频。"""
    tolerance = max(
        MIN_DURATION_TOLERANCE_SECONDS,
        expected_seconds * DURATION_TOLERANCE_RATIO,
    )
    return actual_seconds >= expected_seconds - tolerance


# ── HybridCrawler 延迟导入 ────────────────────────────────────────────────────
def _get_crawler():
    from douyin_core.hybrid_crawler import HybridCrawler
    return HybridCrawler()


# ── 解析视频数据 ──────────────────────────────────────────────────────────────
async def fetch_info(url: str, minimal: bool = False) -> dict | None:
    """
    仅解析并返回视频/图片元数据，不执行下载。

    Parameters
    ----------
    url     : 分享链接
    minimal : True → 返回精简字段；False → 返回完整原始数据
    """
    crawler = _get_crawler()
    try:
        data = await crawler.hybrid_parsing_single_video(url, minimal=minimal)
        return data
    except Exception as e:
        print(f"[错误] 解析失败: {e}")
        return None


# ── 下载视频 / 图片 ───────────────────────────────────────────────────────────
async def download_file(url: str, prefix: bool = True, with_watermark: bool = False) -> str | None:
    """
    下载抖音 视频 / 图片。

    Returns
    -------
    成功时返回本地文件路径（str），失败时返回 None。
    """
    if not config["API"]["Download_Switch"]:
        print("[错误] 配置文件中下载功能已关闭。")
        return None

    crawler = _get_crawler()
    try:
        data = await crawler.hybrid_parsing_single_video(url, minimal=True)
    except Exception as e:
        print(f"[错误] 解析失败: {e}")
        return None

    try:
        data_type   = data.get("type")
        platform    = data.get("platform")
        video_id    = data.get("video_id")
        file_prefix = config["API"]["Download_File_Prefix"] if prefix else ""
        download_path = os.path.join(
            config["API"]["Download_Path"], f"{platform}_{data_type}"
        )
        os.makedirs(download_path, exist_ok=True)

        # ── 视频 ──────────────────────────────────────────────────────────
        if data_type == "video":
            suffix    = "_watermark.mp4" if with_watermark else ".mp4"
            file_name = f"{file_prefix}{platform}_{video_id}{suffix}"
            file_path = os.path.join(download_path, file_name)
            expected_seconds = get_expected_duration_seconds(video_id)

            if os.path.exists(file_path):
                try:
                    actual_seconds = get_local_video_duration_seconds(file_path)
                    if is_duration_complete(expected_seconds, actual_seconds):
                        print(
                            f"[跳过] 文件已存在且时长完整: {file_path} "
                            f"({actual_seconds:.3f}s / 预期 {expected_seconds:.3f}s)"
                        )
                        return file_path
                    print(
                        f"[WARN] 已存在文件时长不足，将重新下载: "
                        f"{actual_seconds:.3f}s / 预期 {expected_seconds:.3f}s"
                    )
                except Exception as exc:
                    print(f"[WARN] 已存在文件校验失败，将重新下载: {exc}")
                os.remove(file_path)

            attempt = 0
            while True:
                attempt += 1
                try:
                    __headers = await DouyinWebCrawler.get_douyin_headers()
                    video_url = (
                        data["video_data"]["nwm_video_url_HQ"]
                        if not with_watermark
                        else data["video_data"]["wm_video_url_HQ"]
                    )
                    print(f"[下载] 第 {attempt} 次 → {file_path}")
                    success = await fetch_data_stream(
                        url=video_url,
                        headers=__headers,
                        file_path=file_path,
                    )
                    if not success:
                        raise RuntimeError("视频下载请求未成功")

                    actual_seconds = get_local_video_duration_seconds(file_path)
                    if is_duration_complete(expected_seconds, actual_seconds):
                        print(
                            f"[完成] 视频已保存: {file_path} "
                            f"({actual_seconds:.3f}s / 预期 {expected_seconds:.3f}s)"
                        )
                        return file_path

                    raise RuntimeError(
                        f"视频时长不足: 实际 {actual_seconds:.3f}s，"
                        f"预期 {expected_seconds:.3f}s"
                    )
                except Exception as exc:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                    print(f"[WARN] 第 {attempt} 次下载或时长校验失败: {exc}")
                    print("[重试] 将重新下载当前视频。")
                    await asyncio.sleep(min(attempt * 2, 60))

        # ── 图片（打包为 zip） ─────────────────────────────────────────────
        elif data_type == "image":
            wm_tag        = "_watermark" if with_watermark else ""
            zip_file_name = f"{file_prefix}{platform}_{video_id}_images{wm_tag}.zip"
            zip_file_path = os.path.join(download_path, zip_file_name)

            if os.path.exists(zip_file_path):
                print(f"[跳过] 压缩包已存在: {zip_file_path}")
                return zip_file_path

            urls = (
                data["image_data"]["no_watermark_image_list"]
                if not with_watermark
                else data["image_data"]["watermark_image_list"]
            )
            image_file_list = []
            for idx, img_url in enumerate(urls):
                async with httpx.AsyncClient() as client:
                    response = await client.get(img_url)
                    response.raise_for_status()
                content_type = response.headers.get("content-type", "image/jpeg")
                file_format  = content_type.split("/")[1]
                img_name     = f"{file_prefix}{platform}_{video_id}_{idx + 1}{wm_tag}.{file_format}"
                img_path     = os.path.join(download_path, img_name)
                image_file_list.append(img_path)
                print(f"[下载] 图片 {idx + 1}/{len(urls)} → {img_path}")
                async with aiofiles.open(img_path, "wb") as out_file:
                    await out_file.write(response.content)

            with zipfile.ZipFile(zip_file_path, "w") as zf:
                for img_path in image_file_list:
                    zf.write(img_path, os.path.basename(img_path))

            print(f"[完成] 图片压缩包已保存: {zip_file_path}")
            return zip_file_path

        else:
            print(f"[错误] 不支持的数据类型: {data_type}")
            return None

    except Exception as e:
        print(f"[错误] 下载过程中出现异常: {e}")
        return None


# ── CLI 入口 ──────────────────────────────────────────────────────────────────
# 直接运行配置辅助
def _sync_runtime_download_config() -> None:
    """将顶部运行配置同步到现有配置对象，尽量不影响原有逻辑。"""
    config.setdefault("API", {})
    config["API"]["Download_Switch"] = RUN_CONFIG["download_switch"]
    config["API"]["Download_File_Prefix"] = RUN_CONFIG["download_file_prefix"]
    config["API"]["Download_Path"] = RUN_CONFIG["download_path"]


def _print_startup_banner() -> None:
    print("=" * 20)
    print("抖音视频工具启动")
    print("=" * 20)
    print(f"当前模式：{RUN_CONFIG['command']}")
    print(f"目标链接：{RUN_CONFIG['url']}")
    print(f"下载开关：{RUN_CONFIG['download_switch']}")
    print(f"下载前缀：{RUN_CONFIG['download_file_prefix']}")
    print(f"下载目录：{RUN_CONFIG['download_path']}")
    print(f"带水印：{RUN_CONFIG['download_with_watermark']}")
    print(f"输出文件：{RUN_CONFIG['info_output']}")
    print("开始执行...\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="douyin_cli",
        description="抖音 / TikTok / Bilibili 视频工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 查看视频元数据（精简）
  python douyin_cli.py info https://www.douyin.com/video/xxx

  # 查看完整原始数据
  python douyin_cli.py info https://www.douyin.com/video/xxx --full

  # 将数据保存为 JSON 文件
  python douyin_cli.py info https://www.douyin.com/video/xxx --output data.json

  # 下载视频（无水印）
  python douyin_cli.py download https://www.douyin.com/video/xxx

  # 下载视频（带水印）
  python douyin_cli.py download https://www.douyin.com/video/xxx --watermark

  # 下载时不添加文件名前缀
  python douyin_cli.py download https://www.douyin.com/video/xxx --no-prefix
        """,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # ── info 子命令 ────────────────────────────────────────────────────────
    info_parser = subparsers.add_parser("info", help="查看视频 / 图片元数据")
    info_parser.add_argument("url", help="分享链接")
    info_parser.add_argument(
        "--full", action="store_true",
        help="返回完整原始数据（默认为精简模式）"
    )
    info_parser.add_argument(
        "--output", "-o", metavar="FILE",
        help="将 JSON 结果保存到指定文件"
    )

    # ── download 子命令 ────────────────────────────────────────────────────
    dl_parser = subparsers.add_parser("download", help="下载视频 / 图片")
    dl_parser.add_argument("url", help="分享链接")
    dl_parser.add_argument(
        "--watermark", action="store_true",
        help="下载带水印版本（默认无水印）"
    )
    dl_parser.add_argument(
        "--no-prefix", action="store_true",
        help="文件名不添加配置前缀"
    )

    return parser


async def cmd_info(args: argparse.Namespace) -> None:
    minimal = not args.full
    print(f"[解析] {'精简' if minimal else '完整'}模式 → {args.url}\n")
    data = await fetch_info(args.url, minimal=minimal)
    if data is None:
        return

    output = json.dumps(data, ensure_ascii=False, indent=2)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"[完成] 数据已保存到: {args.output}")
    else:
        print(output)


async def cmd_download(args: argparse.Namespace) -> None:
    print(f"[解析] 准备下载 → {args.url}")
    result = await download_file(
        url=args.url,
        prefix=not args.no_prefix,
        with_watermark=args.watermark,
    )
    if result:
        print(f"\n✓ 下载成功: {result}")
    else:
        print("\n✗ 下载失败")


async def _run_with_config() -> None:
    _print_startup_banner()
    if not RUN_CONFIG["url"]:
        print("[ERROR] 请先在文件顶部 RUN_CONFIG 中填写 url")
        return

    _sync_runtime_download_config()

    command = RUN_CONFIG["command"]
    if command == "info":
        args = argparse.Namespace(
            url=RUN_CONFIG["url"],
            full=not RUN_CONFIG["info_minimal"],
            output=RUN_CONFIG["info_output"],
        )
        await cmd_info(args)
        return

    if command == "download":
        args = argparse.Namespace(
            url=RUN_CONFIG["url"],
            watermark=RUN_CONFIG["download_with_watermark"],
            no_prefix=RUN_CONFIG["download_no_prefix"],
        )
        await cmd_download(args)
        return

    print(f"[ERROR] 不支持的 command: {command}")


async def _run_cli(args: argparse.Namespace) -> None:
    if args.command == "info":
        await cmd_info(args)
    elif args.command == "download":
        await cmd_download(args)


def main(args=None) -> int:
    if args is None:
        if len(sys.argv) > 1:
            parser = build_parser()
            args = parser.parse_args()
            try:
                asyncio.run(_run_cli(args))
            except Exception as e:
                print(f"[ERROR] 执行失败：{e}")
                return 1
            return 0

        try:
            asyncio.run(_run_with_config())
        except Exception as e:
            print(f"[ERROR] 执行失败：{e}")
            return 1
        return 0

    if isinstance(args, dict):
        args = argparse.Namespace(**args)

    try:
        asyncio.run(_run_cli(args))
    except Exception as e:
        print(f"[ERROR] 执行失败：{e}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
