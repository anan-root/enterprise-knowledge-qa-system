import ast
import json
import asyncio
import os
from typing import  Any
from openai import AsyncOpenAI
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
from fastmcp import Client


# qcc_config = {
#   "mcpServers": {
#     "qcc-company": {
#       "url": "https://agent.qcc.com/mcp/company/stream",
#       "headers": {
#         "Authorization": f"Bearer {os.getenv('qcc_api_key')}"
#       }
#     },
#     "qcc-risk": {
#       "url": "https://agent.qcc.com/mcp/risk/stream",
#       "headers": {
#         "Authorization": f"Bearer {os.getenv('qcc_api_key')}"
#       }
#     },
    # "qcc-ipr": {
    #   "url": "https://agent.qcc.com/mcp/ipr/stream",
    #   "headers": {
    #     "Authorization": f"Bearer {os.getenv('qcc_api_key')}"
    #   }
    # },
    # "qcc-operation": {
    #   "url": "https://agent.qcc.com/mcp/operation/stream",
    #   "headers": {
    #     "Authorization": f"Bearer {os.getenv('qcc_api_key')}"
    #   }
    # },
#   }
# }
# with open(os.path.join(os.path.dirname(__file__) ,'qcc_mcp', 'qcc_tools.json'), 'r', encoding='utf-8') as f:
#     qcc_tools = json.load(f)
with open(os.path.join(os.path.dirname(__file__),'qcc_mcp', 'qcc_tools_company.json'),'r',encoding='utf-8') as f:
    qcc_tools_company = json.load(f)
with open(os.path.join(os.path.dirname(__file__),'qcc_mcp',  'qcc_tools_risk.json'),'r',encoding='utf-8') as f:
    qcc_tools_risk = json.load(f)
with open(os.path.join(os.path.dirname(__file__),'qcc_mcp',  'qcc_tools_operation.json'),'r',encoding='utf-8') as f:
    qcc_tools_operation = json.load(f)
qcc_tools = qcc_tools_company + qcc_tools_risk + qcc_tools_operation
# print(len(qcc_tools))
company_tool_names = [t['name'] for t in qcc_tools_company]
risk_tool_names = [t['name'] for t in qcc_tools_risk]
operation_tool_names = [t['name'] for t in qcc_tools_operation]


company_config = {
    "mcpServers": {
        "qcc-company": {
            "url": "https://agent.qcc.com/mcp/company/stream",
            "headers": {"Authorization": f"Bearer {os.getenv('qcc_api_key')}"}
        }
    }
}

risk_config = {
    "mcpServers": {
        "qcc-risk": {
            "url": "https://agent.qcc.com/mcp/risk/stream",
            "headers": {"Authorization": f"Bearer {os.getenv('qcc_api_key')}"}
        }
    }
}
operation_config = {
    "mcpServers": {
        "qcc-risk": {
            "url": "https://agent.qcc.com/mcp/operation/stream",
            "headers": {"Authorization": f"Bearer {os.getenv('qcc_api_key')}"}
        }
    }
}


