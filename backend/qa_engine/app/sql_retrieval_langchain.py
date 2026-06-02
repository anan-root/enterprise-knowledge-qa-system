import ast
import json
import os
import asyncio
import re
import time

import pandas as pd
from dotenv import load_dotenv
from pprint import pprint
from sqlalchemy import create_engine
from langchain_openai import ChatOpenAI
from langchain_community.utilities import SQLDatabase
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from sqlalchemy import text

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))


# 初始化数据库连接
def get_database():
    """创建数据库连接"""
    host = os.getenv("host")
    user = os.getenv("user")
    password = os.getenv("password")
    db = os.getenv("db")

    # 创建 SQLAlchemy 引擎
    engine = create_engine(f"mysql+pymysql://{user}:{password}@{host}/{db}")

    # 创建 LangChain SQLDatabase
    db_obj = SQLDatabase(
        engine=engine,
        include_tables=ast.literal_eval(os.getenv('include_tables')),
        sample_rows_in_table_info=2  # 每个表在提示词中包含3行示例数据
    )
    return db_obj


# 初始化 LLM
def get_llm():
    """获取 LLM 实例"""
    return ChatOpenAI(
        model=os.getenv("SQL_MODEL"),
        base_url=os.getenv("BASE_URL"),
        temperature=0,
        extra_body={"enable_thinking": False},
        api_key=os.getenv("API_KEY")

    )


def clean_sql_output(sql: str) -> str:
    """清理并校验SQL输出"""
    # 提取 ```sql 代码块
    print(sql)
    match = re.search(r'```sql\s*(.*?)\s*```', sql, re.DOTALL)
    if match:
        sql = match.group(1).strip()
    else:
        # 尝试提取 ``` 代码块
        match = re.search(r'```\s*(.*?)\s*```', sql, re.DOTALL)
        if match:
            sql = match.group(1).strip()
        else:
            sql = sql.strip()

    # 去除可能的阶段标记文本
    lines = sql.split('\n')
    sql_lines = [l for l in lines if not l.strip().startswith('阶段')
                 and not l.strip().startswith('-')
                 and not l.strip().startswith('【')]
    sql = '\n'.join(sql_lines).strip()

    # 3. 仅处理 LIKE 中的匹配值（去掉结尾词）
    def repl(match):
        pattern = match.group(1)
        # 只去掉“结尾”的词
        suffix_map = {
            '项目': '',
            '的产地': '',
            '产地': ''
        }
        for suffix, repl in suffix_map.items():
            if pattern.endswith(suffix):
                pattern = pattern[:-len(suffix)]
                break
        return f"'%{pattern}%'"

    sql = re.sub(r"'%(.*?)%'", repl, sql)
    return sql

def execute_sql(sql: str, db: SQLDatabase) -> pd.DataFrame:
    """执行SQL查询"""
    try:
        # 使用 text() 包装 SQL，避免中文被误解析为格式字符串
        df = pd.read_sql(text(sql), db._engine)
        return df
    except Exception as e:
        print(f"SQL执行错误: {e}")
        raise RuntimeError(f"SQL执行错误: {str(e)}\nSQL语句: {sql}") from e


def dataframe_to_prompt(df) -> str:
    """将DataFrame或错误信息转换为适合LLM理解的字符串格式"""
    if isinstance(df, str):
        return df  # 直接返回错误信息字符串

    if df.empty:
        return "查询结果为空"

    # Markdown表格（LLM理解效果最好）
    markdown_table = df.to_markdown(index=False)
    return markdown_table

def clean_table_info(table_info):
    cleaned = re.sub(r"COMMENT\s+'.*?'", '', table_info)
    return cleaned

