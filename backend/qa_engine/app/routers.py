import ast
import asyncio
import json
import os
import re
import time
from datetime import datetime
from pprint import pprint
import requests

from backend.qa_engine.app.questions_classify import async_client
from backend.qa_engine.app.sql_retrieval_langchain import natural_language_query_langchain



async def router_A(user_question):
    try:
        sql_result = await natural_language_query_langchain(user_question)
    except:
        sql_result = {'content':'查询错误',
                      'sql':'查询错误'}
    sql = sql_result['sql']
    # 提取 FROM 和 JOIN 后面的表名
    tables = re.findall(r'(?:FROM|JOIN)\s+([`"\[]?[a-zA-Z_][a-zA-Z0-9_]*[`"\]]?)', sql, re.IGNORECASE)
    # 去重（保持顺序）
    seen = set()
    unique_tables = [t for t in tables if not (t in seen or seen.add(t))]
    sql_text = f"""SQL查询内容：{sql_result['content']}，
    SQL查询来源: {','.join(unique_tables)}；"""
    return sql_text,sql

async def router_B(user_question):
    from backend.qa_engine.app.getcitybyip import get_city_by_ip

    location =  get_city_by_ip(requests.get('https://ifconfig.me', timeout=5).text.strip())
    sql_result,sql = await router_A(user_question)
    prompt = f"""根据检索信息分别从以下几个方面进行推荐排序：
    【排序策略】
    1. 根据价格（产品价格、预算金额等）进行排序；
    2. 根据公司的地点信息与用户的所在地，由近到远对公司进行排序；
    3. 根据风险数量进行排序；
    4. 如果检索信息没有以上方面（价格、地点、风险数量等），则不要在那方面进行排序；
    5. 如果以上方面都没有，则说明没有足够的信息不进行排序，输出默认检索信息。
    
    【检索信息】
    {sql_result}
    
    【用户所在地】
    除非用户明确说明自己所在地，否则默认{location}
    
    【输出要求】
    1. 价格排序：1. XXX公司，XX价格XXX元，产品XXX；2. XXX公司，XX价格XXX元，产品XXX；
       地点排序：1. XXX公司，所在地XXX；2. XXX公司，所在地XXX；
       风险排序：1. XXX公司，风险数量XX条；2. XXX公司，风险数量XX条；
    2. 没有的排序可不输出；如果都没有则输出没有足够的信息不进行排序。
    3. 除非用户明确要求，否则每个排序方式最多输出5条。
        
    请根据检索信息进行回答，仅输出排序结果即可：    
    """
    try:
        response = await async_client.chat.completions.create(
            model=os.getenv('CLS_MODEL'),
            messages=[
                {"role": "system", "content": "你是一个方案推荐助手，请根据已收集到的信息和用户要求作答。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.0,
            stream=True
        )
        # 流式接收
        full_content = ""

        async for chunk in response:
            if chunk.choices[0].delta.content is not None:
                content = chunk.choices[0].delta.content
                full_content += content
                # 实时显示
                # print(content, end="", flush=True)
        result = sql_result +'\n' + full_content
        return result,sql

    except Exception as e:
        return f"生成答案时出错: {str(e)}",sql

async def router_C(user_question):
    from backend.qa_engine.app.jianyubiaoxun import JianYuAPI
    now = datetime.now()
    current_date = now.strftime("%Y-%m-%d")
    prompt = """根据相应字段的描述，从用户问题中提取对应字段的关键字：
    
    【字段说明】
    start_date / end_date: 日期范围，如"2024-01-01"
    areas: 地区列表，支持中文或代码，如["北京", "上海"]
    info_types: 信息类型，如["招标", "预告", "结果"]
    industries: 行业类型，如["水利工程", "工程施工"]
    buyer_types: 采购单位类型，如["教育", "医疗"]
    amount_min / amount_max: 10000（纯数字，项目金额（元））
    search_mode: 0精准匹配  1模糊匹配
    
    【输出样例】
    提问：北京的由水利部门发布的关于水利工程的招标信息，我要今年3月3号-3月5号，金额在10万到100万的。
    输出：{{'start_date': '2026-03-03',
        'end_date': '2026-03-05',
        'areas': ["北京"],
        'info_types': ["招标"],
        'industries': ["水利工程"],
        'buyer_types': ['水利'],
        'amount_min': 100000,
        'amount_max': 1000000,
        'search_mode': 1}}
    
    【当前日期】
    今天是：{current_date}
        
    【输出要求】
    1. start_date / end_date:必须格式为'2026-03-03'的字符串，没有则为null；如果是查某一天的信息，则start_date日为当天，end_date日期比start_date加一天；
    2. areas、info_types、industries、buyer_types：必须为列表，如["北京"，"天津"]，没有则为null；
    3. amount_min、amount_max：必须为纯数字，例如10万元转换为100000,没有则为null；
    4. search_mode：除非用户明确要求精确匹配（返回纯数字0），否则默认为模糊匹配（返回纯数字1）
    
    【用户问题】
    {user_question}
    
    不要多余其他文字，请直接输出json本身：
    """.format(user_question=user_question,current_date=current_date)
    try:
        response = await async_client.chat.completions.create(
            model=os.getenv('CLS_MODEL'),
            messages=[
                {"role": "system", "content": "你是参数生成器，只按指令返回。"},
                {"role": "user", "content": prompt}
            ],
            extra_body={"enable_thinking": False},
            temperature=0.0,
        )
        content = response.choices[0].message.content
        try:

            args = json.loads(content)
            # print(args)
        except Exception as e:
            print(f'剑鱼参数解析错误：{e}, 原始内容：{content}')
            args = {}
    except Exception as e:
        args = {}
        print(f'剑鱼参数生成错误：{e}')

    if args:
        jianyu_api = JianYuAPI()
        result = jianyu_api.search(**args)
    else:
        result = {}

    print(args)
    return result

async def router_D(user_question):
    from backend.qa_engine.app.qcc_prompt_mcp import qcc_riskcheck
    company_results_dict, risk_results_dict, operation_results_dict = await qcc_riskcheck(user_question)

    prompt = f'''根据用户问题，请从以下三方面检索到的信息中挑选用户关心的信息进行总结，并生成报告。
    【企业基本信息】
    检索内容：{company_results_dict}
    
    【企业风险信息】
    检索内容：{risk_results_dict}
    
    【企业经营信息】
    检索内容：{operation_results_dict}
    
    【报告要求】
    1. 如用户对企业身份验证、股权结构、基本背景调查感兴趣，则对【企业基本信息】进行重点总结，其余两项信息简单概括即可；
    2. 如用户对法律风险（司法诉讼）、信用风险（执行与失信）、经营风险（经营异常）、债务风险（担保与抵押）、合规风险（行政处罚、其他风险）感兴趣，则对【企业风险信息】进行重点总结，每方面风险多少条信息数量要写明，其余两项信息简单概括即可；
    3. 如用户对经营能力、市场竞争力、发展潜力、舆情监控感兴趣，则对【企业经营信息】进行重点总结，其余两项信息简单概括即可；
    4. 报告要脉络清晰、结构明了，最终给出总结性结论；
    5. 检索内容为空时，则直接说明未检索到相关内容，并简单说明原因（如，公司全称不对），不需要生成报告。
    
    【用户问题】
    {user_question}
    
    请生成：
    '''
    try:
        response = await async_client.chat.completions.create(
            model=os.getenv('CLS_MODEL'),
            messages=[
                {"role": "system", "content": "你是一个企业调研专家，请根据要求作答。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            stream=True
        )
        has_content = False

        async for chunk in response:
            # 极端防御
            if chunk is None:
                continue

            choices = getattr(chunk, "choices", None)
            if not choices or not isinstance(choices, list) or len(choices) == 0:
                continue

            choice = choices[0]

            delta = getattr(choice, "delta", None)
            content = getattr(delta, "content", None)

            if content:
                has_content = True
                yield content

            finish_reason = getattr(choice, "finish_reason", None)
            if finish_reason:
                break

        if not has_content:
            yield "（模型未返回有效内容）"

    except Exception as e:
        yield f"生成答案时出错: {str(e)}"


async def router_E(user_question):
    now = datetime.now()
    current_date = now.strftime("%Y-%m-%d")
    try:
        prompt = '''根据用户问题判断是否需要联网搜索：
【用户问题】
{user_question}

【当前时间】
{current_date}

【输出要求】
1. 如果需要联网搜索，输出数字1；
2. 如果不需要联网搜索，输出数字0；

请输出纯数字，不要多余内容：
'''.format(user_question=user_question,current_date=current_date)

        response = await async_client.chat.completions.create(
            model=os.getenv('CLS_MODEL'),
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            extra_body={'enable_thinking': False},
            stream=False,
            max_tokens=1
        )
        content = response.choices[0].message.content.strip()
        arg_web = 1 if '1' in content else 0

    except Exception as e:
        print(f"路由判断失败: {e}")
        arg_web = 0  # 默认不联网，避免阻塞

    if arg_web == 1:
        try:
            from backend.qa_engine.app.web_search_async import web_search_rag
            web_results = await web_search_rag(
                query=user_question,
                num_results=5,
                top_k_per_page=2,
                min_score=0.65
            )
            # 空结果检查
            if not web_results:
                return '联网搜索未找到相关结果，请依据本身能力回答。',{'index':0,'source':'','text':'','score':0}

            choice_web_results = [{
                'index': r['chunk_index'],
                'source': r['source'],
                'text': r['content'],
                'score': r['score']
            } for r in web_results]
            from backend.qa_engine.app.vector_bm25_milvus_retrieval import reranker
            rerank_web_results = reranker(user_question, choice_web_results, score_threshold=0.7,top_k = None)
            web_texts = []
            i = 1
            for r in rerank_web_results:
                t = f"""网络查询内容{i}:{r['text']},
            网络查询来源{i}:{r['source']};\n"""
                i += 1
                web_texts.append(t)
            return '\n'.join(web_texts),rerank_web_results

        except Exception as e:
            print(f"联网搜索失败: {e}，依据模型本身能力回答，")
            response = await async_client.chat.completions.create(
                model=os.getenv('CLS_MODEL'),
                messages=[{"role": "user", "content": user_question}],
                temperature=0.0,
                extra_body={'enable_thinking': False},
                stream=False,

            )
            content = response.choices[0].message.content.strip()
            return content,[{'index':0,'source':'','text':'','score':0}]
    else:
        response = await async_client.chat.completions.create(
            model=os.getenv('CLS_MODEL'),
            messages=[{"role": "user", "content": user_question}],
            temperature=0.0,
            extra_body={'enable_thinking': False},
            stream=False,

        )
        content = response.choices[0].message.content.strip()
        return content, [{'index': 0, 'source': '', 'text': '', 'score': 0}]

async def router_F(user_question):
    from backend.qa_engine.app.vector_bm25_milvus_retrieval import hyde_retrieval, reranker
    try:
        vector_results = await hyde_retrieval(user_question,
                                              collection_name="laws_m3",  # 使用之前创建的 collection
                                              bm25_dir=os.getenv("BM25_DIR"),
                                              bm25_top_k=20,
                                              index_paths=ast.literal_eval(os.getenv("INDEX_PATH")))
    except Exception as e:
        print(f"向量检索异常: {e}")
        vector_results = [{'index':0,'source':'','text':'','score':0}]

    if vector_results:
        vector_results = reranker(user_question, vector_results,score_threshold=0.7,top_k=8)
    else:
        vector_results = [{'index':0,'source':'','text':'','score':0}]

    vector_texts = []
    i = 1
    for r in vector_results:
        t = f"""向量库查询内容{i}:{r['text']},
向量库查询来源{i}:{r['source']};\n"""
        i += 1
        vector_texts.append(t)

    return '\n'.join(vector_texts),vector_results


if __name__ == '__main__':

    user_question = '上海洛景企业管理有限公司有经营风险吗？'
    # user_question = '北京远洋控股集团有限公司怎么样？'
    # user_question = '勇芝控股有限公司情况怎么样？'
    # user_question = '上海翼水忻河体育管理有限公司有风险吗，经营情况如何？'
    # results = asyncio.run(router_D(user_question))
    # print(results)

    # user_question = '上海关于智能系统的招标有哪些？我要这个月发布的招标信息。金额在10万到100万之间。'
    # result = asyncio.run(router_C(user_question))
    # pprint(result)
    # user_question = '招标的流程有哪些？'
    # result = asyncio.run(router_C(user_question))
    # pprint(result)
    start = time.time()
    async def main():
        async for r in router_D(user_question):
            print(r, end='', flush=True)

    asyncio.run(main())
    end = time.time()
    print(end-start)

