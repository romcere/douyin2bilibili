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
# - 修改部分代码为静态方法
# - 改造为 Python CLI 形式运行
# ==============================================================================
"""
抖音用户作品获取脚本
基于 Douyin_TikTok_Download_API 封装的用户主页数据抓取工具

使用方法:
  1. 通过用户主页的 URL 获取 sec_user_id

  2. 获取用户作品数据（默认获取 5 条，不包含置顶）:
       python -m crawler_suite.douyin_user_info <sec_user_id> -c 5 -m 0

  3. 输出到控制台（stdout）:
       python -m crawler_suite.douyin_user_info <sec_user_id> -o -

"""
import asyncio
import argparse
import json
import sys
from douyin_core.web_crawler import DouyinWebCrawler

crawler = DouyinWebCrawler()

# 直接运行时使用的配置区
# 只需要修改这里，就可以不传命令行参数直接启动脚本
RUN_CONFIG = {
    "sec_user_id": "MS4wLjABAAAAsFL91bhVsEDoW39ZsExLDP6vhQ901VeWqx_eANoIMjJM4fKuSnka68tqyBHJs87j",
    "count": 5,
    "max_cursor": 0,
    "output": "output/user_info.json",
}

async def fetch_user_post_videos(
    sec_user_id: str,
    max_cursor: int = 0,
    count: int = 5
) -> dict:
    """
    # [中文]
    ### 用途:
    - 获取用户主页作品数据
    ### 参数:
    - sec_user_id: 用户sec_user_id
    - max_cursor: 最大游标 (最大时间 ms时间戳)
    - count: 最大数量 —— 会保留置顶视频
    ### 返回:
    - 用户作品数据
    """
    try:
        data = await crawler.fetch_user_post_videos(sec_user_id, max_cursor, count)
        return {"code": 200, "data": data}
    except Exception as e:
        return {"code": 400, "message": str(e)}


async def run(args: argparse.Namespace) -> int:
    result = await fetch_user_post_videos(
        sec_user_id=args.sec_user_id,
        max_cursor=args.max_cursor,
        count=args.count,
    )

    if args.output == "-":
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        import os

        output_dir = os.path.dirname(args.output)

        # 如果存在目录路径，则自动创建
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        print(f"已保存到 {args.output}")

    if result.get("code") != 200:
        return 1
    return 0


def _print_startup_banner() -> None:
    print("=" * 20)
    print("抖音用户作品获取工具启动")
    print("=" * 20)
    print(f"当前任务：获取用户作品")
    print(f"用户ID：{RUN_CONFIG['sec_user_id']}")
    print(f"获取数量：{RUN_CONFIG['count']}")
    print(f"起始游标：{RUN_CONFIG['max_cursor']}")
    print(f"输出文件：{RUN_CONFIG['output']}")
    print("开始执行...\n")


async def _run_with_config() -> int:
    _print_startup_banner()
    if not RUN_CONFIG["sec_user_id"]:
        print("[ERROR] 请先在文件顶部 RUN_CONFIG 中填写 sec_user_id")
        return

    args = argparse.Namespace(
        sec_user_id=RUN_CONFIG["sec_user_id"],
        count=RUN_CONFIG["count"],
        max_cursor=RUN_CONFIG["max_cursor"],
        output=RUN_CONFIG["output"],
    )
    try:
        return await run(args)
    except Exception as e:
        print(f"[ERROR] 执行失败：{e}")
        return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fetch_douyin",
        description="获取抖音用户主页作品数据",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "sec_user_id",
        help="用户的 sec_user_id（必填）",
    )
    parser.add_argument(
        "-c", "--count",
        type=int,
        default=5,
        metavar="N",
        help="期望获取的作品数量",
    )
    parser.add_argument(
        "-m", "--max-cursor",
        type=int,
        default=0,
        dest="max_cursor",
        metavar="CURSOR",
        help="分页游标，首次请求填 0",
    )
    parser.add_argument(
        "-o", "--output",
        default="config/user_info.json",
        metavar="FILE",
        help="结果保存路径，填 - 则输出到 stdout",
    )
    return parser


def main(args=None):
    if args is None:
        if len(sys.argv) > 1:
            parser = build_parser()
            args = parser.parse_args()
            try:
                code = asyncio.run(run(args))
            except Exception as e:
                print(f"[ERROR] 执行失败：{e}")
                return 1
            return code
        return asyncio.run(_run_with_config())

    if isinstance(args, dict):
        args = argparse.Namespace(**args)

    try:
        code = asyncio.run(run(args))
    except Exception as e:
        print(f"[ERROR] 执行失败：{e}")
        return 1
    return code


if __name__ == "__main__":
    raise SystemExit(main())
