import asyncio
import json
import os
import re
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
import logging
import numpy as np
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', ".env"))
# ============ 配置日志 ============
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


client = AsyncOpenAI(
    api_key=os.getenv("API_KEY"),
    base_url=os.getenv("BASE_URL")
)


@dataclass
class SubQuestion:
    """子问题"""
    content: str  # 子问题内容
    q_type: str  # "law" | "sql" | "web"
    contexts: List[str]  # 该子问题检索到的片段列表
    score: float = None #law和web的reranker得分
    sql_query: Optional[str] = None  # SQL场景专用


@dataclass
class EvalResult:
    """评估结果"""
    score: float
    raw_result: str
    metric: str
    evaluator: str


# ============ 1. 基础评估器（只负责 context_relevancy） ============
class LawRetrieverEvaluator:
    """法律检索评估器 - 只评估子问题的检索质量"""

    async def evaluate_retrieval(self, sub_question: str, contexts: List[str],score:float) -> EvalResult:
        """评估子问题的检索质量（context_relevancy）"""
        return EvalResult(
            score=score if score is not None else 0.5,
            raw_result=None,
            metric="context_relevancy",
            evaluator="law"
        )


class SQLRetrieverEvaluator:
    """SQL检索评估器 - 只评估子问题的检索质量"""

    def __init__(self, model: Optional[str] = None):
        self.model = model or os.getenv("RAGAS_LLM")

    def _extract_score(self, result: str) -> float:
        patterns = [
            r'(?:\*\*)?(?:分数|总分|Score|得分|评分)(?:\*\*)?[:：]\s*((?:0\.\d{1,2}|1\.0{1,2}|1|0))',
            r'(?:分数|总分|得分|评分|Score|score|综合得分|综合评分|最终得分)[:：\s]*[\*<【（(]*\s*(\d\.\d{1,2}|\d{1,2}(?:\.\d+)?%?)',
        ]
        for pattern in patterns:
            match = re.search(pattern, result, re.IGNORECASE)
            if match:
                return min(max(float(match.group(1)), 0.0), 1.0)
        return 0.5

    async def evaluate_retrieval(self, sub_question: str, contexts: List[str],score:float) -> EvalResult:
        try:
            """评估SQL子问题的检索质量"""
            combined_context = "\n\n---\n\n".join([f"[查询结果{i + 1}]\n{ctx}" for i, ctx in enumerate(contexts)])

            prompt = f"""
            你是一名数据库架构评审员。请评估SQL查询结果对回答子问题的有效程度。
    
            【评估标准】
            1. Schema匹配度（40%）：查询的表和字段是否直接对应子问题
            2. 数据时效（30%）：数据更新时间是否满足子问题要求
            3. 过滤精准度（30%）：WHERE条件是否精准，有无多余或遗漏
    
            【评分标准】
            - 1.00：表/字段完全匹配、数据最新、过滤精准
            - 0.70-0.99：基本匹配但缺少部分字段或数据略旧
            - 0.40-0.69：表相关但字段不匹配，或数据明显过期
            - 0.10-0.39：仅返回关联表，无法直接回答子问题
            - 0.00：完全无关表或数据严重过期
    
            【子问题】
            {sub_question}
    
            【SQL查询结果片段】
            {combined_context}
    
            【输出格式】
            分析：<Schema匹配度、数据时效、过滤条件说明>
            分数: <0.00-1.00，保留2位>
            Schema问题: <表/字段不匹配的具体问题>
            时效警告: <数据过期或更新不及时>
            遗漏判断: <子问题要求的数据是否都检索到了>
            
            【输出示例】
            分析:分析内容
            分数:0.76
            Schema问题:问题内容
            时效警告: 警告内容
            遗漏判断: 遗漏内容            
            """

            response = await client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                extra_body={"enable_thinking": False},
                temperature=0.0
            )

            result = response.choices[0].message.content
            score = self._extract_score(result)

            return EvalResult(
                score=score,
                raw_result=result,
                metric="context_relevancy",
                evaluator="sql"
            )
        except Exception as e:
            logger.error(f"SQL评估器异常: {e}")
            return EvalResult(
                score=0.5,  # 异常时返回默认值
                raw_result=f"评估异常: {str(e)}",
                metric="context_relevancy",
                evaluator="sql"
            )

