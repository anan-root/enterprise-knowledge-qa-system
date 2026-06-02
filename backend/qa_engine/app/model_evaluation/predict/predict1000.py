import asyncio
import json
import os
import re
import traceback
from dotenv import load_dotenv
from main import main
import pandas as pd

# data1 = pd.read_csv('q_and_a/laws_data.csv')
# data2 = pd.read_csv('q_and_a/sql_data.csv')
#
# print(data1.shape)
# print(data2.shape)


async def predict(questions: list, nums: int = None):
    if nums:
        questions = questions[:nums]

    semaphore = asyncio.Semaphore(3)

    async def process_one(user_question):
        async with semaphore:
            for attempt in range(3):  # 超时重试3次
                try:
                    result = await asyncio.wait_for(
                        main(
                            user_question,
                            prompt_template='',
                            print_retrieval_results=False,
                            stream_print=False,
                            if_evaluate=True
                        ),
                        timeout=180
                    )
                    return result
                except asyncio.TimeoutError:
                    print(f"问题超时，第{attempt+1}次重试: {user_question[:30]}...")
                    await asyncio.sleep(2 ** attempt)
                except Exception as e:
                    traceback.print_exc()
                    raise
            return {"生成答案": "错误: 请求超时，多次重试后失败"}

    tasks = [process_one(q) for q in questions]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # 处理异常：将异常对象替换为包含错误信息的字典
    processed_results = []
    for i, r in enumerate(results):
        if isinstance(r, Exception):
            print(f"问题 {i} 异常: {r}")
            processed_results.append({"生成答案": f"错误: {str(r)}"})
        else:
            processed_results.append(r)

    return processed_results

async def process_all(questions, batch_size=50):
    answers = []
    print(f"总问题数: {len(questions)}")
    for i in range(0, len(questions), batch_size):
        batch = questions[i:i + batch_size]
        print(f"处理第 {i // batch_size + 1} 批")
        results = await predict(batch, nums=None)  # 直接用 await
        # pprint(results)
        answers.extend(results)
    print(f"\n最终答案总数: {len(answers)}")
    return answers


if __name__ == '__main__':
    with open('/backend/qa_engine/app/model_evaluation/predict/q_and_a/少量问题/questions_law.json', 'r', encoding='utf-8') as f:
        data1 = json.load(f)
    data1 = pd.DataFrame(data1)
    data2 = pd.read_excel('F:/kedaxunfei/code/backend/qa_engine/q_and_a/少量问题/sql.xlsx')
    data2 = data2.iloc[:,:2]
    print(len(data1))
    print(len(data2))
    data1.rename(columns={'user_question': 'question', 'answer_chunks': 'answer'}, inplace=True)
    data2.rename(columns={'问题': 'question', '标准答案': 'answer'}, inplace=True)
    # print(data1.iloc[0])
    # print(data2.iloc[0])

    data = pd.concat([data1, data2], axis=0)
    questions = data.iloc[:, 0].values.tolist()

    # questions = questions[:1]

    answers = asyncio.run(process_all(questions, batch_size=50))

    load_dotenv(os.path.join(os.path.dirname(__file__),'app', ".env"))

    llm_model_name = os.getenv('LLM_MODEL', 'unknown_model')
    safe_name = re.sub(r'[\\/:*?"<>|\-]', '_', llm_model_name)  # 清理非法字符
    # df_answers = pd.DataFrame(answers)
    # df_answers.to_csv(f'./q_and_a/answers_{safe_name}.csv',encoding='utf-8',index=False)
    # print(f"DataFrame 行数: {len(df_answers)}")

    with open(f'q_and_a/answers_{safe_name}.json', 'w', encoding='utf-8') as f:
        json.dump(answers, f, ensure_ascii=False, indent=4)





