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
#
# Modifications by romcere, 2026
#
# Changes made:
# - 新增 fetch_one_video() 方法，该方法遵循 Apache 2.0 许可证
# ==============================================================================
from urllib.parse import urlencode
from core.models import PostDetail
from core.base_crawler import BaseCrawler
from core.ab import BogusManager
from core.common.cookie import get_douyin_headers
# 获取单个作品数据
async def fetch_one_video(aweme_id: str):
    # 获取抖音的实时Cookie
    kwargs = await get_douyin_headers()
    # 创建一个基础爬虫
    base_crawler = BaseCrawler(proxies=kwargs["proxies"], crawler_headers=kwargs["headers"])
    async with base_crawler as crawler:
        # 创建一个作品详情的BaseModel参数
        params = PostDetail(aweme_id=aweme_id)
        # 生成一个作品详情的带有a_bogus加密参数的Endpoint
        params_dict = params.model_dump()
        params_dict["msToken"] = ''
        a_bogus = BogusManager.ab_model_2_endpoint(params_dict, kwargs["headers"]["User-Agent"])
        endpoint = f"https://www.douyin.com/aweme/v1/web/aweme/detail/?{urlencode(params_dict)}&a_bogus={a_bogus}"

        response = await crawler.fetch_get_json(endpoint)
    return response
# # 获得响应数据
# async def main():
#     result = await fetch_one_video("7618953950175300904")  # 已经是 dict
#     # SON 字符串
#     json_str = json.dumps(result, ensure_ascii=False, indent=2)
#     print(json_str)
#
# if __name__ == "__main__":
#     asyncio.run(main())