class WebRetrieverEvaluator:
    """互联网检索评估器 - 只评估子问题的检索质量"""

    async def evaluate_retrieval(self, sub_question: str, contexts: List[str],score:float) -> EvalResult:
        """评估互联网子问题的检索质量"""
        return EvalResult(
            score=score if score is not None else 0.5,
            raw_result=None,
            metric="context_relevancy",
            evaluator="web"
        )


# ============ 2. 全局生成评估器（评估最终答案） ============
class AnswerGeneratorEvaluator:
    """
    全局答案生成评估器
    - 基于所有子问题的检索片段（汇总后）评估最终答案
    - 评估 faithfulness + answer_relevancy
    """

    def __init__(self, model: Optional[str] = None):
        self.model = model or os.getenv("RAGAS_LLM")

    def _extract_score(self, result: str) -> float:
        patterns = [
            r'(?:\*\*)?(?:分数|总分|Score|得分|评分)(?:\*\*)?[:：]\s*((?:0\.\d{1,2}|1\.0{1,2}|1|0))',
            r'(?:\*\*)?(?:总分|Total Score)(?:\*\*)?[:：]\s*((?:0\.\d{1,2}|1\.0{1,2}|1|0))',
        ]
        for pattern in patterns:
            match = re.search(pattern, result, re.IGNORECASE)
            if match:
                return min(max(float(match.group(1)), 0.0), 1.0)
        return 0.5

    async def evaluate_faithfulness(
            self,
            original_question: str,
            all_retrievals:str,
            final_answer: str
    ) -> EvalResult:
        """
        全局忠实度：评估最终答案是否忠实于所有检索片段
        不同来源的片段有不同的忠实度标准
        """


        prompt = f"""
        你是一名招投标综合合规审查员。请严格评估最终答案中的每个声明是否能在所有检索片段中找到依据。

        【多源审查标准】
        对于法律片段：
        - 只有片段中的明确文字表述才能支持
        - 时间、金额、比例、资格条件等数字必须完全匹配原文
        - 可适当概括、转述

        对于SQL数据片段：
        - 数值精确匹配，禁止四舍五入或估算
        - 字段溯源：每个数据点必须能追溯到具体表和字段
        - 单位检查：万元/元、百分比/小数必须一致

        对于互联网片段：
        - 事实一致性：关键事实、数据必须与网页内容一致
        - 允许合理概括，但禁止添加网页未提及的信息
        - 多源冲突时应说明分歧，而非武断选择

        【评估步骤】
        1. 将最终答案拆分为独立声明（事实、数据、法条引用）
        2. 对每个声明，在所有片段中查找依据，标注来源类型
        3. 按各自的标准判定（法律片段用法律标准，SQL片段用数据标准）
        4. 忠实度 = 得到支持的声明数 / 总声明数

        【原始问题】
        {original_question}

        【所有检索片段（按子问题分组）】
        {all_retrievals}

        【最终答案】
        {final_answer}

        【输出格式】
        逐条审查：
        1. [声明内容] → 支持/不支持 | 来源：[子问题X-片段Y] | 类型：[law/sql/web] | 风险：[无/数值偏差/法条错配/推断/多源冲突]
        ...
        分数: <0.00-1.00，保留2位>
        风险标记: <按严重程度列出所有风险>
        未验证声明: <所有片段都无依据的声明>
        跨源冲突: <不同来源信息矛盾的地方>
        
        【输出示例】
        分数: 0.76
        风险标记: 风险内容
        未验证声明: 未验证内容
        跨源冲突: 冲突内容
        """

        response = await client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            extra_body={"enable_thinking": False},
            temperature=0.0
        )

        result = response.choices[0].message.content
        score = self._extract_score(result)

        return EvalResult(
            score=score,
            raw_result=result,
            metric="faithfulness",
            evaluator="global"
        )

    async def evaluate_answer_relevancy(
            self,
            original_question: str,
            sub_questions: List[SubQuestion],
            final_answer: str
    ) -> EvalResult:
        """
        全局答案相关性：评估最终答案对原始问题的回应质量
        需要考虑是否整合了各子问题的信息
        """
        # 提取所有子问题内容
        sub_q_text = "\n".join([f"{i + 1}. [{sq.q_type}] {sq.content}" for i, sq in enumerate(sub_questions)])

        prompt = f"""
        你是一名招投标业务总监。请评估最终答案对原始问题的综合回应质量。

【评估维度】（每项权重25%，共4项）
1. 直接回应度：是否直接、明确地回答了原始问题的核心诉求
2. 子问题利用度：是否在最终答案中有效利用了与原始问题相关的子问题信息（不要求覆盖所有子问题，只评估所用部分是否恰当）
3. 信息整合度：是否将检索到的信息有机整合，而非简单拼接或罗列
4. 逻辑自洽性：答案内部是否存在矛盾（如法律条文与数据结论冲突时是否妥善处理）

【评分标准】
- 1.00：完美回应，精准针对原始问题，利用相关信息得当，整合流畅，逻辑严密
- 0.80-0.99：良好，回应核心问题，利用的子问题信息恰当，整合较好但有小瑕疵
- 0.50-0.79：一般，回应了主要问题但信息利用不充分或整合生硬
- 0.20-0.49：较差，仅涉及问题边缘，信息利用明显不足
- 0.00-.19：完全不相关或答非所问

【原始问题】
{original_question}

【子问题参考】
{sub_q_text}

【最终答案】
{final_answer}

【输出格式】
维度评分：<4个维度单项得分（0.00-1.00）>
总分: <加权平均分，保留2位>
信息利用不足的子问题: <与原始问题相关但未在答案中有效使用的子问题>
整合问题: <不同来源信息整合不当的地方>
逻辑矛盾: <答案内部的矛盾点>
改进建议: <如何提升答案质量>

【输出示例】
维度评分：0.85 0.90 0.80 0.95
总分: 0.8750
信息利用不足的子问题: 子问题A（与原始问题相关但未充分利用）
整合问题: 数据引用与结论衔接不够自然
逻辑矛盾: 无
改进建议: 在结论前补充子问题A的关键信息，并将数据与风险结论更紧密结合
        """

        response = await client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            extra_body={"enable_thinking": False},
            temperature=0.0
        )

        result = response.choices[0].message.content
        score = self._extract_score(result)

        return EvalResult(
            score=score,
            raw_result=result,
            metric="answer_relevancy",
            evaluator="global"
        )


