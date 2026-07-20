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
# - 删除了一些没有使用的方法
# ==============================================================================
from urllib.parse import urlencode
from douyin_core.models import PostDetail, UserPost
from douyin_core.base_crawler import BaseCrawler
from douyin_core.ab import BogusManager
from douyin_core.common.utils import AwemeIdFetcher
from config.settings import CONFIG
import sys

# 配置文件路径
config = CONFIG


def _safe_header_value(value: object, field_name: str) -> str:
    """
    将请求头值规范为 ASCII 安全字符串。

    httpx / 底层 HTTP 实现对 header 值非常敏感，若配置里混入了
    非 ASCII 字符（例如中文省略号 `…`），会在编码阶段触发
    `UnicodeEncodeError: 'ascii' codec can't encode character ...`。
    这里采用忽略策略，避免直接中断请求流程。
    """
    text = "" if value is None else str(value)
    cleaned = text.encode("ascii", errors="ignore").decode("ascii")
    if cleaned != text:
        print(
            f"[WARN] {field_name} 含有非 ASCII 字符，已自动清理",
            file=sys.stderr
        )
    return cleaned

class DouyinWebCrawler:
    # 从配置文件中获取抖音的请求头
    @staticmethod
    async def get_douyin_headers():
        douyin_config = config["TokenManager"]["douyin"]
        kwargs = {
            "headers": {
                "Accept-Language": _safe_header_value(
                    douyin_config["headers"]["Accept-Language"], "Accept-Language"
                ),
                "User-Agent": _safe_header_value(
                    douyin_config["headers"]["User-Agent"], "User-Agent"
                ),
                "Referer": _safe_header_value(
                    douyin_config["headers"]["Referer"], "Referer"
                ),
                "Cookie": _safe_header_value(
                    douyin_config["headers"]["Cookie"], "Cookie"
                ),
            },
            "proxies": {"http://": douyin_config["proxies"]["http"], "https://": douyin_config["proxies"]["https"]},
        }
        return kwargs
    # 获取单个作品数据
    @staticmethod
    async def fetch_one_video(aweme_id: str):
        # 获取抖音的实时Cookie
        kwargs = await DouyinWebCrawler.get_douyin_headers()
        # 创建一个基础爬虫
        base_crawler = BaseCrawler(proxies=kwargs["proxies"], crawler_headers=kwargs["headers"])
        async with base_crawler as crawler:
            # 创建一个作品详情的BaseModel参数
            params = PostDetail(aweme_id=aweme_id)
            # 生成一个作品详情的带有加密参数的Endpoint
            # 2024年6月12日22:41:44 由于XBogus加密已经失效，所以不再使用XBogus加密参数，转移至a_bogus加密参数。
            # endpoint = BogusManager.xb_model_2_endpoint(
            #     DouyinAPIEndpoints.POST_DETAIL, params.dict(), kwargs["headers"]["User-Agent"]
            # )

            # 生成一个作品详情的带有a_bogus加密参数的Endpoint
            params_dict = params.dict()
            params_dict["msToken"] = ''
            a_bogus = BogusManager.ab_model_2_endpoint(params_dict, kwargs["headers"]["User-Agent"])
            endpoint = f"https://www.douyin.com/aweme/v1/web/aweme/detail/?{urlencode(params_dict)}&a_bogus={a_bogus}"

            response = await crawler.fetch_get_json(endpoint)
        return response
    # 提取单个作品id
    async def get_aweme_id( url: str):
        return await AwemeIdFetcher.get_aweme_id(url)

    # 获取用户发布作品数据
    async def fetch_user_post_videos(self, sec_user_id: str, max_cursor: int, count: int):
        kwargs = await self.get_douyin_headers()
        base_crawler = BaseCrawler(proxies=kwargs["proxies"], crawler_headers=kwargs["headers"])
        async with base_crawler as crawler:
            params = UserPost(sec_user_id=sec_user_id, max_cursor=max_cursor, count=count)
            # endpoint = BogusManager.xb_model_2_endpoint(
            #     DouyinAPIEndpoints.USER_POST, params.dict(), kwargs["headers"]["User-Agent"]
            # )
            # response = await crawler.fetch_get_json(endpoint)

            # 生成一个用户发布作品数据的带有a_bogus加密参数的Endpoint
            params_dict = params.dict()
            params_dict["msToken"] = ''
            a_bogus = BogusManager.ab_model_2_endpoint(params_dict, kwargs["headers"]["User-Agent"])
            endpoint = f"https://www.douyin.com/aweme/v1/web/aweme/post/?{urlencode(params_dict)}&a_bogus={a_bogus}"
            response = await crawler.fetch_get_json(endpoint)
        return response
