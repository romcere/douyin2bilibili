# ABogus生成
from .common.abogus import ABogus as AB
from urllib.parse import quote

class BogusManager:
    # 字典方法生成A-Bogus参数，感谢 @JoeanAmier 提供的纯Python版本算法。
    @classmethod
    def ab_model_2_endpoint(cls, params: dict, user_agent: str) -> str:
        if not isinstance(params, dict):
            raise TypeError("参数必须是字典类型")

        try:
            ab_value = AB().get_value(params, )
        except Exception as e:
            raise RuntimeError("生成A-Bogus失败: {0})".format(e))

        return quote(ab_value, safe='')

