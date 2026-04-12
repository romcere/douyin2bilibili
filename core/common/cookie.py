import yaml
import os
path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))

# 读取配置文件
with open(os.path.join(path, "config.yaml"), "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)

# 从配置文件中获取抖音的请求头
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