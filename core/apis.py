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
# - 修改了config.yaml的路径配置
# ==============================================================================
# API请求结构
import httpx
import os
import yaml
import json
from core.common.logger import logger
from core.common.utils import gen_random_str, get_timestamp


class APIError(Exception):
    """基本API异常类，其他API异常都会继承这个类"""
    def __init__(self, status_code=None):
        self.status_code = status_code
        print(
            "程序出现异常，请检查错误信息。"
        )
    def display_error(self):
        """显示错误信息和状态码（如果有的话）"""
        return f"Error: {self.args[0]}." + (
            f" Status Code: {self.status_code}." if self.status_code else ""
        )

class APIResponseError(APIError):
    """当API返回的响应与预期不符时抛出"""
    def display_error(self):
        return f"API Response Error: {self.args[0]}."

# 读取配置文件
path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

with open(os.path.join(path, "config.yaml"), "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)

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
        transport = httpx.HTTPTransport(retries=5)
        with httpx.Client(transport=transport, proxy=cls.proxies.get("https://")) as client:
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
                logger.error("请求Douyin msToken API时发生错误：{0}".format(e))
                logger.info("将使用本地生成的虚假msToken参数，以继续请求。")
                return cls.gen_false_msToken()
    @classmethod
    def gen_false_msToken(cls) -> str:
        """生成随机msToken (Generate random msToken)"""
        return gen_random_str(126) + "=="