# ============ 3. 评估器路由与总控 ============
class EvaluatorFactory:
    """评估器工厂"""

    RETRIEVAL_EVALUATORS = {
        "law": LawRetrieverEvaluator,
        "sql": SQLRetrieverEvaluator,
        "web": WebRetrieverEvaluator,
    }

    @classmethod
    def get_retrieval_evaluator(cls, q_type: str):
        evaluator_class = cls.RETRIEVAL_EVALUATORS.get(q_type)
        if not evaluator_class:
            raise ValueError(f"未知的检索评估器类型: {q_type}")
        return evaluator_class()


class PipelineEvaluator:
    """
    流水线评估总控
    协调子问题级检索评估 + 全局生成评估
    """

    def __init__(self):
        self.generator_evaluator = AnswerGeneratorEvaluator()

    async def evaluate_retrieval_stage(
            self,
            sub_questions: List[SubQuestion]
    ) -> Dict[str, Any]:
        """
        第一阶段：评估每个子问题的检索质量（并行）
        """
        tasks = []
        for sq in sub_questions:
            evaluator = EvaluatorFactory.get_retrieval_evaluator(sq.q_type)
            tasks.append(evaluator.evaluate_retrieval(sq.content, sq.contexts,sq.score))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 按子问题组装结果
        retrieval_results = []
        for sq, result in zip(sub_questions, results):
            if isinstance(result, Exception):
                logger.error(f"子问题评估异常 [{sq.q_type}]: {result}")
                result = EvalResult(
                    score=0.0,
                    raw_result=f"异常: {str(result)}",
                    metric="context_relevancy",
                    evaluator=sq.q_type
                )
            elif result.score is None:  # 额外检查 None
                logger.warning(f"评估器返回 None 分数 [{sq.q_type}]: {sq.content[:50]}...")
                result = EvalResult(
                    score=0.5,
                    raw_result=result.raw_result or "分数为None，使用默认值0.5",
                    metric="context_relevancy",
                    evaluator=sq.q_type
                )
            retrieval_results.append({
                "sub_question": sq.content,
                "q_type": sq.q_type,
                "context_relevancy": {
                    "score": result.score,
                    "raw": result.raw_result
                },
                "pass": (result.score or 0.0) >= 0.6
            })

        # 计算平均检索质量
        avg_retrieval_score = sum(r["context_relevancy"]["score"] for r in retrieval_results) / len(retrieval_results)

        return {
            "stage": "retrieval",
            "sub_question_results": retrieval_results,
            "avg_context_relevancy": round(avg_retrieval_score, 2),
            "all_pass": all(r["pass"] for r in retrieval_results)
        }

    async def evaluate_generation_stage(
            self,
            original_question: str,
            sub_questions: List[SubQuestion],
            all_retrievals:str,
            final_answer: str
    ) -> Dict[str, Any]:
        """
        第二阶段：评估最终答案的生成质量
        """
        faithfulness, relevancy = await asyncio.gather(
            self.generator_evaluator.evaluate_faithfulness(original_question, all_retrievals, final_answer),
            self.generator_evaluator.evaluate_answer_relevancy(original_question, sub_questions, final_answer),
            return_exceptions=True
        )

        # 处理异常
        if isinstance(faithfulness, Exception):
            logger.error(f"忠实度评估异常: {faithfulness}")
            faithfulness = EvalResult(0.0, str(faithfulness), "faithfulness", "global")
        if isinstance(relevancy, Exception):
            logger.error(f"相关性评估异常: {relevancy}")
            relevancy = EvalResult(0.0, str(relevancy), "answer_relevancy", "global")

        return {
            "stage": "generation",
            "faithfulness": {
                "score": faithfulness.score,
                "raw": faithfulness.raw_result
            },
            "answer_relevancy": {
                "score": relevancy.score,
                "raw": relevancy.raw_result
            }
        }

    async def full_evaluation(
            self,
            original_question: str,
            sub_questions: List[SubQuestion],
            all_retrievals: str,
            final_answer: str
    ) -> Dict[str, Any]:
        """
        完整评估流水线
        """
        # 阶段1：检索评估
        retrieval_eval = await self.evaluate_retrieval_stage(sub_questions)

        # 阶段2：生成评估
        generation_eval = await self.evaluate_generation_stage(
            original_question, sub_questions, all_retrievals,final_answer
        )

        # 综合评分
        # 权重：检索质量30%，忠实度40%，答案相关性30%
        total_score = (
                retrieval_eval["avg_context_relevancy"] * 0.3 +
                generation_eval["faithfulness"]["score"] * 0.4 +
                generation_eval["answer_relevancy"]["score"] * 0.3
        )

        # 告警规则
        raw_faithfulness = generation_eval["faithfulness"]["raw"] or ""
        alerts = []
        if not retrieval_eval["all_pass"]:
            low_score_subs = [r["sub_question"] for r in retrieval_eval["sub_question_results"] if not r["pass"]]
            alerts.append(f"以下子问题检索质量不足: {low_score_subs}")

        if generation_eval["faithfulness"]["score"] < 0.8:
            alerts.append("最终答案忠实度低于0.8，存在幻觉风险")

        if generation_eval["answer_relevancy"]["score"] < 0.7:
            alerts.append("最终答案相关性不足，可能未充分回应问题")

        # ✅ 修复：精确匹配"跨源冲突"章节，避免误报
        conflict_markers = [
            r"跨源冲突\s*[:：]\s*(?!无|没有|未发现|不存在)",
            r"跨源冲突\s*[:：]\s*.*?(?=\n|$)"
        ]
        has_conflict = False
        for marker in conflict_markers:
            match = re.search(marker, raw_faithfulness, re.IGNORECASE)
            if match:
                conflict_content = match.group(0).lower()
                if not any(x in conflict_content for x in ["无", "没有", "未发现", "不存在", "none", "no"]):
                    has_conflict = True
                    break

        if has_conflict:
            alerts.append("检测到不同来源信息冲突，建议人工复核")

        return {
            "original_question": original_question,
            "retrieval_evaluation": retrieval_eval,
            "generation_evaluation": generation_eval,
            "total_score": round(total_score, 2),
            "alerts": alerts,
            "pass": bool(total_score >= 0.75 and len(alerts) == 0)
        }





