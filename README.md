# 企业知识库智能问答系统

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688?style=flat-square&logo=fastapi&logoColor=white)
![Vue](https://img.shields.io/badge/Vue-3.x-42B883?style=flat-square&logo=vue.js&logoColor=white)
![TypeScript](https://img.shields.io/badge/TypeScript-5.x-3178C6?style=flat-square&logo=typescript&logoColor=white)
![Vite](https://img.shields.io/badge/Vite-5.x-646CFF?style=flat-square&logo=vite&logoColor=white)
![MySQL](https://img.shields.io/badge/MySQL-Structured%20Data-4479A1?style=flat-square&logo=mysql&logoColor=white)
![Milvus](https://img.shields.io/badge/Milvus-Vector%20Search-00A1EA?style=flat-square)
![Redis](https://img.shields.io/badge/Redis-Cache-DC382D?style=flat-square&logo=redis&logoColor=white)
![RAG](https://img.shields.io/badge/RAG-BM25%20%2B%20Vector%20%2B%20Rerank-7C3AED?style=flat-square)
![Status](https://img.shields.io/badge/status-MVP-0A7BBB?style=flat-square)

企业知识库智能问答系统是一个面向企业内部知识问答与业务资料检索的智能系统原型。它围绕“多轮提问、问题拆分、结构化数据查询、法规/文档知识库检索、联网搜索、企业风险查询、流式回答”这一条主流程，帮助用户从企业知识库和外部数据源中快速获得可追溯的回答。

当前项目以招投标业务知识为主要示例场景：系统可以查询企业、项目、产品、供应商等结构化数据，也可以检索招投标法规资料、实时招标信息和企业风险信息。项目定位为企业内部 MVP，适合流程验证、样例测试和后续产品化开发，不建议直接作为无人值守的正式决策系统。

> 安全提醒：真实 API Key、数据库密码、Redis 密码、企查查/剑鱼接口密钥、`.env`、生成的索引文件、运行缓存和评测产物都不应提交到 Git。公开仓库前请检查 `.env`、`node_modules/`、`__pycache__/`、`*.pkl`、`*_bm25.txt` 和历史提交。

## 项目定位

这个项目不是普通的大模型聊天框，而是一个面向企业知识场景的问答工作台。系统会先理解用户问题，再根据问题类型选择不同的数据源和检索方式，最后基于检索结果生成回答。

核心链路：

```text
用户提问
  -> 多轮历史改写
  -> 问题拆分与分类
  -> A/B/C/D/E/F 多路检索
  -> 检索结果汇总
  -> 大模型生成回答
  -> 前端流式展示
  -> 会话保存与摘要压缩
```

## 主要能力

- **流式问答**：前端实时展示后端生成内容，支持停止生成。
- **多轮记忆**：结合历史会话改写当前问题，解决“它”“这个公司”“刚才那个项目”等指代问题。
- **问题拆分与分类**：将复杂问题拆成多个子问题，并标注不同处理类型。
- **结构化数据查询**：通过自然语言生成 SQL，查询企业、项目、产品、供应商等结构化数据。
- **法规知识库 RAG**：使用 BM25、Milvus 向量检索、HyDE、SimHash 去重和 rerank 检索法规资料。
- **企业风险查询**：对接企查查相关工具，整理企业基本信息、风险信息和经营信息。
- **实时招标查询**：从用户问题中抽取查询参数，调用实时招投标数据接口。
- **联网搜索 RAG**：对需要外部信息的问题进行网页搜索、正文抽取、切片、重排和回答。
- **会话管理**：支持新建、切换、删除、收藏、标题生成和本地降级缓存。
- **开发 Trace 文档**：提供从零讲解项目的设计和开发过程，见 `docs/qa_system_trace.md`。

## 技术栈

| 层级 | 技术 |
| --- | --- |
| 前端 | Vue3、TypeScript、Vite、Pinia、Vue Router、Marked |
| 后端 | FastAPI、Uvicorn、Pydantic、OpenAI-compatible SDK |
| 数据 | MySQL、Redis、Milvus |
| 检索 | BM25、jieba、BGE-M3 embedding、Milvus dense vector search、BGE reranker、SimHash |
| AI 链路 | 问题分类与拆分、Query rewrite、HyDE、RAG、多源检索结果融合、流式生成 |
| 工程文档 | README、从零开发 Trace、环境变量模板、Git 忽略规则 |

## 目录结构

```text
.
├── backend/
│   ├── run_api.py
│   └── qa_engine/
│       ├── main.py
│       ├── main_api_with_memory.py
│       ├── app/
│       │   ├── questions_classify.py
│       │   ├── prompt_templates.py
│       │   ├── routers.py
│       │   ├── sql_retrieval_langchain.py
│       │   ├── vector_bm25_milvus_retrieval.py
│       │   ├── web_search_async.py
│       │   ├── memory_history.py
│       │   └── session_manager.py
│       └── data_processing/
│           ├── clean_md.py
│           ├── md2nodes.py
│           ├── nodes2pkl.py
│           └── nodes2vector_m3_milvus.py
├── frontend1/
│   ├── package.json
│   └── src/
│       ├── views/
│       ├── components/
│       ├── composables/
│       ├── stores/
│       └── router/
├── docs/
│   └── qa_system_trace.md
├── start_all.py
└── README.md
```

## 问题分类

后端会将用户问题拆分为子问题，并按 A-F 分类路由：

| 类别 | 含义 | 处理方式 |
| --- | --- | --- |
| A | 结构化信息检索 | 自然语言转 SQL，查询 MySQL |
| B | 信息推荐 | 基于结构化检索结果做价格、地点、风险排序 |
| C | 实时招投标查询 | 抽取参数后调用实时招标接口 |
| D | 企业风险判断 | 调用企业信息和风险工具，生成风险报告 |
| E | 其他 / 联网搜索 | 判断是否联网，必要时做 Web RAG |
| F | 法律法规检索 | BM25 + 向量 + HyDE + rerank 的法规 RAG |

## 核心流程

### 1. 前端发送问题

入口文件：

```text
frontend1/src/components/ChatArea.vue
frontend1/src/views/ChatView.vue
frontend1/src/composables/useChat.ts
```

前端会先把用户消息加入当前会话，再创建一条空的 assistant 消息。后端每返回一个 chunk，前端就更新这条 assistant 消息，实现流式展示。

### 2. 后端接收聊天请求

入口文件：

```text
backend/qa_engine/main_api_with_memory.py
```

主接口：

```text
POST /api/chat/stream
```

后端会读取会话历史，调用问题改写模块，然后把改写后的问题交给核心问答 pipeline。

### 3. 问题改写

文件：

```text
backend/qa_engine/app/memory_history.py
```

作用：

- 将“它有没有风险”改写成明确问题。
- 保留最近 10 轮完整对话。
- 更早对话按批次压缩成摘要。

### 4. 分类、检索、生成

文件：

```text
backend/qa_engine/main.py
backend/qa_engine/app/routers.py
```

核心函数：

```python
main_stream()
retrieval()
router_A()
router_B()
router_C()
router_D()
router_E()
router_F()
```

系统会根据分类结果调用不同 router，再把所有检索结果交给最终回答 prompt 生成答案。

## 法规 RAG 设计

法规知识库检索使用多路召回：

```text
用户问题
  -> BM25 关键词召回
  -> 原问题向量召回
  -> HyDE 假答案向量召回
  -> SimHash 去重
  -> BGE rerank
  -> top_k 片段进入最终回答
```

对应文件：

```text
backend/qa_engine/app/vector_bm25_milvus_retrieval.py
backend/qa_engine/data_processing/nodes2pkl.py
```

### BM25

使用 `jieba` 对中文法规文本分词，再用 `rank_bm25` 构建关键词索引。BM25 适合召回包含明确法规术语的片段。

### 向量检索

通过 BGE-M3 embedding 服务生成 dense vector，在 Milvus 中检索语义相近的法规片段。

### HyDE

先让模型根据问题生成一段“可能包含答案的假答案”，再用假答案做向量检索。这样可以提升法规类问题的语义召回能力。

### Rerank

候选片段会发送到 BGE reranker 服务：

```json
{
  "query": "用户问题",
  "documents": ["候选片段1", "候选片段2"],
  "normalize": true
}
```

系统按相关性分数过滤低质量片段，并取 top_k 作为最终证据。

## 环境变量

复制环境模板：

```bash
copy backend\qa_engine\app\.env.example backend\qa_engine\app\.env
```

至少需要配置：

```text
API_KEY
BASE_URL
CLS_MODEL
LLM_MODEL
SQL_MODEL
host
user
password
db
include_tables
MILVUS_HOST
MILVUS_PORT
BGE_M3_URL
BGE_RERANKER_URL
BM25_DIR
INDEX_PATH
SERPER_API_KEY
JY_AppID
JY_SecretKey
qcc_api_key
```

注意：`.env` 包含密钥和数据库连接信息，不应提交到 GitHub。

## 本地运行

### 1. 安装前端依赖

```bash
cd frontend1
npm install
```

### 2. 启动后端

```bash
cd backend
python run_api.py
```

后端默认监听：

```text
http://localhost:8000
```

### 3. 启动前端

```bash
cd frontend1
npm run dev
```

前端默认监听：

```text
http://localhost:3000
```

### 4. 一键启动

项目根目录提供了 `start_all.py`：

```bash
python start_all.py
```

它会同时启动后端和前端。

## 构建

```bash
cd frontend1
npm run build
```

## 开发文档

完整设计与开发 Trace：

```text
docs/qa_system_trace.md
```

该文档按从零开发的顺序解释了项目结构、前端、后端、问答 pipeline、RAG、rerank、会话记忆和后续工程化思路。

## 安全说明

- 不要提交 `.env`。
- 不要把真实 API Key、数据库密码、Redis 密码、企查查 Key、剑鱼接口密钥上传到公开仓库。
- 当前项目包含外部服务依赖，运行前需要准备对应服务和环境变量。
- SQL 生成功能建议在生产环境增加只读账号、SQL 白名单和语句校验。

## 当前限制

- 运行依赖外部 LLM、MySQL、Milvus、embedding、reranker、Redis 和搜索接口。
- 法规索引 pkl、BM25 txt、评测结果等生成产物默认不提交，需要本地生成或重新配置。
- 企业风险和实时招标查询依赖第三方接口权限。
- 当前运行时 trace、evidence 独立返回、grounding check 和人工复核流程还可以继续工程化完善。

## License

当前未指定开源许可证。公开使用或二次开发前，请先补充许可证文件。
