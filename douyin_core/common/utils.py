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
# - 重构代码结构，优化页面逻辑，移除冗余方法以提升可读性与可维护性
# - 适配 httpx 0.28+ 版本变更，移除已废弃的 proxies 参数
# - 使用 transport / mounts 机制重写代理逻辑
# - 优化config.yaml索引
# ==============================================================================
# 方法
import datetime
import random
import re
import httpx
import json
from config.settings import CONFIG
from douyin_core.common.api_exceptions import (
    APIConnectionError,
    APIResponseError
)
# 配置文件路径
config = CONFIG
def gen_random_str(randomlength: int) -> str:
    """
    根据传入长度产生随机字符串 (Generate a random string based on the given length)
    Args:
        randomlength (int): 需要生成的随机字符串的长度 (The length of the random string to be generated)
    Returns:
        str: 生成的随机字符串 (The generated random string)
    """
    base_str = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+-"
    return "".join(random.choice(base_str) for _ in range(randomlength))
def get_timestamp(unit: str = "milli"):
    """
    根据给定的单位获取当前时间 (Get the current time based on the given unit)
    Args:
        unit (str): 时间单位，可以是 "milli"、"sec"、"min" 等
            (The time unit, which can be "milli", "sec", "min", etc.)
    Returns:
        int: 根据给定单位的当前时间 (The current time based on the given unit)
    """
    now = datetime.datetime.utcnow() - datetime.datetime(1970, 1, 1)
    if unit == "milli":
        return int(now.total_seconds() * 1000)
    elif unit == "sec":
        return int(now.total_seconds())
    elif unit == "min":
        return int(now.total_seconds() / 60)
    else:
        raise ValueError("Unsupported time unit")
# Token解析
class TokenManager:
    douyin_manager = config.get("TokenManager").get("douyin")
    token_conf = douyin_manager.get("msToken", None)
    ttwid_conf = douyin_manager.get("ttwid", None)
    proxies_conf = douyin_manager.get("proxies", None)
    proxies = {
        "http://": proxies_conf.get("http", None),
        "https://": proxies_conf.get("https", None),
    }
    @classmethod
    def gen_real_msToken(cls) -> str:
        """
        生成真实的msToken,当出现错误时返回虚假的值
        (Generate a real msToken and return a false value when an error occurs)
        """
        payload = json.dumps(
            {
                "magic": cls.token_conf["magic"],
                "version": cls.token_conf["version"],
                "dataType": cls.token_conf["dataType"],
                "strData": cls.token_conf["strData"],
                "tspFromClient": get_timestamp(),
            }
        )
        headers = {
            "User-Agent": cls.token_conf["User-Agent"],
            "Content-Type": "application/json",
        }

        with httpx.Client(
                mounts={
                    "http://": httpx.HTTPTransport(proxy=cls.proxies.get("http://")),
                    "https://": httpx.HTTPTransport(proxy=cls.proxies.get("https://")),
                }
        ) as client:
            try:
                response = client.post(
                    cls.token_conf["url"], content=payload, headers=headers
                )
                response.raise_for_status()

                msToken = str(httpx.Cookies(response.cookies).get("msToken"))
                if len(msToken) not in [120, 128]:
                    raise APIResponseError("响应内容：{0}， Douyin msToken API 的响应内容不符合要求。".format(msToken))

                return msToken

            except Exception as e:
                # 返回虚假的msToken (Return a fake msToken)
                print("请求Douyin msToken API时发生错误：{0}".format(e))
                print("将使用本地生成的虚假msToken参数，以继续请求。")
                return cls.gen_false_msToken()

    @classmethod
    def gen_false_msToken(cls) -> str:
        """生成随机msToken (Generate random msToken)"""
        return gen_random_str(126) + "=="
# URL解析
class AwemeIdFetcher:
    # 预编译正则表达式
    _DOUYIN_VIDEO_URL_PATTERN = re.compile(r"video/([^/?]*)")
    _DOUYIN_VIDEO_URL_PATTERN_NEW = re.compile(r"[?&]vid=(\d+)")
    _DOUYIN_NOTE_URL_PATTERN = re.compile(r"note/([^/?]*)")
    _DOUYIN_DISCOVER_URL_PATTERN = re.compile(r"modal_id=([0-9]+)")

    @classmethod
    async def get_aweme_id(cls, url: str) -> str:
        """
        从单个url中获取aweme_id (Get aweme_id from a single url)
        Args:
            url (str): 输入的url (Input url)
        Returns:
            str: 匹配到的aweme_id (Matched aweme_id)
        """
        if not isinstance(url, str):
            raise TypeError("参数必须是字符串类型")

        # 重定向到完整链接
        transport = httpx.AsyncHTTPTransport(retries=5)
        async with httpx.AsyncClient(
                transport=transport, proxy=None, timeout=10
        ) as client:
            try:
                response = await client.get(url, follow_redirects=True)
                response.raise_for_status()
                response_url = str(response.url)
                # 按顺序尝试匹配视频ID
                for pattern in [
                    cls._DOUYIN_VIDEO_URL_PATTERN,
                    cls._DOUYIN_VIDEO_URL_PATTERN_NEW,
                    cls._DOUYIN_NOTE_URL_PATTERN,
                    cls._DOUYIN_DISCOVER_URL_PATTERN
                ]:
                    match = pattern.search(response_url)
                    if match:
                        return match.group(1)
                raise APIResponseError("未在响应的地址中找到 aweme_id，检查链接是否为作品页")
            except httpx.RequestError as exc:
                raise APIConnectionError(
                    f"请求端点失败，请检查当前网络环境。链接：{url}，代理：{TokenManager.proxies}，异常类名：{cls.__name__}，异常详细信息：{exc}"
                )
            except httpx.HTTPStatusError as e:
                raise APIResponseError(
                    f"链接：{e.response.url}，状态码 {e.response.status_code}：{e.response.text}"
                )