semaphore = asyncio.Semaphore(5)
async def natural_language_query_langchain(question: str):
    question = ''.join(question.split())

    """使用 LangChain 的 LCEL 方式"""
    db = get_database()
    llm = get_llm()

    prompt_template = """
        你是一个SQL专家。请严格按照以下两阶段流程生成SQL查询。
        
        ## 阶段一：字段分析
        根据用户问题和数据库表结构，先列出所有可能相关的表,分析需要查询的表和字段。对于每个字段：
        1. 写出字段的中文含义
        2. 写出该表实际定义的字段名（必须严格匹配表结构中的字段名，不能臆造）
        3. 确认该字段存在于目标表中
        
        ## 阶段二：SQL生成
        基于阶段一确认的字段名，生成标准SQL语句，如果涉及多表可以用JOIN或UNION连接。
        
        数据库表结构：
        {table_info}
        
        【注意事项】
        1. 只生成一条SQL语句。
        2. 使用正确的LIKE语法进行模糊匹配，并去除要查询字段的空格，再匹配。
        3. 统计个数的要求，对查询结果没有LIMIT限制。
        4. 其余要求中如果没有明确说明不限制检索条数，则默认LIMIT为不超过20。
        
        
        【SQL生成示例】
        1. 如果匹配内容末尾包含‘项目’两个字必须去掉。
            如：生物分子相互作用分析系统项目是否接受联合体投标？->SELECT `申请人资格要求` FROM `政府招标信息` WHERE REPLACE(`项目名称`, ' ', '') LIKE '%生物分子相互作用分析系统%' LIMIT 20
        2. 上海健康医学院附属崇明医院医疗设备采购（全自动数字化高档彩色多普勒超声仪）项目的联系人是谁？->SELECT `项目联系人` FROM `政府招标信息` WHERE REPLACE(`项目名称`, ' ', '') LIKE '%上海健康医学院附属崇明医院医疗设备采购%' AND `包名称` LIKE '%全自动数字化高档彩色多普勒超声仪%';
        3. 上海电机学院激光增材再制造系统项目中，包2的预算金额是多少？->SELECT `分包最高限价` FROM `政府招标信息` WHERE REPLACE(`项目名称`, ' ', '') LIKE '%上海电机学院激光增材再制造系统%' AND `分包最高限价` LIKE '%包2%';
        4. ND:YAG皮秒激光治疗仪项目的特定资格要求中，是否专门面向中小企业？->SELECT `申请人资格要求` FROM `政府招标信息` WHERE REPLACE(`项目名称`, ' ', '') LIKE '%ND:YAG皮秒激光治疗仪%'
        5. 巨祥冶自流平水泥的初凝时间是多久？->SELECT product_parameters FROM `市场产品信息` WHERE REPLACE(material_name,' ','') LIKE '%巨祥冶自流平水泥%'
        6. 奥典商超不锈钢货架的表面处理工艺是什么？->SELECT product_parameters FROM `市场产品信息` WHERE REPLACE(material_name,' ','') LIKE '%奥典商超不锈钢货架%';
        7. 永久自行车锁防盗锁5位密码锁山地车锁摩托车单车链条锁电动车锁的品牌是什么？->SELECT product_parameters FROM `市场产品信息` WHERE REPLACE(`material_name`, ' ', '') LIKE '%永久自行车锁防盗锁5位密码锁山地车锁摩托车单车链条锁电动车锁%' LIMIT 20
        8. 如果条件值末尾包含‘的产地’几个字必须去掉。如：白色球形锁三杆锁圆锁铝合金门塑钢门卫浴三插锁卫生间的产地是哪里？->SELECT `product_parameters` FROM `市场产品信息` WHERE REPLACE(`material_name`, ' ', '') LIKE '%白色球形锁三杆锁圆锁铝合金门塑钢门卫浴三插锁卫生间%' LIMIT 20

        【用户问题】
        {input}
        
        请按以下格式输出：
        
        阶段一分析：
        - 目标表1：[表名]
        - 需要的字段：[中文含义] -> [实际字段名]
        - 查询条件：[条件字段] -> [实际字段名] = [值]
        
        - 目标表2：[表名]
        - 需要的字段：[中文含义] -> [实际字段名]
        - 查询条件：[条件字段] -> [实际字段名] = [值]
        
        阶段二SQL：
        - ```sql
            [SQL语句]```        
        """
    # 创建提示词
    prompt = PromptTemplate(
        input_variables=["input", "table_info"],
        template=prompt_template
    )

    # 获取表信息（在链外准备，因为它是静态的）
    table_info = db.get_table_info()
    # cleaned_table_info = clean_table_info(table_info)
    # 使用 LCEL 构建链：prompt | llm | parser
    chain = (
            {
                "input": lambda x: x["input"],
                "table_info": lambda x: table_info
            }
            | prompt
            | llm
            | StrOutputParser()
            | clean_sql_output
    )

    sql = None
    last_error = None
    df = None
    success = False

    # 有限次数的重试机制
    for attempt in range(3):  # 最多尝试3次
        try:
            if attempt == 0:
                current_question = question
            else:
                debug_question = f"""
                之前的SQL执行失败，以下是之前的SQL和错误信息：
                之前的SQL语句：{sql}，
                错误信息：{last_error}。
                
                数据库表结构：
                {table_info}
                
                
                请根据用户问题及错误信息修正SQL语句，下面是用户问题：
                {question}
                """
                current_question = debug_question

            # 生成SQL
            async with semaphore:
                sql = await chain.ainvoke({"input": current_question})
            # print(f"第{attempt + 1}次尝试，生成的SQL: {sql}")

            # 执行SQL
            df = execute_sql(sql, db)
            success = True
            if success:
                break  # 成功，跳出循环

        except RuntimeError as e:
            # 捕获SQL执行错误
            last_error = str(e)
            print(f"第{attempt + 1}次尝试失败，SQL错误: {last_error[:100]}")

            if attempt < 2:  # 如果还有重试机会
                await asyncio.sleep(0.5)
            else:
                df = pd.DataFrame()  # 返回空DataFrame
                success = False
                break

        except Exception as e:
            # 捕获其他错误（如LLM调用失败）
            last_error = str(e)
            print(f"第{attempt + 1}次尝试失败，其他错误: {last_error[:100]}")

            if attempt < 2:
                await asyncio.sleep(0.5)
            else:
                df = pd.DataFrame()
                success = False
                break

    # 转换为字符串格式供LLM使用
    if success and isinstance(df, pd.DataFrame) and not df.empty:
        df_str = dataframe_to_prompt(df)
    elif success and isinstance(df, pd.DataFrame) and df.empty:
        df_str = "查询成功，但未找到匹配的数据。"
    else:
        error_msg = last_error if last_error else "未知错误"
        df_str = f"SQL查询失败: {error_msg}"
        df = None
        sql = "未生成有效的SQL"

    return {
        "question": question,
        # "dataframe": df,  # 原始DataFrame，成功时为DataFrame，失败时为None
        "content": df_str,  # 字符串格式
        "sql": sql,
        }


if __name__ == '__main__':
    user_question = input('请输入问题:')
    start = time.time()
    result = asyncio.run(natural_language_query_langchain(user_question))
    end = time.time()
    print(f'time:', end - start)
    print(result['sql'])
    print(result['content'])

    # import pandas as pd
    # datas = pd.read_excel(r'F:\科大讯飞实训\工作目录\汇报ppt\指标表.xlsx',sheet_name='sql_qwen3-8b')
    # questions1 = datas.iloc[:,0].dropna().tolist()
    #
    # user_question = questions1
    # print(len(user_question))
    # # print(user_question)
    #
    #
    #
    # async def main(user_questions, max_concurrent=10):
    #     semaphore = asyncio.Semaphore(max_concurrent)
    #
    #     async def bounded_query(q):
    #         async with semaphore:
    #             return await natural_language_query_langchain(q)
    #
    #     tasks = [bounded_query(q) for q in user_questions]
    #     return await asyncio.gather(*tasks)
    #
    # start = time.time()
    # results = asyncio.run(main(user_question))
    # end = time.time()
    # print(f'time:',end-start)
    #
    # df = pd.DataFrame(results)
    # df.to_csv('sql_df_qwen3-8b_补充.csv',index=False)