def process_data(json_path):

    with open (json_path, 'r', encoding='utf-8') as f:
        datas = json.load(f)
    print(len(datas))

    original_questions = [data["原问题"] for data in datas]
    all_retrievals = [data["已检索的子问题及其检索信息"] for data in datas]
    final_answers = [data["生成答案"] for data in datas]


    # class SubQuestion:
    #     """子问题"""
    #     content: str  # 子问题内容
    #     q_type: str  # "law" | "sql" | "web"
    #     contexts: List[str]  # 该子问题检索到的片段列表
    #     score: float = None  # law和web的reranker得分
    #     sql_query: Optional[str] = None  # SQL场景专用
    all_sub_questions = []
    for data in datas:
        sub_questions = []
        for d in data["子问题"]:
            content = d["子问题"] #content: str
            q_type = 'law' if d['分类'] == 'F' else('web' if d['分类'] == 'E' else 'sql') #q_type: str

            if q_type == 'sql':
                contexts = [d['sql内容']] #contexts: List[str]
            else:
                contexts = [v['text'] for v in d['vector_chunks']] #contexts: List[str]

            if q_type == 'sql':
                score = 0.0
            elif q_type == 'web':
                if isinstance(d['web_chunks'],dict):
                    d['web_chunks'] = [d['web_chunks']]
                chunks = d.get('web_chunks', [])
                score = float(np.mean([v['score'] for v in chunks])) if chunks else 0.0
            else:  # law
                chunks = d.get('vector_chunks', [])
                score = float(np.mean([v['score'] for v in chunks])) if chunks else 0.0

            sql_query = d["sql语句"] if d["sql语句"] else None  #sql_query: Optional[str] = None
            sub_question = SubQuestion(content=content, q_type=q_type, contexts=contexts, score=score,sql_query=sql_query)
            sub_questions.append(sub_question)
        all_sub_questions.append(sub_questions)

    return original_questions, all_sub_questions, all_retrievals, final_answers

