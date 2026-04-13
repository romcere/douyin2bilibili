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
# Modifications by romcere, 2026
#
# Changes made:
# - 新增 get_douyin_headers() 方法，该方法遵循 Apache 2.0 许可证
# - 将该文件重构为独立方法模块，移除 FastAPI 依赖
# ==============================================================================
import os
import zipfile
import asyncio
import aiofiles
import httpx
from core.web_crawler import DouyinWebCrawler
from config.settings import CONFIG
# ── 读取配置文件 ────────────────────────────────────────
config = CONFIG
async def fetch_data_stream(
    url: str,
    headers: dict = None,
    file_path: str = None,
) -> bool:
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

# ── HybridCrawler（延迟导入，避免在不需要时引入依赖） ──────────────────────
def _get_crawler():
    from core.hybrid_crawler import HybridCrawler  # noqa: PLC0415
    return HybridCrawler()

# ── 核心下载函数（原 router 端点的逻辑，完全解耦） ────────────────────────────
async def download_file(
    url: str,
    prefix: bool = True,
    with_watermark: bool = False
) -> str | None:
    """
    下载抖音 | TikTok | Bilibili 视频 / 图片。
    Parameters
    ----------
    url          : 视频或图片的分享链接
    prefix       : 是否为输出文件名添加配置文件中定义的前缀
    with_watermark: 是否下载带水印版本（Bilibili 无效）

    Returns
    -------
    成功时返回本地文件路径（str），失败时返回 None。
    """
    # ── 检查开关 ────────────────────────────────────────────────────────────
    if not config["API"]["Download_Switch"]:
        print("Download endpoint is disabled in the configuration file.")
        return None

    # ── 解析数据 ─────────────────────────────────────────────────────────────
    crawler = _get_crawler()
    try:
        data = await crawler.hybrid_parsing_single_video(url, minimal=True)
    except Exception as e:
        print(f"解析失败: {e}")
        return None

    # ── 下载逻辑 ─────────────────────────────────────────────────────────────
    try:
        data_type = data.get("type")
        platform = data.get("platform")
        video_id = data.get("video_id")
        file_prefix = config["API"]["Download_File_Prefix"] if prefix else ""
        download_path = os.path.join(
            config["API"]["Download_Path"], f"{platform}_{data_type}"
        )
        os.makedirs(download_path, exist_ok=True)

        # ── 视频 ────────────────────────────────────────────────────────────
        if data_type == "video":
            suffix = "_watermark.mp4" if with_watermark else ".mp4"
            file_name = f"{file_prefix}{platform}_{video_id}{suffix}"
            file_path = os.path.join(download_path, file_name)

            if os.path.exists(file_path):
                print(f"文件已存在，直接返回: {file_path}")
                return file_path

            __headers = await DouyinWebCrawler.get_douyin_headers()

            video_url = (
                data["video_data"]["nwm_video_url_HQ"]
                if not with_watermark
                else data["video_data"]["wm_video_url_HQ"]
            )
            success = await fetch_data_stream(
                url=video_url,
                headers=__headers,
                file_path=file_path
            )

            if not success:
                print("下载视频失败")
                return None

            print(f"视频已保存到: {file_path}")
            return file_path

        # ── 图片（打包为 zip） ───────────────────────────────────────────────
        elif data_type == "image":
            wm_tag = "_watermark" if with_watermark else ""
            zip_file_name = f"{file_prefix}{platform}_{video_id}_images{wm_tag}.zip"
            zip_file_path = os.path.join(download_path, zip_file_name)

            if os.path.exists(zip_file_path):
                print(f"压缩包已存在，直接返回: {zip_file_path}")
                return zip_file_path

            urls = (
                data["image_data"]["no_watermark_image_list"]
                if not with_watermark
                else data["image_data"]["watermark_image_list"]
            )
            image_file_list = []
            for idx, img_url in enumerate(urls):
                # 图片下载
                async with httpx.AsyncClient() as client:
                    response = await client.get(img_url)
                    response.raise_for_status()
                content_type = response.headers.get("content-type", "image/jpeg")
                file_format = content_type.split("/")[1]
                img_name = f"{file_prefix}{platform}_{video_id}_{idx + 1}{wm_tag}.{file_format}"
                img_path = os.path.join(download_path, img_name)
                image_file_list.append(img_path)
                async with aiofiles.open(img_path, "wb") as out_file:
                    await out_file.write(response.content)

            with zipfile.ZipFile(zip_file_path, "w") as zf:
                for img_path in image_file_list:
                    zf.write(img_path, os.path.basename(img_path))

            print(f"图片压缩包已保存到: {zip_file_path}")
            return zip_file_path

        else:
            print(f"不支持的数据类型: {data_type}")
            return None

    except Exception as e:
        print(f"下载过程中出现异常: {e}")
        return None

# ── 入口 ─────────────────────────────────────────────────────────────────────
async def main():
    # 在这里修改目标 URL 和参数
    target_url = "https://www.douyin.com/video/7628183120067779d675?modeFrom="

    result = await download_file(
        url=target_url,
        prefix=True,
        with_watermark=False,
    )
    if result:
        print(f"\n✓ 下载成功: {result}")
    else:
        print("\n✗ 下载失败")


if __name__ == "__main__":
    asyncio.run(main())