import json

def get_q_a(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        datas = json.load(f)

    print(len(datas))
    q_a = []

    for data in datas:
        user_question = data['instruction']
        answer_chunks = [item['answer'] for item in data['output']]

        q_a.append({
            'user_question': user_question,
            'answer_chunks': answer_chunks
        })

    for data in datas:
        for item in data['output']:
            user_question = item['source']
            answer_chunks = item['answer']
            q_a.append({
                'user_question': user_question,
                'answer_chunks': [answer_chunks]
            })

    return q_a


def get_q_a2(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        datas = json.load(f)

    # 定义映射关系：旧键 -> 新键
    # 根据截图，输入键可能是 instruction 或 question，输出键是 output
    key_mapping = {
        'question': 'user_question',
        'instruction': 'user_question',  # 将 instruction 也归为 user_question
        'answer': 'answer_chunks',
        'output': 'answer_chunks'  # 将 output 也归为 answer_chunks
    }

    for data in datas:
        # 【关键修正】必须获取当前正在处理的 data 的键，而不是 datas[0] 的键
        current_keys = list(data.keys())

        for k in current_keys:
            if k in key_mapping:
                new_key = key_mapping[k]
                # 赋值并删除旧键
                data[new_key] = data.pop(k)

    error_ids = []
    for i,data in enumerate(datas):
        if 'user_question' in data and 'answer_chunks' in data:
            continue
        else:
           error_ids.append(i)
    error_ids.sort(reverse=True)
    print(error_ids)
    for idx in error_ids:
        del datas[idx]
    return datas


def merge_q_a(q_a_pathlist:list):
    q_a_merged = []
    for path in q_a_pathlist:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        for item in data:
            q_a_merged.append({"user_question":item['user_question'],"answer_chunks":item['answer_chunks'] if isinstance(item['answer_chunks'], list) else [item['answer_chunks']]})
    return q_a_merged


if __name__ == '__main__':
    # q_a = get_q_a('xiaofirst中华人民共和国招标投标法律法规全书.json')
    # print(len(q_a))
    # with open('q_a1_clear.json', 'w', encoding='utf-8') as f:
    #     json.dump(q_a, f, ensure_ascii=False, indent=4)

    # datas = get_q_a2(file_path='../../data_for_recall/2.json')
    # print(len(datas))
    # with open('q_a3_clear.json', 'w', encoding='utf-8') as f:
    #     json.dump(datas, f, ensure_ascii=False, indent=4)

    q_a_list = ['q_a1_clear.json','q_a2_clear.json','q_a3_clear.json']
    q_a_merged = merge_q_a(q_a_list)
    print(q_a_merged[0])
    print(len(q_a_merged))

    with open('q_a_merged.json', 'w', encoding='utf-8') as f:
        json.dump(q_a_merged, f, ensure_ascii=False, indent=4)