# async def batch_evaluate(original_questions:list, all_sub_questions:list, all_retrievals:list, final_answers:list):
#     semaphore = asyncio.Semaphore(3)
#
#     async def one_evaluate(oq,asq,ar,fa):
#
#         async with semaphore:
#             evaluator = PipelineEvaluator()
#             result = await evaluator.full_evaluation(oq,asq,ar,fa)
#             return result
#
#     tasks=[]
#     for oq,asq,ar,fa in zip(original_questions, all_sub_questions, all_retrievals, final_answers):
#         tasks.append(one_evaluate(oq,asq,ar,fa))
#
#     results = await asyncio.gather(*tasks)
#
#     return results

from tqdm.asyncio import tqdm_asyncio  # 或 from tqdm import tqdm

async def batch_evaluate(
    original_questions: list,
    all_sub_questions: list,
    all_retrievals: list,
    final_answers: list,
    max_concurrent: int = 3
):
    semaphore = asyncio.Semaphore(max_concurrent)
    total = len(original_questions)

    async def one_evaluate(oq, asq, ar, fa, index: int):
        async with semaphore:
            evaluator = PipelineEvaluator()
            result = await evaluator.full_evaluation(oq, asq, ar, fa)
            return index, result  # 返回索引保持顺序

    # 创建所有任务
    tasks = [
        asyncio.create_task(one_evaluate(oq, asq, ar, fa, i))
        for i, (oq, asq, ar, fa) in enumerate(
            zip(original_questions, all_sub_questions, all_retrievals, final_answers)
        )
    ]

    # 使用 tqdm_asyncio 显示进度
    results = [None] * total
    for coro in tqdm_asyncio.as_completed(tasks, total=total, desc="评估进度"):
        index, result = await coro
        results[index] = result

    return results
if __name__ == "__main__":
    from pathlib import Path
    filename = 'answers_qwen3.6_27b.json'
    path = Path(filename)

    original_questions, all_sub_questions, all_retrievals, final_answers = process_data(path)

    # lenth = len(original_questions)
    # np.random.seed(42)
    # rn = np.random.permutation(lenth)[:3]
    # # 将 NumPy 数组转换为 Python 列表
    # rn_list = rn.tolist()
    # print(f"索引列表: {rn_list}")
    #
    # # 使用列表推导式提取
    # original_questions = [original_questions[i] for i in rn_list]
    # all_sub_questions = [all_sub_questions[i] for i in rn_list]
    # all_retrievals = [all_retrievals[i] for i in rn_list]
    # final_answers = [final_answers[i] for i in rn_list]

    # original_questions = original_questions[50:]
    # all_sub_questions = all_sub_questions[50:]
    # all_retrievals = all_retrievals[50:]
    # final_answers = final_answers[50:]

    results = asyncio.run(batch_evaluate(original_questions, all_sub_questions, all_retrievals, final_answers))

    # 保存结果
    with open(f'{path.stem}_results.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    logger.info(f"评估完成，共 {len(results)} 条，通过 {sum(1 for r in results if r.get('pass'))} 条")