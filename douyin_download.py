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
import os
import json
import zipfile
import asyncio
import argparse
import aiofiles
import httpx
from douyin_core.web_crawler import DouyinWebCrawler
from config.settings import CONFIG

config = CONFIG


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
    下载抖音 | TikTok | Bilibili 视频 / 图片。

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

            if os.path.exists(file_path):
                print(f"[跳过] 文件已存在: {file_path}")
                return file_path

            __headers = await DouyinWebCrawler.get_douyin_headers()
            video_url = (
                data["video_data"]["nwm_video_url_HQ"]
                if not with_watermark
                else data["video_data"]["wm_video_url_HQ"]
            )
            print(f"[下载] 视频 → {file_path}")
            success = await fetch_data_stream(url=video_url, headers=__headers, file_path=file_path)
            if not success:
                print("[错误] 视频下载失败")
                return None
            print(f"[完成] 视频已保存: {file_path}")
            return file_path

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


async def _main() -> None:
    parser = build_parser()
    args   = parser.parse_args()

    if args.command == "info":
        await cmd_info(args)
    elif args.command == "download":
        await cmd_download(args)


if __name__ == "__main__":
    asyncio.run(_main())