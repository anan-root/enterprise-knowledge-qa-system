import asyncio
import json
import os
from pprint import pprint
from dotenv import load_dotenv
from fastmcp import Client
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

async def main():
    """使用 fastmcp.Client 连接企查查 MCP HTTP 服务器"""

    # 企查查 MCP 配置 - 使用正确的 URL 和 Headers
    config = {
  "mcpServers": {
    "qcc-company": {
      "url": "https://agent.qcc.com/mcp/company/stream",
      "headers": {
        "Authorization": f"Bearer {os.getenv('qcc_api_key')}"
      }
    },
    "qcc-risk": {
      "url": "https://agent.qcc.com/mcp/risk/stream",
      "headers": {
        "Authorization": f"Bearer {os.getenv('qcc_api_key')}"
      }
    },
    "qcc-ipr": {
      "url": "https://agent.qcc.com/mcp/ipr/stream",
      "headers": {
        "Authorization": f"Bearer {os.getenv('qcc_api_key')}"
      }
    },
    "qcc-operation": {
      "url": "https://agent.qcc.com/mcp/operation/stream",
      "headers": {
        "Authorization": f"Bearer {os.getenv('qcc_api_key')}"
      }
    },
  }
}

    # 使用配置初始化客户端
    client = Client(config)

    async with client:
        print("✅ 已连接到企查查 MCP 服务器 (company 服务)")

        # 获取可用的工具列表
        tools = await client.list_tools()
        print(f"\n📋 发现 {len(tools)} 个可用工具：")
        tools_data = []
        for tool in tools:
            tool_dict = {
                "name": tool.name,
                "title": getattr(tool, 'title', None),
                "description": tool.description,
                "inputSchema": tool.inputSchema,
                "outputSchema": getattr(tool, 'outputSchema', None),
                "icons": getattr(tool, 'icons', None),
                "annotations": getattr(tool, 'annotations', None),
                "meta": getattr(tool, 'meta', None),
                "execution": getattr(tool, 'execution', None),
                "_registration_tool": getattr(tool, '_registration_tool', None),
            }
            tools_data.append(tool_dict)
        pprint(tools_data)
        # 保存为JSON文件
        output_file = "qcc_tools_operation.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(tools_data, f, ensure_ascii=False, indent=2)

        print(f"\n💾 工具信息已保存到: {output_file}")


        # # 调用工具 - 根据实际返回的工具名称调整
        # # 企查查常见工具名可能包括：company_search, get_company_info 等
        # try:
        #     result = await client.call_tool(
        #         "get_dishonest_info",  # 请根据实际工具名称调整
        #         {"searchKey": "上海洛景企业管理有限公司"}  # 根据实际参数格式调整
        #     )
        #     print("\n🔍 查询结果：")
        #     print(result)
        #
        # except Exception as e:
        #     print(f"\n❌ 调用工具失败: {e}")
        #     print("提示：请根据上面列出的可用工具名称调整 call_tool 的第一个参数")


def convert_mcp_tools_to_openai(mcp_tools: list, save_path: str = None) -> list:
    """
    将 MCP 工具格式转换为 OpenAI Function Calling 格式
    可选保存为 JSON 文件供后续直接使用
    """
    openai_tools = []
    for tool in mcp_tools:
        raw_schema = tool.get("inputSchema", {})
        clean_parameters = {
            "type": raw_schema.get("type", "object"),
            "properties": raw_schema.get("properties", {}),
            "required": raw_schema.get("required", [])
        }

        openai_tool = {
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool.get("description", ""),
                "parameters": clean_parameters
            }
        }
        openai_tools.append(openai_tool)

    # 保存为 JSON（如果指定路径）
    if save_path:
        with open(save_path, 'w', encoding='utf-8') as f:
            json.dump(openai_tools, f, ensure_ascii=False, indent=2)
        print(f"💾 已保存到: {save_path}")

    return openai_tools




if __name__ == "__main__":
    asyncio.run(main())
    # with open('./qcc_tools_risk.json', 'r', encoding='utf-8') as f:
    #     raw_qcc_tools = json.load(f)
    #
    # # 转换并保存
    # qcc_tools = convert_mcp_tools_to_openai(raw_qcc_tools, save_path='qcc_tools_openai.json')