class QccMCPToolsManager:
    """自动发现企查查MCP工具并供LLM调用"""
    def __init__(self, api_key: str,base_url: str):
        self.async_client = AsyncOpenAI(api_key=api_key,base_url=base_url)

        self.company_tool_names = company_tool_names
        self.risk_tool_names = risk_tool_names
        self.operation_tool_names = operation_tool_names

        self.tools = qcc_tools
        self.toollist = [{'name':tool['name'],'description':tool['description']} for tool in self.tools]

        self.company_client = Client(company_config)
        self.risk_client = Client(risk_config)
        self.operation_client = Client(operation_config)

    async def chat(self, user_question: str):
        """Step 2: LLM自动判断调用哪些工具"""
        # 第一轮：LLM选择工具

        prompt = f'''请根据用户问题，选择可以解决该问题的工具。
        【工具清单】
        {self.toollist},
        
        【用户问题】
        {user_question},
        
        【输出要求】
        1. 根据工具清单中的'description'来选择一个或多个工具;
        2. 仅以列表的形式返回所需工具的name，不要多余信息;
        3. 提取用户问题中需要查询的公司名称，与要求2组成嵌套列表;
        4. 如果没有工具需要选择，或者提取不到公司名称，则返回空列表[];
        5. 如果有多个公司要组成嵌套列表;
        6. get_company_registration_info工具必须被选中
        
        例子：
        [[['get_administrative_penalty','get_bankruptcy_reorganization'],'公司名称1'],[['get_administrative_penalty','get_bankruptcy_reorganization'],'公司名称2']]
        []
        
        请直接输出Python列表：       
        '''
        response = await self.async_client.chat.completions.create(
            model=os.getenv('CLS_MODEL'),
            messages=[{"role": "system", "content": "你是一个企查查mcp选择助手，根据用户问题选择相关的工具。"},
                {"role": "user", "content": prompt}],
            extra_body={"enable_thinking": False},
            temperature=0
        )
        results = response.choices[0].message.content

        try:
            parsed_results = ast.literal_eval(results)
            print(parsed_results)
            tool_names = []
            company_names = []
            for parsed_result in parsed_results:
                if isinstance(parsed_result, list) and len(parsed_result) == 2:
                    company_name = parsed_result[1]
                    if isinstance(company_name, list):
                        company_name = company_name[0]
                    else:
                        company_name = str(company_name)
                    company_names.append(company_name)
                    print(company_name)
                    if isinstance(parsed_result[0], list):
                        tool_name = [str(t) for t in parsed_result[0]]
                        tool_names.append(tool_name)
                    else:
                        tool_name = []
                        tool_names.append(tool_name)
                else:
                    company_name = ''
                    tool_names.append(company_name)
                    tool_name = []
                    tool_names.append(tool_name)

        except Exception as e:
            print(str(e))
            tool_names = []
            company_names = []

        tasks = [self._execute_tool(t_name,company_name)
                 for tool_name,company_name in zip(tool_names,company_names)
                 for t_name in tool_name]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        risk_results = []
        for tool_name, result in zip([t_name for tool_name in tool_names for t_name in tool_name], results):
            if isinstance(result, Exception):
                risk_results.append({
                    'tool_name': tool_name,
                    'content': f"调用失败: {str(result)}"
                })
            else:
                risk_results.append({
                    'tool_name': tool_name,
                    'content': result
                })

        risk_results_dict = {company_name:[] for company_name in company_names}
        len_tools = [len(tool_name) for tool_name in tool_names]
        i=0
        for company_name,num in zip(company_names,len_tools):
            risk_results_dict[company_name]= risk_results[i:i+num]
            i += num

        return risk_results_dict

    async def _execute_tool(self, tool_name, company_name) -> Any:
        """执行单个工具调用"""
        tool_arguments = {"searchKey": company_name}

        # 选择正确的 client
        if tool_name in company_tool_names:
            client = self.company_client
        elif tool_name in risk_tool_names:
            client = self.risk_client
        else:
            client = self.operation_client

        try:
            async with client:
                result = await client.call_tool(tool_name, tool_arguments)
                content =  result.content[0]
                if hasattr(content,"text"):
                    return content.text
                else:
                    texts = []
                    async for chunk in content:
                        texts.append(chunk)
                    return "".join(texts)

        except Exception as e:
            print("error:", "tool_name:",tool_name,str(e))
            return f"调用失败: {str(e)}"

    async def company_check(self, user_question: str):
        # 1. 提取公司名称
        prompt = f'''请根据用户问题，提取要查询的公司名称。                
                【用户问题】
                {user_question},

                【输出要求】
                1. 提取用户问题中需要查询的公司名称，返回列表;
                2. 如果没有工具需要选择，或者提取不到公司名称，则返回空列表[];

                例子：
                ['公司名称1','公司名称2']
                []

                请直接输出Python列表：       
                '''
        response = await self.async_client.chat.completions.create(
            model=os.getenv('CLS_MODEL'),
            messages=[{"role": "user", "content": prompt}],
            extra_body={"enable_thinking": False},
            temperature=0
        )
        results = response.choices[0].message.content
        print('提取实体：',results)
        try:
            company_names = ast.literal_eval(results)
            print(company_names)
        except Exception as e:
            print(str(e))
            company_names = []

        if not company_names:
            return {}, {}, {}  # 没有公司名，返回三个空字典

        # 2. 为每个公司准备三个工具集的任务
        # company 工具
        company_tasks = [
            self._execute_tool(t_name, company_name)
            for company_name in company_names
            for t_name in self.company_tool_names
        ]

        # risk 工具
        risk_tasks = [
            self._execute_tool(t_name, company_name)
            for company_name in company_names
            for t_name in self.risk_tool_names
        ]

        # operation 工具
        operation_tasks = [
            self._execute_tool(t_name, company_name)
            for company_name in company_names
            for t_name in self.operation_tool_names
        ]

        # 3. 并行执行所有任务
        company_results, risk_results, operation_results = await asyncio.gather(
            asyncio.gather(*company_tasks, return_exceptions=True),
            asyncio.gather(*risk_tasks, return_exceptions=True),
            asyncio.gather(*operation_tasks, return_exceptions=True)
        )

        # 4. 分别整理三个结果字典
        company_results_dict = self._organize_results(
            company_names, self.company_tool_names, company_results
        )
        risk_results_dict = self._organize_results(
            company_names, self.risk_tool_names, risk_results
        )
        operation_results_dict = self._organize_results(
            company_names, self.operation_tool_names, operation_results
        )

        return company_results_dict, risk_results_dict, operation_results_dict

    def _organize_results(self, company_names, tool_names, results):
        """辅助方法：整理结果为 {公司名: [{tool_name, content}, ...]} 格式"""
        organized = []
        for tool_name, result in zip(
                [t for _ in company_names for t in tool_names], results
        ):
            if isinstance(result, Exception):
                organized.append({
                    'tool_name': tool_name,
                    'content': f"调用失败: {str(result)}"
                })
            else:
                organized.append({
                    'tool_name': tool_name,
                    'content': result
                })

        results_dict = {company_name: [] for company_name in company_names}
        tools_per_company = len(tool_names)

        for i, company_name in enumerate(company_names):
            start_idx = i * tools_per_company
            end_idx = start_idx + tools_per_company
            results_dict[company_name] = organized[start_idx:end_idx]

        return results_dict


async def qcc_riskcheck(user_question: str):
    manager = QccMCPToolsManager(os.getenv('API_KEY'),os.getenv('BASE_URL'))
    company_results_dict, risk_results_dict, operation_results_dict = await manager.company_check(user_question)
    return company_results_dict, risk_results_dict, operation_results_dict



if __name__ == '__main__':
    # a,b,c = asyncio.run(qcc_riskcheck('企查查科技股份有限公司和上海洛景企业管理有限公司还有星空公司有税务风险吗？'))
    a = asyncio.run(qcc_riskcheck('融创中国怎么样'))
    print(a)
    # print()
    # print(b)
    # print()
    # print(c)
    # for i in a:
    #     print(f'共计调用工具{len(a[i])}个')