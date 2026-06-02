import asyncio
import os
# 加载环境变量（确保 .env 中有 API_KEY）
from dotenv import load_dotenv
from backend.qa_engine.app.routers import router_A, router_F, router_B, router_D, router_C, router_E
env_path = os.path.join(os.path.dirname(__file__), 'app', ".env")
load_dotenv(env_path)
import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
from backend.qa_engine.app.questions_classify import async_classify_question_cot as classify, async_client
from backend.qa_engine.app.prompt_templates import DEFAULT_ANSWER_PROMPT

#信息检索收集
async def retrieval(q_and_c):

    if q_and_c[1] == 'A':
        question = q_and_c[0]
        router_result, sql = await router_A(question)
        router_result = 'router_A检索内容：'+ router_result
        return question, router_result,sql

    elif q_and_c[1] == 'B':
        question = q_and_c[0]
        router_result, sql = await router_B(question)
        router_result = 'router_B检索内容：'+ router_result
        return question, router_result, sql

    elif q_and_c[1] == 'C':
        question = q_and_c[0]
        router_result = 'router_C检索内容：'+ str(await router_C(question))
        return question, router_result, ''

    elif q_and_c[1] == 'D':
        question = q_and_c[0]
        report = ''
        try:
            async for r in router_D(question):
                report += r
        except Exception as e:
            report += f"系统错误：{str(e)}"

        router_result = 'router_D检索内容：'+ report
        return question, router_result, ''

    elif q_and_c[1] == 'F':
        question = q_and_c[0]
        router_result,vector_results = await router_F(question)
        router_result = 'router_F检索内容：'+ router_result
        return question, router_result, vector_results
    else:
        question = q_and_c[0]
        router_result,web_results = await router_E(question)
        router_result = 'router_E检索内容：'+ router_result
        return question, router_result, web_results

#答案生成
async def change_question(prompt):
    response = await async_client.chat.completions.create(
        model=os.getenv('CLS_MODEL'),
        messages=[
            {"role": "system", "content": "你是问题改写助手，请根据已收集到的信息和用户问题作答。"},
            {"role": "user", "content": prompt}
        ],
        temperature=0.0,
        extra_body={"enable_thinking": False},
        stream=False
    )
    question = response.choices[0].message.content
    return question

