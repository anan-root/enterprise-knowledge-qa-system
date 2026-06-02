import json
import os
import asyncio
import time
from pprint import pprint

from openai import AsyncOpenAI
# 加载环境变量（确保 .env 中有 API_KEY）
from dotenv import load_dotenv
from backend.qa_engine.app.prompt_templates import prompt_questions_cls_cot_json, example_json

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
questioncategory=[
    "A",  # 信息检索（公司/产品信息/供应商信息等结构化信息）
    "B",  # 信息推荐（产品推荐、供应商推荐）
    "C",  # 招标信息实时查询（查看招投标信息）
    "D",  # 标书判断（资质、价格、风险舆情等）
    "E",  # 其他
    "F"   # 法律法规检索（法律法规、规章制度等非结构化信息）
]

# 初始化LLM客户端
async_client = AsyncOpenAI(
    api_key=os.getenv("API_KEY"),
    base_url=os.getenv("BASE_URL")  # 支持本地部署的LLM
)


class FormatError(Exception):
    pass
async def classify_question_cot(user_question: str,max_retries=1) -> list:
    prompt = prompt_questions_cls_cot_json.format(user_question=user_question,example_json=example_json)

    for attempt in range(max_retries + 1):
        try:
            response = await async_client.chat.completions.create(
                model=os.getenv('CLS_MODEL'),
                messages=[
                    {"role": "system", "content": "你是一个精准的招投标问题分类器，只输出 JSON。"},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                extra_body={"enable_thinking": False},
                temperature=0.0,  # 严格分类，低随机性

            )
            content = response.choices[0].message.content
            data = json.loads(content)

            if not isinstance(data, list):
                raise FormatError("返回不是 list")

            result = []
            for item in data:
                if (
                        isinstance(item, dict)
                        and "question" in item
                        and "category" in item
                ):
                    cat = item["category"].upper()
                    cat = cat if cat in questioncategory else "E"
                    result.append([item["question"], cat])
                else:
                    raise FormatError("子项格式错误")

            return result or [[user_question, "E"]]

        except Exception as e:
            if attempt < max_retries:
                print(f"分类格式错误，重试中: {e}")
                continue
            else:
                print(f"分类失败（已重试）: {e}")
                return [[user_question, "E"]]


semaphore = asyncio.Semaphore(5)
async def async_classify_question_cot(user_question: str):
    async with semaphore:
        try:
            return await classify_question_cot(user_question)
        except Exception:
            return await classify_question_cot(user_question)

if __name__ == '__main__':
    async def main_cot(test_questions):
        return await asyncio.gather(*[async_classify_question_cot(q) for q in test_questions])

    test_questions = [
        # ["在判定国有资金项目时，‘占控股或者主导地位’的出资额或股份比例标准是什么？"],
        # ['为什么说招标投标具有竞争充分的特点?'],
        # ['对于通过正常渠道进口但在境内多次流转无法提供报关单证的产品,应如何查证?'],
        # ['什么是贫困地区农副产品?'],
        # ['铁路工程建设项目投标人在投标文件中填报的信息应当与什么平台一致?'],
        # ['<国有土地使用权出让预申请书示范文本>中,申请人需要承诺什么内容?'],
        # ['失信被执行人信息查询内容包括哪些?'],
        # ['查询失信被执行人信息的渠道有哪些?'],
        # ['失信被执行人信息由谁推送?'], ['失信被执行人信息推送到哪里?'],
        # ['招标人或代理机构在评标阶段如何查询投标人是否为失信被执行人?'],
        # ['交通运输基础设施项目包括哪些类型?'],
        # ['通信基础设施项目具体指什么?'],
        # ['招标代理机构自愿报送基本信息的平台是什么?'],
        # ['水利基础设施项目包括哪些?'],
        # ['工程建设项目具体指哪些内容?'],
        # ['项目监理评标标准包括哪五个方面?'],
        # ['铁路建设工程评标专家库按招标项目类别分为哪两个子库?'],
        # ['加强中小型水利工程建设管理,防范廉政风险的重要意义是什么?'],
        # ['定标主体是谁？'],
        # ['如何查询招标投标违法行为记录公告？'],
        # ['在民生保障领域,政府购买服务重点购买哪些项目?'],
        # ['在社会治理领域，政府购买服务的重点项目有哪些?'],
        # ['在行业管理领域,政府购买服务重点购买哪些项目?'],
        # ['中央预算单位批量集中采购的范围包括哪些品目?'],
        # ['台式计算机批量集中采购通常包括哪些设备?'], ['台式计算机批量集中采购不包括哪些特殊设备?'],
        # ['便携式计算机批量集中采购通常包括哪些设备?'], ['便携式计算机批量集中采购不包括哪些特殊设备?'],
        # ['中央预算单位批量集中采购品目配置参考在哪里更新?'],
        # ['空调机批量集中采购通常包括哪些设备?'], ['空调机批量集中采购不包括哪些特殊设备?'],
        # ['打印机批量集中采购通常包括哪些设备?'], ['打印机批量集中采购不包括哪些设备?'],
        # ['招标投标如何促进技术进步和管理提升?'],
        # ['招标投标在提供市场信息方面有何作用?'],
        # ['为什么说邀请招标的竞争程度不如公开招标?'],
        # ['邀请招标在交易成功率方面的优势是什么?'],
        # ['国际招标的评标机构是什么?'], ['国内招标的评标机构是什么?'],
        # ['国际招标与国内招标的评标机构有何不同?'],
        # ['国际招标的评标规则是什么?'], ['国内招标的评标规则是什么?'],
        # ['国际招标与国内招标的评标规则有何不同?'],
        # ['电子招标投标系统的三大平台分别是什么?'], ['三大平台之间的关系是什么?'],
        # ['行政监督平台的服务对象是谁?'],
        # ['电子招标投标与纸质招标的异同点有哪些?'],
        # ['什么是工程建设项目?'],
        # ['行政监督平台由谁建立?'],
        # ['什么是招标投标中的决策风险?'],
        # ['自然及环境风险包括哪些因素?'],
        # ['运营管理风险如何影响招标的具体方面有哪些?'],
        # ['市场风险对招标有何影响?'],
        # ['什么是"议标"?', 'F'],
        # ['招标文件中关于计算评标总价的规定是什么?'],
        # ['对于关境外产品,评标总价包含哪些费用?'],
        # ['招标文件中关于评标总价的计算方法是如何规定的?'], ['对于关境内制造的产品,评标总价包含哪些费用?'],
        # ['投标人作出是否投标决策时通常考虑的因素有哪些?'],
        # ['对于货物招标项目,哪些产品需要实行生产许可证管理?'],
        # ['对于科技,信息化或管理咨询项目采用招标方式的风险有哪些?'],
        # ['对于货物招标项目,哪些产品需要实行生产许可证管理?'],
        # ['投标文件中报价漏项将导致什么法律后果?'],
        # ['在购买三柱式隔离开关的案例中,投标单位投成了双柱式,评标委员会未发现此错误可能导致的后果是什么?'],
        # ['在货物招标中,非价格标准主要有哪几项?'],
        # ['在工程项目招标评标时,非价格标准主要有哪几项?'],
        # ['在服务招标评标时,非价格标准主要有哪几项?'],
        # ['恒大集团的全称是什么，如果本地没有就网上查一下'],
        # ['高强度C22圆棒的直径是多少？'],
        # ['消毒供应一体化服务项目的特定资格要求中，是否专门面向中小企业？'],
        # ['EUVL流体光源实验系统项目的特定资格要求中，是否允许采购进口产品？'],
        # ['电子支气管镜系统项目是否接受进口产品投标？'],
        # ['茂名市古音遗艺文化有限公司的经营范围包含非物质文化遗产保护吗？'],
        # ['什么是年度投标保证金？'],
        # ['什么是政务信息系统政府采购？ '],
        # ['什么是电子招标投标？ '],
        # ['什么是低于成本报价竞标？如何处理？ '],
        # ['什么是“以他人名义投标”？'],
        # ['批发龙门锁阻车器加厚地锁龙门挡车器U型汽车挡车锁防撞护栏厂家的品牌是什么？'],
        # ['广东星巴克咖啡有限公司茂名化州万达广场分店的成立日期?'],
        # ['茂名市达丰水产养殖有限公司的许可经营项目有哪些？'],
        # ['2024年青浦区卫健委医疗设备采购项目三（2）的采购预算是多少？'],
        # ['嘉定卫生信息服务采购项目的项目编号是什么？'],
        # ['有多少生产混凝土的供应商，给我按距离排序推荐5个公司'],
        # ['有多少生产混凝土的供应商，公司都叫什么?'],
        # ['23年以后关于上海的医疗设备的招标项目中，金额最高是哪个?'],
        # ['2026年1月份北京的水利招标项目有哪些？'],
        # ['2026年1月份北京的水利招标的最新项目有哪些？'],
        # ['建筑产业链中的生产和采购企业有哪些?'],
        ['帮我查一下 A 公司有没有失信记录，再顺便看看《招标投标法》里对失信的规定，顺便推荐几家靠谱的施工单位。']
        # ['在线询价有规定最少几家单位报价？安徽混凝土供应商都有哪些？如果供应商不按时供货，有什么方法制约他？'],
        # ['询价文件里边标注响应文件必须含有“某某时间不能起封”，但是没有写“不这个样子就要终止采购”；有写“必须严格按照要求递交，未按照要求，代理商有权拒绝和退回，重新填了之后再次递交”，但是，询价现场有的供应商并没有按照这个样子做，采购代理机构也未叫供应商检查，只叫监督检查密封性，然后询价就结束了。这种是否可以质疑或者是现场发出疑问？'],
        # ['老供应商每次报价都略高于新供应商，但沟通后又同意适当降低，应如何处理对这种情况?'],
        # # ['这份投标标书的报价是否合理，投标公司有没有风险？'],
        # ['有些货物采购项目涉及多种货物和多个制造商，投标人从批发商或者经销商处拿货，而非从制造商处直接拿货，难以获知所有制造商的从业人员、营业收入、资产总额等数据。如果制造商提供给投标人的数据有误或者故意提供虚假的数据，是否认定投标人虚假投标（投标人没有主观故意）？'],
        # ['某项目采用综合评分法进行评标，招标文件规定,AAA重服务守信用单位、AAA重质量守信用单位、AAA诚信经营示范单位、AAA重合同守信用单位,每一项AAA证书获得一项得2分,满分8分。这样的设置可以吗?'],
    ]
    start = time.time()
    results = asyncio.run(main_cot(test_questions))
    end = time.time()
    print(f'time:', end - start)
    pprint(results)
