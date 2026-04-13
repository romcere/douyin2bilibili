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
# - 修改部分代码为静态方法
# ==============================================================================

import os  # 系统操作
import yaml  # 配置文件
from urllib.parse import urlencode
from core.models import PostDetail
from core.base_crawler import BaseCrawler
from core.ab import BogusManager
from core.common.utils import AwemeIdFetcher

# 配置文件路径
path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# 读取配置文件
with open(f"{path}/config.yaml", "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)


class DouyinWebCrawler:
    # 从配置文件中获取抖音的请求头
    @staticmethod
    async def get_douyin_headers():
        douyin_config = config["TokenManager"]["douyin"]
        kwargs = {
            "headers": {
                "Accept-Language": douyin_config["headers"]["Accept-Language"],
                "User-Agent": douyin_config["headers"]["User-Agent"],
                "Referer": douyin_config["headers"]["Referer"],
                "Cookie": douyin_config["headers"]["Cookie"],
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
