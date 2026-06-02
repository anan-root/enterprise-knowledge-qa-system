import os
from pprint import pprint

import requests
import time
import hashlib
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv

# 加载环境变量
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

# ========== 代码表配置（根据你的图片整理）==========
with open(os.path.join(os.path.dirname(__file__),'jianyu_getmcp', "jianyu_code.json"),'r',encoding='utf-8') as f:
    jianyu_code = json.load(f)

# 地区代码表
AREA_CODES = jianyu_code['area']

# 信息行业代码表
INDUSTRY_CODES = jianyu_code['industry']

# 信息类型代码表
INFO_TYPE_CODES = jianyu_code['info_type']

# 采购单位类型代码表
BUYER_TYPE_CODES = jianyu_code['buyer_type']

# 拟在建项目阶段代码表
PROJECT_STAGE_CODES = jianyu_code['project_stage']

# 拟在建业主类型代码表
OWNER_TYPE_CODES = jianyu_code['owner_type']




class JianYuAPI:
    """剑鱼标讯 API 封装类"""

    def __init__(self):
        self.appid = os.getenv('JY_AppID')
        self.secretkey = os.getenv('JY_SecretKey')
        self.base_url = "https://api.jianyu360.com/thirdpartyapi/standard/bid/search"
        self.encode = 'utf-8'

        if not self.appid or not self.secretkey:
            raise ValueError("请在 .env 文件中配置 JY_AppID 和 JY_SecretKey")

    def _generate_sign(self, timestamp: str) -> str:
        """生成 MD5 签名"""
        sign_str = self.appid + timestamp + self.secretkey
        hl = hashlib.md5()
        hl.update(sign_str.encode(encoding=self.encode))
        return hl.hexdigest().upper()

    def _date_to_timestamp(self, date_str: str) -> int:
        """将日期字符串转为10位时间戳"""
        return int(time.mktime(time.strptime(date_str, "%Y-%m-%d")))

    def search(
            self,
            # 时间范围（支持日期字符串或时间戳）
            start_date: str = None,  # 格式：2024-01-01
            end_date: str = None,  # 格式：2024-12-31
            start_time: int = None,  # 10位时间戳
            end_time: int = None,  # 10位时间戳

            # 关键词
            keywords: list = None,  # 如：["污水处理", "环保"]
            keyword_range: list = None,  # 范围：标题、正文、附件、项目名称/标的物、采购单位、中标企业

            # 排除词
            exclude_words: list = None,
            exclude_word_range: list = None,

            # 搜索模式
            search_mode: int = 1,  # 0:精准模式  1:模糊模式

            # 地区（支持中文名称或代码）
            areas: list = None,  # 如：["北京", "天津"] 或 ["110000", "120000"]

            # 信息类型（支持中文名称或代码）
            info_types: list = None,  # 如：["招标", "预告"] 或 ["02", "01"]

            # 行业（支持中文名称或代码）
            industries: list = None,  # 如：["建筑工程", "工程施工"] 或 ["0201", "0203"]

            # 采购单位类型（支持中文名称或代码）
            buyer_types: list = None,  # 如：["教育", "医疗"] 或 ["01", "04"]

            # 项目金额范围（单位：元）
            amount_min: int = None,
            amount_max: int = None,

            # 分页
            # page: int = None,

            # 调试模式
            debug: bool = False
    ) -> dict:
        """
        查询招标信息

        参数说明：
            start_date/end_date: 日期范围，如 "2024-01-01"
            keywords: 关键词列表，如 ["污水处理", "环保工程"]
            keyword_range: 搜索范围，如 ["标题", "正文"]
            areas: 地区列表，支持中文或代码，如 ["北京", "上海"]
            info_types: 信息类型，如 ["招标", "预告", "结果"]
            industries: 行业类型，如 ["建筑工程", "工程施工"]
            buyer_types: 采购单位类型，如 ["教育", "医疗"]
            amount_min/amount_max: 项目金额（元）
            search_mode: 0精准 1模糊
            page: 页码
        """

        # 生成签名
        timestamp = str(int(time.time()))
        sign = self._generate_sign(timestamp)

        headers = {
            'Content-Type': 'application/json;charset=utf-8',
            'timestamp': timestamp,
            'sign': sign
        }

        payload = {}
        # if page:
        #     payload["page"] = page

        # 处理时间范围
        if start_date:
            payload["releaseTimeStart"] = self._date_to_timestamp(start_date)
        elif start_time:
            payload["releaseTimeStart"] = start_time

        if end_date:
            payload["releaseTimeEnd"] = self._date_to_timestamp(end_date)
        elif end_time:
            payload["releaseTimeEnd"] = end_time

        # 处理关键词
        if keywords:
            payload["keyWord"] = keywords
        if keyword_range:
            payload["keyWordRange"] = keyword_range

        # 处理排除词
        if exclude_words:
            payload["excludeWord"] = exclude_words
        if exclude_word_range:
            payload["excludeWordRange"] = exclude_word_range

        payload["searchMode"] = search_mode

        # 处理地区（中文转代码）
        if areas:
            payload["area"] = self._convert_codes(areas, AREA_CODES, "地区")

        # 处理信息类型（中文转代码）
        if info_types:
            payload["informationType"] = self._convert_codes(info_types, INFO_TYPE_CODES, "信息类型")

        # 处理行业（中文转代码）
        if industries:
            payload["industry"] = self._convert_codes(industries, INDUSTRY_CODES, "行业")

        # 处理采购单位类型（中文转代码）
        if buyer_types:
            payload["buyerType"] = self._convert_codes(buyer_types, BUYER_TYPE_CODES, "采购单位类型")

        # 处理金额范围
        if amount_min is not None:
            payload["projectAmountStart"] = amount_min
        if amount_max is not None:
            payload["projectAmountEnd"] = amount_max

        if debug:
            print("请求参数:", json.dumps(payload, ensure_ascii=False, indent=2))

        # 发送请求
        url = f"{self.base_url}?appid={self.appid}"

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            result = response.json()

            if result.get("error_code") != 0:
                print(f"API错误: {result.get('error_msg')} (code: {result.get('error_code')})")
                return result

            # 格式化输出
            return self._format_result(result)

        except requests.exceptions.RequestException as e:
            print(f"请求异常: {e}")
            return {"error_code": -1, "error_msg": str(e)}

    def _convert_codes(self, items: list, code_map: dict, item_name: str) -> list:
        """将中文名称转换为代码"""
        result = []
        for item in items:
            if item in code_map:
                result.append(code_map[item])
            elif item in code_map.values():
                result.append(item)  # 已经是代码
            else:
                print(f"警告: 未知的{item_name} '{item}'，可用选项: {list(code_map.keys())}...")
        return result if result else items

    def _format_result(self, result: dict, current_page: int = 1) -> dict:
        """
        格式化返回结果 - 转换为中文字典形式，便于阅读和理解
        去掉代码和项目ID等冗余字段
        """
        if result.get("error_code") != 0:
            return {
                "错误码": result.get("error_code", -1),
                "错误信息": result.get("error_msg", "未知错误"),
                "数据": None
            }

        data = result.get("data", {})
        items = data.get("list", [])
        formatted_items = []

        for item in items:
            # 转换时间戳为日期字符串
            publishtime = item.get("publishtime", 0)
            if publishtime:
                import time
                date_str = time.strftime("%Y-%m-%d %H:%M", time.localtime(publishtime))
            else:
                date_str = ""

            formatted_item = {
                "标题": item.get("title"),
                "信息类型": item.get("toptype"),
                "子类型": item.get("subtype"),
                "地区": {
                    "省份": item.get("area"),
                    "城市": item.get("city"),
                    "区县": item.get("district")
                },
                "发布时间": date_str,
                "采购单位": {
                    "名称": item.get("buyer"),
                    "类型": item.get("buyerclass")
                },
                "代理机构": item.get("agency"),
                "行业分类": item.get("s_subscopeclass", [])
            }
            formatted_items.append(formatted_item)

        return {
            "返回条数": f'{len(formatted_items)}条。',
            "数据列表": formatted_items,
            # "原始数据": result
        }


# ========== 使用示例 ==========

if __name__ == "__main__":

    # 初始化API
    api = JianYuAPI()

    """参数说明：
    start_date / end_date: 日期范围，如
    "2024-01-01"
    keywords: 关键词列表，如["污水处理", "环保工程"]
    keyword_range: 搜索范围，如["标题", "正文"]
    areas: 地区列表，支持中文或代码，如["北京", "上海"]
    info_types: 信息类型，如["招标", "预告", "结果"]
    industries: 行业类型，如["水利工程", "工程施工"]
    buyer_types: 采购单位类型，如["教育", "医疗"]
    amount_min / amount_max: 10000（纯数字，项目金额（元））
    search_mode: 0精准  1模糊
    """
    args = {'start_date':'2026-03-03',
    'end_date':'2026-03-04',
    'areas':["北京"],
    'info_types':["招标"],
    'industries' : ["水利工程"],
    'buyer_types' : ['水利'],
    'amount_min' : None,
    'amount_max' : None,
    'search_mode':1}

    result = api.search(**args)

    pprint(result)