"""用修复后的正则从 raw 字段重新提取分数，更新 results JSON 文件。"""
import json
import re

# 与修复后 evaluator.py 中 AnswerGeneratorEvaluator._extract_score 一致
PATTERNS = [
    r'(?:\*\*)?(?:分数|总分|Score|得分|评分)(?:\*\*)?[:：]\s*((?:0\.\d{1,2}|1\.0{1,2}|1|0))',
    r'(?:\*\*)?(?:总分|Total Score)(?:\*\*)?[:：]\s*((?:0\.\d{1,2}|1\.0{1,2}|1|0))',
]


def extract_score(raw: str | None) -> float | None:
    if not raw:
        return None
    for pattern in PATTERNS:
        m = re.search(pattern, raw, re.IGNORECASE)
        if m:
            return min(max(float(m.group(1)), 0.0), 1.0)
    return None


def fix_results(filepath: str):
    with open(filepath, 'r', encoding='utf-8') as f:
        results = json.load(f)

    faith_fixed = 0
    relev_fixed = 0

    for r in results:
        gen = r.get('generation_evaluation', {})
        faith = gen.get('faithfulness', {})
        rel = gen.get('answer_relevancy', {})

        # ---------- 修复 faithfulness ----------
        old_f = faith.get('score')
        new_f = extract_score(faith.get('raw'))
        if new_f is not None and old_f != new_f:
            print(f'  [faithfulness] {old_f} -> {new_f}  | {r["original_question"][:50]}...')
            faith['score'] = new_f
            faith_fixed += 1

        # ---------- 修复 answer_relevancy ----------
        old_r = rel.get('score')
        new_r = extract_score(rel.get('raw'))
        if new_r is not None and old_r != new_r:
            print(f'  [answer_relevancy] {old_r} -> {new_r}  | {r["original_question"][:50]}...')
            rel['score'] = new_r
            relev_fixed += 1

        # ---------- 重新计算 total_score ----------
        avg_retrieval = r['retrieval_evaluation']['avg_context_relevancy']
        total = round(avg_retrieval * 0.3 + faith['score'] * 0.4 + rel['score'] * 0.3, 2)
        r['total_score'] = total

        # ---------- 重新生成 alerts ----------
        alerts = []
        if not r['retrieval_evaluation']['all_pass']:
            low = [sr['sub_question'] for sr in r['retrieval_evaluation']['sub_question_results'] if not sr['pass']]
            alerts.append(f"以下子问题检索质量不足: {low}")
        if faith['score'] < 0.8:
            alerts.append('最终答案忠实度低于0.8，存在幻觉风险')
        if rel['score'] < 0.7:
            alerts.append('最终答案相关性不足，可能未充分回应问题')

        raw_faith = faith.get('raw') or ''
        for marker in [r'跨源冲突\s*[:：]\s*(?!无|没有|未发现|不存在)', r'跨源冲突\s*[:：]\s*.*?(?=\n|$)']:
            m = re.search(marker, raw_faith, re.IGNORECASE)
            if m and not any(x in m.group(0).lower() for x in ['无', '没有', '未发现', '不存在', 'none', 'no']):
                alerts.append('检测到不同来源信息冲突，建议人工复核')
                break

        r['alerts'] = alerts
        r['pass'] = bool(total >= 0.75 and len(alerts) == 0)

    # ---------- 写回 ----------
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f'[{filepath}]  faithfulness 修复: {faith_fixed} 条,  answer_relevancy 修复: {relev_fixed} 条')
    total_items = len(results)
    passed = sum(1 for r in results if r['pass'])
    print(f'[{filepath}]  共 {total_items} 条,  pass: {passed},  fail: {total_items - passed}')


if __name__ == '__main__':
    import sys
    files = sys.argv[1:] if len(sys.argv) > 1 else [
        'answers_qwen3_8b_results_1.json',
        'answers_qwen3_8b_results_2.json',
    ]
    for fp in files:
        print(f'\n===== 处理 {fp} =====')
        fix_results(fp)
    print('\n全部完成.')