async def response(retrieval_results:str,user_question:str,prompt:str,stream_print=False):
    prompt = prompt.format(
        retrieval_results=retrieval_results,
        user_question=user_question
    )
    try:
        response = await async_client.chat.completions.create(
            model=os.getenv('LLM_MODEL'),
            messages=[
                {"role": "system", "content": "你是一个企业知识库问答助手，请根据已收集到的信息和用户问题作答。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.0,
            stream=True
        )
        # 流式接收
        full_content = ""

        async for chunk in response:
            if (
                    chunk.choices
                    and chunk.choices[0].delta
                    and chunk.choices[0].delta.content is not None
            ):
                content = chunk.choices[0].delta.content
                full_content += content
                if stream_print:
                    print(content, end="", flush=True)

        # print()  # 换行
        return full_content

    except Exception as e:
        return f"生成答案时出错: {str(e)}"

def create_dict():
    return {
        "原问题":'',
        "问题拆分":[],
        "子问题":[],
        "已检索的子问题及其检索信息":'',
        "生成答案":''
    }
def create_subdict():
    return {
        "子问题": "",
        "分类": "",
        "sql语句": "",
        "sql内容": "",
        "vector_chunks": [],
        "web_chunks": [],
        "jy_qcc": ''
    }

async def main(user_question: str, prompt_template: str='',print_retrieval_results=False,stream_print=False,if_evaluate = False):
    if if_evaluate:
        main_dict = create_dict()

    # 1. 分类
    cls_results = await classify(user_question)
    print(cls_results)

    # 2. 检索
    retrieval_results = ''
    for i,q in enumerate(cls_results):
        if i == 0:
            cls = q[1]
            if cls =='F':
                question, router_result,vector_results = await retrieval(q)
                sql = ''
            elif cls == 'E':
                question, router_result, web_results = await retrieval(q)
                sql = ''
            else:
                question, router_result,sql = await retrieval(q)

            retrieval_results += f'子问题{i+1}：{question}，检索结果：{router_result}；\n'

            if if_evaluate:
                sub_dict = create_subdict()
                sub_dict['子问题'] = q[0]
                sub_dict['分类'] = q[1]
                sub_dict['sql语句'] = sql
                if q[1] == 'A' or q[1] == 'B':
                    sub_dict['sql内容'] = router_result
                elif q[1] == 'C' or q[1] == 'D':
                    sub_dict['jy_qcc'] = router_result
                elif q[1] == 'E':
                    sub_dict['web_chunks'] = web_results
                else:
                    sub_dict['vector_chunks'] = vector_results
                main_dict['子问题'].append(sub_dict)

        else:
            prompt_change_question = _build_change_question_prompt(user_question, cls_results, retrieval_results, q[0], i)
            #生成改写后的问题
            changed_question = await change_question(prompt_change_question)
            print(changed_question)
            cls = q[1]
            change_question_cls = [changed_question,cls]
            #用改写后的问题及分类检索
            if cls =='F':
                question, router_result,vector_results = await retrieval(change_question_cls)
                sql = ''
            elif cls == 'E':
                question, router_result, web_results = await retrieval(change_question_cls)
                sql = ''
            else:
                question, router_result,sql = await retrieval(change_question_cls)
            retrieval_results += f'子问题{i + 1}：{question}，检索结果：{router_result}；\n'

            if if_evaluate:
                sub_dict = create_subdict()
                sub_dict['子问题'] = q[0]
                sub_dict['分类'] = q[1]
                sub_dict['sql语句'] = sql
                if q[1] == 'A' or q[1] == 'B':
                    sub_dict['sql内容'] = router_result
                elif q[1] == 'C' or q[1] == 'D':
                    sub_dict['jy_qcc'] = router_result
                elif q[1] == 'E':
                    sub_dict['web_chunks'] = web_results
                else:
                    sub_dict['vector_chunks'] = vector_results
                main_dict['子问题'].append(sub_dict)

    if print_retrieval_results:
        print(retrieval_results)

    # 3. 生成回答
    if not prompt_template:
        prompt_template = DEFAULT_ANSWER_PROMPT

    response_result = await response(retrieval_results, user_question, prompt_template,stream_print=stream_print)

    if if_evaluate:
        main_dict['原问题'] = user_question
        main_dict['问题拆分'] = cls_results
        main_dict['已检索的子问题及其检索信息'] = retrieval_results
        main_dict['生成答案'] = response_result

        return main_dict

    return response_result




async def response_stream(retrieval_results:str,user_question:str,prompt:str):
    prompt = prompt.format(
        retrieval_results=retrieval_results,
        user_question=user_question
    )
    try:
        response = await async_client.chat.completions.create(
            model=os.getenv('LLM_MODEL'),
            messages=[
                {"role": "system", "content": "你是一个企业知识库问答助手，请根据已收集到的信息和用户问题作答。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.0,
            extra_body={"enable_thinking": False},
            stream=True
        )

        has_content = False

        async for chunk in response:
            # 极端防御：chunk 本身异常
            if chunk is None:
                continue

            choices = getattr(chunk, "choices", None)
            if not choices or not isinstance(choices, list):
                continue

            if len(choices) == 0:
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

        # 兜底：防止空流
        if not has_content:
            yield "（模型未返回有效内容）"

    except Exception as e:
        yield f"生成答案时出错：{str(e)}"


def _build_change_question_prompt(user_question, cls_results, retrieval_results, current_q, i):
    return f"""为解决用户原始问题已将其按解决问题步骤拆分为一个或多个子问题，因为每个子问题有可能依赖于前面问题的答案，所以需要根据已检索到的信息改写当前子问题，让当前子问题更明晰明确方便后续检索。
根据以下子问题及检索信息，改写当前子问题。
【改写要求】
1. 根据已检索到的信息，将当前子问题里的代词替换为明确的信息，以便后续检索信息；
2. 如果对已检索信息中提到了某个实体的完整名称（如公司全称），在改写时必须使用该完整名称；
3. 如果判断前面检索的信息与当前子问题无关，则不改变当前子问题。
4. 改写后的子问题尽量凝练，但明确。

【用户原始问题及拆分的所有子问题】
原始问题：{user_question}
拆分所有子问题：{cls_results}

【已检索的子问题及其检索信息】
已检索信息：{retrieval_results}

【当前子问题{i+1}】
{current_q}

【示例】
用户原始问题及拆分的所有子问题：原始问题：招商蛇口房地产公司的全称是什么，有没有风险？
                          拆分所有子问题：['招商蛇口房地产公司的全称是什么？','E'],['招商蛇口房地产公司是否存在经营风险或法律处罚记录？','D']
已检索信息：子问题1：招商蛇口房地产公司的全称是什么？检索结果1：招商蛇口房地产公司的全称是招商局蛇口工业区控股股份有限公司‌。
当前子问题2:招商蛇口房地产公司是否存在经营风险或法律处罚记录？
改写后的问题：招商局蛇口工业区控股股份有限公司‌是否存在经营风险或法律处罚记录？

仅改写当前子问题，请直接输出改写后的问题本身：
"""

semaphore = asyncio.Semaphore(int(os.getenv('MAX_CONCURRENT',5)))

async def run_with_semaphore(coro):
    async with semaphore:
        return await coro

async def run_with_semaphore_yield(coro):
    async with semaphore:
        async for item in coro:
            yield item

async def main_stream(user_question: str, prompt_template: str=''):
    try:
        # 1. 分类
        cls_results = await run_with_semaphore(classify(user_question))
        print(cls_results)
        # 2. 检索
        if len(cls_results) ==1 and cls_results[0][1]=='D':
            try:
                async for r in router_D(user_question):
                    yield r
                return
            except Exception as e:
                yield f"系统错误D：{str(e)}"
                return

        retrieval_results = ''
        for i, q in enumerate(cls_results):
            if i == 0:
                cls = q[1]

                if cls == 'A':
                    question, router_result, sql = await run_with_semaphore(retrieval(q))

                    if sql == '未生成有效的SQL':
                        prompt_similar_quesiton = f"""请将下面的问题重写为一个意思相同的问题：
                        【改写要求】
                        重写的问题要与原问题意思相同或非常相近，不能改变原问题的含义。
                        
                        【原问题】
                        {question}
                        
                        请直接输出改写后的问题本身，不要多余文字：
                        """
                        similar_question = await run_with_semaphore(change_question(prompt_similar_quesiton))

                        q = await run_with_semaphore(classify(similar_question))
                        question, router_result, _ = await run_with_semaphore(retrieval(q))
                else:
                    question, router_result, _ = await run_with_semaphore(retrieval(q))

                retrieval_results += f'子问题{i + 1}：{question}，检索结果{i + 1}：{router_result}；\n'

            else:

                prompt_change_question = _build_change_question_prompt(user_question, cls_results, retrieval_results, q[0], i)
                # 生成改写后的问题
                changed_question = await run_with_semaphore(change_question(prompt_change_question))
                print('改写后问题：',changed_question)
                cls = q[1]
                change_question_cls = [changed_question, cls]
                # 用改写后的问题及分类检索
                if cls == 'F':
                    question, router_result, vector_results = await run_with_semaphore(retrieval(change_question_cls))

                elif cls == 'E':
                    question, router_result, web_results = await run_with_semaphore(retrieval(change_question_cls))

                else:
                    question, router_result, sql = await run_with_semaphore(retrieval(change_question_cls))
                retrieval_results += f'子问题{i + 1}：{question}，检索结果{i + 1}：{router_result}；\n'
        # print(retrieval_results)

        # 3. 生成回答
        if not prompt_template:
            prompt_template = DEFAULT_ANSWER_PROMPT

        async for chunk in run_with_semaphore_yield(response_stream(retrieval_results, user_question, prompt_template)):
            yield chunk

    except Exception as e:
        yield f"系统错误：{str(e)}"

if __name__ == '__main__':
    user_question = input('请输入问题：')
    # prompt = ''
    # response_result = asyncio.run(main(user_question,prompt,print_retrieval_results=False,stream_print=True))



    async def run():
        async for chunk in main_stream(user_question):
            print(chunk, end="", flush=True)

    asyncio.run(run())
    # import sys
    #
    # print(sys.path)


