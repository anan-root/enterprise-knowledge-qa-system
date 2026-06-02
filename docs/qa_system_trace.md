# 企业知识库智能问答系统设计与开发 Trace

## 0. 从零开发逐步 Trace

这一节按“如果从零搭建这个项目”的顺序来讲。目标不是改造当前代码，而是把当前项目背后的工程步骤、技术选择和实现路径讲清楚。每一步说明：做什么、为什么做、用了什么技术、对应当前项目里的哪些文件。

### Step 0.1: 明确项目目标

项目目标：

- 做一个招投标领域的智能问答系统。
- 用户可以在网页聊天界面输入问题。
- 系统根据问题类型自动选择不同检索路径。
- 支持结构化数据查询、实时招标信息查询、企业风险查询、法规知识库检索、联网搜索。
- 支持多轮对话记忆，用户后续可以问“它有没有风险”“这个项目合法吗”这类依赖上下文的问题。
- 前端用 Vue3 展示聊天、历史会话、设置。
- 后端用 FastAPI 提供聊天 API 和会话 API。

为什么不是直接做一个“大模型聊天框”：

- 招投标问答需要依据具体数据和法规，不适合完全让大模型凭空回答。
- 企业风险、招标项目、法规条款来自不同数据源，需要先路由再检索。
- 法规问答要有知识库检索，结构化项目查询要有 SQL，企业风险要接外部工具。
- 所以核心不是“问模型”，而是“分类 - 检索 - 汇总 - 生成”。

当前项目对应文件：

```text
frontend1/
backend/
start_all.py
```

### Step 0.2: 设计前后端分离结构

从零设计时，先拆成两个主要部分：

```text
frontend1/          Vue3 前端
backend/            FastAPI 后端
backend/qa_engine/  问答引擎
```

前端职责：

- 展示聊天页面。
- 管理当前会话和历史会话。
- 把用户问题发给后端。
- 接收后端流式返回的文本，并实时渲染。

后端职责：

- 接收用户问题。
- 读取会话历史并做问题改写。
- 调用问答 pipeline。
- 保存用户消息和助手消息。
- 管理会话列表、标题、收藏、删除等。

为什么要前后端分离：

- 前端专注交互体验，后端专注 AI 和检索逻辑。
- AI 检索链路较重，不应该放在浏览器里。
- 后端可以统一保护 API Key、数据库密码、Milvus 地址等敏感配置。

当前项目对应：

```text
frontend1/src/
backend/qa_engine/
```

### Step 0.3: 搭建前端工程

当前前端是 Vue3 + TypeScript + Vite。

核心依赖：

```json
{
  "vue": "^3.5.0",
  "vue-router": "^4.2.5",
  "pinia": "^2.1.7",
  "marked": "^18.0.2",
  "vite": "^5.0.0",
  "typescript": "^5.9.3"
}
```

对应文件：

```text
frontend1/package.json
frontend1/vite.config.ts
frontend1/src/main.ts
frontend1/src/App.vue
```

为什么选这些：

- `Vue3`：适合做单页应用和组件化聊天界面。
- `TypeScript`：让消息、会话、API 返回结构更明确。
- `Vite`：开发启动快，配置轻。
- `Pinia`：统一管理会话状态。
- `vue-router`：支持 `/`、`/history`、`/settings`、`/session/:id` 页面。
- `marked`：后端回答通常是 Markdown，前端需要渲染格式化内容。

### Step 0.4: 配置前端代理

当前前端开发端口是 `3000`，后端端口是 `8000`。

对应文件：

```text
frontend1/vite.config.ts
```

关键配置：

```ts
server: {
  port: 3000,
  host: '0.0.0.0',
  proxy: {
    '/api': {
      target: 'http://localhost:8000',
      changeOrigin: true
    }
  }
}
```

这一步做了什么：

- 浏览器访问前端 `http://localhost:3000`。
- 前端请求 `/api/chat/stream`。
- Vite 自动把 `/api` 转发给 `http://localhost:8000`。

为什么要这样做：

- 前端代码里不需要写死后端地址。
- 开发时避免跨域问题。
- 后续部署时也可以通过反向代理统一路径。

### Step 0.5: 设计前端页面路由

当前路由：

```text
/             聊天页
/session/:id  指定会话聊天页
/history      历史记录页
/settings     设置页
```

对应文件：

```text
frontend1/src/router/index.ts
```

设计思路：

- 默认入口就是聊天，不做营销页。
- 历史记录和设置独立成页面。
- 会话详情通过 URL 中的 session id 识别，方便刷新和分享当前会话状态。

### Step 0.6: 设计前端组件结构

当前核心组件：

```text
frontend1/src/views/ChatView.vue
frontend1/src/components/ChatArea.vue
frontend1/src/components/MessageItem.vue
frontend1/src/components/Sidebar.vue
frontend1/src/components/ChatHeader.vue
frontend1/src/components/HistoryList.vue
frontend1/src/components/SettingsPanel.vue
```

组件职责：

- `ChatView.vue`：聊天页总控，连接会话状态、发送逻辑和页面组件。
- `ChatArea.vue`：输入框、消息列表、发送按钮、停止生成按钮。
- `MessageItem.vue`：单条消息渲染，支持 Markdown。
- `Sidebar.vue`：左侧会话列表、新建会话、切换会话。
- `ChatHeader.vue`：顶部标题、清空、收藏等操作。
- `HistoryList.vue`：历史记录展示。
- `SettingsPanel.vue`：设置、导入导出、主题等。

为什么这样拆：

- 输入、消息展示、会话管理是不同关注点。
- 聊天页逻辑集中在 `ChatView.vue`，组件只负责 UI 和事件。
- 后续改样式或改 API 时影响范围更小。

### Step 0.7: 设计前端会话状态

当前状态管理使用 Pinia。

对应文件：

```text
frontend1/src/stores/session.ts
```

核心状态：

```ts
sessions: Session[]
currentSessionId: string | null
_synced: boolean
```

这一步做了什么：

- 保存所有会话。
- 保存当前选中的会话。
- 判断是否已经和后端同步。
- 后端不可用时降级使用 `localStorage`。

为什么要这样设计：

- 聊天类应用最核心的数据是“会话列表 + 当前会话消息”。
- 前端需要立即显示用户输入，不能等后端保存成功后再显示。
- 本地缓存可以提高容错能力，后端连接失败时仍能保留页面状态。

当前实现细节：

- `loadFromStorage()` 优先调用后端 `/api/sessions`。
- 如果后端失败，则读取 `localStorage` 中的 `bid_sessions`。
- `createSession()` 优先调用后端创建会话，失败时用时间戳生成本地 id。
- `addMessage()` 会把消息加入当前会话并保存到本地。
- assistant 消息有内容时，会触发 `syncMessagesToBackend()` 同步到后端。

### Step 0.8: 编写聊天发送逻辑

当前发送入口：

```text
frontend1/src/components/ChatArea.vue
frontend1/src/views/ChatView.vue
frontend1/src/composables/useChat.ts
```

完整路径：

1. 用户在 `ChatArea.vue` 输入内容。
2. 点击发送按钮或按 Enter。
3. `ChatArea.vue` 触发 `send-message` 事件。
4. `ChatView.vue` 的 `handleSendMessage()` 接收内容。
5. `ChatView.vue` 先添加用户消息。
6. 再创建一条空的 assistant 消息。
7. 调用 `useChat.sendMessage()`。
8. 后端每返回一段文本，前端就更新 assistant 消息内容。

为什么要先创建空 assistant 消息：

- 流式回答不是一次性返回。
- 页面需要有一个位置持续追加模型输出。
- 用户能看到答案正在生成，而不是等待很久后一次性出现。

当前流式读取方式：

```ts
const reader = response.body!.getReader()
const decoder = new TextDecoder('utf-8')
```

每读到一个 chunk：

```ts
fullContent += chunk
onChunk?.(fullContent)
```

这里 `onChunk` 会回到 `ChatView.vue`，更新 assistant 消息。

### Step 0.9: 搭建后端 FastAPI 应用

当前后端入口：

```text
backend/run_api.py
backend/qa_engine/main_api_with_memory.py
```

启动方式：

```bash
cd backend
python run_api.py
```

`run_api.py` 做了两件事：

- 把项目根目录加入 `PYTHONPATH`。
- 用 uvicorn 启动 `backend.qa_engine.main_api_with_memory:app`。

FastAPI 应用定义在：

```text
backend/qa_engine/main_api_with_memory.py
```

核心配置：

- 应用名称：企业知识库智能问答系统 API（含记忆模块）。
- CORS 允许 `localhost:3000` 和 `localhost:5173`。
- 启动时尝试创建 Milvus 会话 collection。

为什么要有 `main_api_with_memory.py`：

- 原始问答 pipeline 在 `main.py`。
- API 层负责 HTTP 请求、会话、记忆、持久化。
- 这样可以不直接改 `main.py` 的核心 pipeline。

### Step 0.10: 设计 API 数据结构

当前请求模型：

```python
class ChatRequest(BaseModel):
    question: str
    session_id: Optional[str] = None
    cot: bool = True
    max_concurrent: int = 5
    stream: bool = False
    history: Optional[list] = None
```

字段含义：

- `question`：用户当前问题。
- `session_id`：当前会话 id。
- `history`：前端传来的历史消息，用于问题改写。
- `stream`：是否流式输出。
- `max_concurrent`：预留并发控制参数。
- `cot`：预留思维链/分类控制参数。

当前聊天接口：

```text
POST /api/chat
POST /api/chat/stream
```

会话接口：

```text
POST   /api/sessions
GET    /api/sessions
GET    /api/sessions/{session_id}
PUT    /api/sessions/{session_id}
DELETE /api/sessions/{session_id}
POST   /api/sessions/{session_id}/title
PUT    /api/sessions/{session_id}/messages
```

设计思路：

- `/api/chat/stream` 是前端主用接口。
- `/api/chat` 是非流式兼容接口。
- session 接口负责会话 CRUD，不和聊天生成逻辑混在一起。

### Step 0.11: 加入多轮对话记忆

当前记忆相关文件：

```text
backend/qa_engine/app/memory_history.py
backend/qa_engine/app/session_manager.py
```

记忆链路：

1. 前端在发送问题时，把当前问题之前的历史消息传给后端。
2. 后端 `_load_history()` 优先使用前端传来的 history。
3. 如果前端没有传 history，则从后端会话存储里读取。
4. `rewrite_question_with_history()` 根据历史把当前问题改写为独立问题。
5. 改写后的问题再进入分类和检索 pipeline。

例子：

```text
上一轮：招商蛇口房地产公司的全称是什么？
助手：招商局蛇口工业区控股股份有限公司。
当前问题：它有没有风险？
改写后：招商局蛇口工业区控股股份有限公司有没有经营风险或法律处罚记录？
```

为什么要改写：

- 用户多轮对话经常使用“它”“这个公司”“刚才那个项目”。
- 检索系统不能理解代词，必须先把代词替换成明确实体。
- 改写后的问题更适合分类、SQL、企业风险工具和法规检索。

当前实现方式：

- `format_history_for_rewrite()` 保留最近 10 轮完整对话。
- `save_messages()` 每到第 11、21、31 轮时，批量压缩前 10 轮为摘要。
- 摘要存在 Milvus 的 `summary` 字段里。
- Redis 用作会话元数据和消息缓存。
- Redis 不可用时，系统会降级走 Milvus 查询。

### Step 0.12: 搭建会话持久化

当前会话存储：

```text
backend/qa_engine/app/session_manager.py
backend/qa_engine/data_processing/create_conversations_collection.py
backend/qa_engine/app/redis_client.py
```

使用组件：

- Milvus：保存会话记录、消息 JSON、摘要、标题、收藏状态等。
- Redis：缓存会话元数据和近期消息。
- LLM：生成会话标题、压缩历史摘要。

为什么把会话存在 Milvus：

- 当前项目已经依赖 Milvus。
- 会话摘要后续可以向量化，支持跨会话召回或长期记忆扩展。
- 当前代码中 `summary_vector` 已经预留。

当前写入逻辑：

- 新建会话时写入 session_id、title、created_at。
- 每次保存消息时，替换旧记录并写入 messages_json。
- 消息过大时，会从最早消息开始裁剪，防止单条记录超过限制。
- 每 10 轮压缩一次旧历史。

### Step 0.13: 设计问答核心 Pipeline

当前核心文件：

```text
backend/qa_engine/main.py
```

核心函数：

```python
main()
main_stream()
retrieval()
response()
response_stream()
change_question()
```

核心链路：

```text
用户问题
  -> 历史改写
  -> 问题分类与拆分
  -> 按类别路由到不同检索器
  -> 汇总检索结果
  -> 构造最终回答 prompt
  -> LLM 生成答案
  -> 流式返回前端
  -> 保存会话消息
```

为什么这样设计：

- 招投标问题不是单一类型。
- 有些问题需要查数据库，有些需要查法规，有些需要查企业风险。
- 复杂问题可能拆成多个子问题，每个子问题走不同工具。
- 检索结果统一汇总后，再交给最终 LLM 生成自然语言答案。

### Step 0.14: 设计问题分类器

当前文件：

```text
backend/qa_engine/app/questions_classify.py
backend/qa_engine/app/prompt_templates.py
```

分类类别：

```text
A 信息检索：历史投标、中标、公司、产品、供应商等结构化数据
B 信息推荐：推荐产品、供应商等
C 实时招投标查询：明确要求最新、实时、联网的招投标信息
D 信息判断：企业风险、处罚、资质、信用等
E 其他或互联网检索
F 法律法规检索：法规、流程、制度、行为判断等
```

当前做法：

- 用 LLM 读取用户问题。
- 要求输出 JSON 数组。
- 每个元素包含 `question` 和 `category`。
- 如果输出格式错误，则重试。
- 如果仍失败，则降级为 `[[user_question, "E"]]`。

为什么要拆分问题：

用户问题可能是：

```text
帮我查一下 A 公司有没有失信记录，再看看招标投标法里对失信的规定，顺便推荐几家靠谱施工单位。
```

这个问题实际包含：

- 公司风险查询：D。
- 法规查询：F。
- 供应商推荐：B。

如果不拆分，单一路径很难回答完整。

### Step 0.15: 设计检索路由层

当前文件：

```text
backend/qa_engine/app/routers.py
```

路由函数：

```python
router_A()
router_B()
router_C()
router_D()
router_E()
router_F()
```

作用：

- `router_A`：自然语言转 SQL，查结构化数据库。
- `router_B`：在结构化检索结果基础上做推荐排序。
- `router_C`：调用剑鱼招标接口查实时招投标信息。
- `router_D`：调用企查查相关工具做企业风险报告。
- `router_E`：判断是否需要联网搜索，不需要则直接问模型。
- `router_F`：查法规知识库，走 BM25 + 向量 + rerank。

为什么要单独做 router：

- 每类问题的数据源不同。
- SQL、向量库、外部 API、MCP 工具调用方式都不同。
- 路由层把工具差异包起来，`main.py` 只关心“输入问题，得到检索文本”。

### Step 0.16: 实现结构化 SQL 查询

当前文件：

```text
backend/qa_engine/app/sql_retrieval_langchain.py
```

使用技术：

- MySQL。
- SQLAlchemy。
- LangChain `SQLDatabase`。
- LangChain `ChatOpenAI`。
- LCEL 链式调用。
- pandas 执行 SQL 并格式化成 Markdown 表格。

核心流程：

1. 从 `.env` 读取 MySQL 连接信息。
2. 用 SQLAlchemy 创建连接。
3. 用 `SQLDatabase` 获取表结构。
4. 把用户问题和表结构交给 SQL 模型。
5. 模型按“两阶段流程”生成 SQL：
   - 先分析字段。
   - 再生成 SQL。
6. `clean_sql_output()` 从模型输出里提取 SQL。
7. `execute_sql()` 执行 SQL。
8. 结果 DataFrame 转成 Markdown 表格。
9. 如果 SQL 执行失败，最多重试 3 次。

为什么要让模型先分析字段：

- 结构化数据表字段多，字段名可能是中文或业务字段。
- 直接生成 SQL 容易编造字段。
- 先让模型列出目标表、字段、查询条件，可以降低 SQL 错误率。

当前风险点：

- 目前 SQL 安全边界主要靠 prompt 和执行失败重试。
- 如果从零做生产级系统，需要加 SQL 白名单，只允许 `SELECT`。
- 需要限制表名、字段名、LIMIT、禁止 DDL/DML。

从零设计时建议加：

```text
SQLValidator
  - 只允许 SELECT
  - 禁止 INSERT / UPDATE / DELETE / DROP / ALTER
  - 校验表名在 include_tables 中
  - 自动补 LIMIT
  - 记录生成 SQL 和执行耗时
```

### Step 0.17: 实现供应商/产品推荐

当前文件：

```text
backend/qa_engine/app/routers.py
```

对应函数：

```python
router_B()
```

当前做法：

1. 先调用 `router_A()` 查结构化数据。
2. 通过 IP 获取用户所在地。
3. 把 SQL 查询结果交给 LLM。
4. 要求模型按价格、地点、风险数量排序。
5. 如果没有足够信息，则说明无法排序。

为什么推荐不直接写死规则：

- 数据表里可能有价格、地点、风险、产品、供应商等不同字段。
- 用户问题可能只要求价格，也可能要求距离或风险。
- 让 LLM 做结果整理可以快速适配不同查询结果。

当前不足：

- 距离排序目前依赖所在地文本，没有真正地理编码和距离计算。
- 风险排序依赖检索结果里是否已有风险数量。
- 生产级推荐应把价格、距离、风险做成结构化评分。

从零设计时可以扩展：

```text
RecommendationScorer
  - price_score
  - distance_score
  - risk_score
  - availability_score
  - final_score
```

### Step 0.18: 实现实时招标信息查询

当前文件：

```text
backend/qa_engine/app/routers.py
backend/qa_engine/app/jianyubiaoxun.py
```

对应函数：

```python
router_C()
```

当前做法：

1. 用 LLM 从用户问题中提取查询参数。
2. 参数包括日期、地区、信息类型、行业、采购单位类型、金额范围、匹配模式。
3. 调用 `JianYuAPI.search(**args)` 查询实时招投标信息。
4. 查询结果返回给最终回答生成阶段。

为什么需要参数提取：

用户会问：

```text
我要今年 3 月 3 号到 3 月 5 号北京水利工程 10 万到 100 万的招标信息。
```

外部 API 需要的是结构化参数：

```json
{
  "start_date": "2026-03-03",
  "end_date": "2026-03-05",
  "areas": ["北京"],
  "info_types": ["招标"],
  "industries": ["水利工程"],
  "amount_min": 100000,
  "amount_max": 1000000
}
```

当前不足：

- 参数解析失败时直接返回空结果。
- 日期依赖当前时间和 prompt 规则。
- 生产级系统应加参数 schema 校验和默认策略。

### Step 0.19: 实现企业风险查询

当前文件：

```text
backend/qa_engine/app/routers.py
backend/qa_engine/app/qcc_prompt_mcp.py
backend/qa_engine/app/qcc_mcp/
```

对应函数：

```python
router_D()
```

当前做法：

1. 调用 `qcc_riskcheck(user_question)`。
2. 获取企业基本信息、企业风险信息、企业经营信息。
3. 把三类结果交给 LLM。
4. 根据用户关注点生成报告。
5. 流式返回报告内容。

为什么 D 类可以短路主生成：

`main_stream()` 中有一段特殊逻辑：

```python
if len(cls_results) == 1 and cls_results[0][1] == 'D':
    async for r in router_D(user_question):
        yield r
    return
```

意思是：

- 如果用户只问企业风险，不需要再经过最终 `DEFAULT_ANSWER_PROMPT`。
- `router_D` 自己已经生成了完整风险报告。
- 这样可以减少一次 LLM 汇总调用，流式输出更快。

当前不足：

- 企业风险属于高风险业务结论。
- 目前系统会生成总结，但没有人工复核流程。
- 从零做生产级系统，应标注“仅供参考”，并对法律/财务/投标决策场景加人工复核。

### Step 0.20: 实现法规知识库检索

当前文件：

```text
backend/qa_engine/app/vector_bm25_milvus_retrieval.py
backend/qa_engine/data_processing/nodes2pkl.py
backend/qa_engine/data_processing/md2nodes.py
backend/qa_engine/data_processing/nodes2vector_m3_milvus.py
```

对应函数：

```python
router_F()
hyde_retrieval()
simple_milvus_query()
search_multiple_indices()
reranker()
```

法规检索目标：

- 回答法律法规、流程、评分标准、合规判断等问题。
- 尽量基于法规原文或实务资料片段。
- 不让模型完全凭常识回答。

当前知识库文件：

```text
backend/qa_engine/data_processing/中华人民共和国招标投标法律法规全书.md
backend/qa_engine/data_processing/招标投标法律解读与风险防范实务.md
backend/qa_engine/data_processing/*.pkl
backend/qa_engine/data_processing/*_bm25.pkl
```

从零处理流程：

1. 原始法规资料转 Markdown。
2. 清洗 Markdown。
3. 切成 TextNode。
4. 保存 pkl。
5. 构建 BM25 索引。
6. 生成 embedding。
7. 写入 Milvus collection。
8. 查询时做 BM25 + 向量 + HyDE + rerank。

### Step 0.21: 实现 BM25 关键词检索

当前文件：

```text
backend/qa_engine/data_processing/nodes2pkl.py
```

使用技术：

- `jieba`：中文分词。
- `rank_bm25.BM25Okapi`：关键词检索。
- `pickle`：保存索引、原文和 metadata。

构建流程：

1. 遍历所有 node。
2. 对 node.text 用 jieba 分词。
3. 用 `BM25Okapi(tokenized_corpus)` 建索引。
4. 保存：
   - bm25 对象。
   - corpus 原文。
   - metadata 来源。

检索流程：

1. 查询语句用 jieba 分词。
2. 调 `bm25.get_scores()` 得分。
3. 按分数排序。
4. 取 top_k。
5. 过滤 score 为 0 的片段。

为什么要 BM25：

- 法规问题中很多关键词非常关键，例如“投标保证金”“失信被执行人”“评标委员会”。
- 纯向量检索可能语义相近但漏掉精确术语。
- BM25 对精确词命中更稳定。

### Step 0.22: 实现向量检索

当前文件：

```text
backend/qa_engine/app/vector_bm25_milvus_retrieval.py
```

使用组件：

- BGE-M3 embedding HTTP 服务。
- Milvus 远端向量库。
- `AsyncMilvusClient`。

查询流程：

1. `get_embedding_api(text)` 调用 embedding 服务。
2. 得到 dense vector。
3. `simple_milvus_query()` 连接 Milvus。
4. 在 collection `laws_m3` 中 search。
5. 返回 text、source、score。
6. 过滤低于 similarity threshold 的结果。

为什么要向量检索：

- 用户问题和法规原文不一定用同样词。
- 向量检索可以匹配语义相近的内容。
- 例如用户问“评分标准能不能设置 AAA 加分”，法规里可能写的是“不得以不合理条件限制、排斥潜在投标人”。

当前不足：

- `simple_milvus_query()` 当前只返回命中 chunk，没有展开上下文窗口。
- 文件中有注释掉的 context window 版本，说明已经考虑过上下文扩展。
- 从零做时建议保留 chunk_index，并把命中 chunk 前后各 1 个片段一起取回。

### Step 0.23: 实现 HyDE 检索

当前文件：

```text
backend/qa_engine/app/vector_bm25_milvus_retrieval.py
```

对应函数：

```python
another_query()
hyde_retrieval()
```

HyDE 的意思：

```text
Hypothetical Document Embeddings
```

通俗讲：

- 用户问题可能很短，直接做 embedding 不稳定。
- 先让模型根据问题生成一段“可能包含答案的假答案”。
- 再用这个假答案去做向量检索。
- 假答案通常更像法规资料片段，所以更容易召回相关 chunk。

当前实现流程：

1. BM25 检索原问题。
2. LLM 生成 fake answer。
3. 用原问题做向量检索。
4. 用 fake answer 做向量检索。
5. 合并三路结果：
   - BM25 results。
   - query vector results。
   - fake answer vector results。
6. 用 SimHash 去重。
7. 返回候选片段。

为什么这样做：

- BM25 保障关键词命中。
- 原问题向量保障语义召回。
- fake answer 向量增强法规风格召回。
- 多路召回后再 rerank，整体准确率更高。

当前代码中有一个需要注意的点：

```python
unique_by_simhash = deduplication(all_docs, threshold==threshold)
```

这里从语义上看，应该传入 `threshold=threshold`，当前写法会把布尔值传给第二个参数。文档这里只记录 trace，不做代码改造；如果后续要提升检索质量，这一处应优先检查。

### Step 0.24: 实现 SimHash 去重

当前函数：

```python
deduplication()
```

为什么要去重：

- BM25、原问题向量、HyDE 向量可能召回同一段或高度相似段落。
- 不去重会浪费上下文窗口。
- 重复证据还会影响 rerank 和最终回答。

当前做法：

1. 对每个候选 doc 的 text 计算 SimHash。
2. 和已保留片段比较海明距离。
3. 距离小于等于阈值则认为重复。
4. 只保留第一条非重复结果。

这种方式适合：

- 文本重复、近重复。
- 同一法规条款在不同资料中重复出现。
- Markdown 转换后产生重复片段。

### Step 0.25: 实现 Rerank

当前文件：

```text
backend/qa_engine/app/vector_bm25_milvus_retrieval.py
```

对应函数：

```python
reranker()
```

当前做法：

1. 把候选片段中的 `text` 提取出来。
2. 请求 `BGE_RERANKER_URL/rerank`。
3. 请求体包含：

```json
{
  "query": "用户问题",
  "documents": ["候选片段1", "候选片段2"],
  "normalize": true
}
```

4. rerank 服务返回每个候选的相关性分数。
5. 过滤低于 `score_threshold` 的结果。
6. 默认最多保留 15 条。
7. 如果传入 `top_k`，再截断到 top_k。

当前法规检索里：

```python
vector_results = reranker(user_question, vector_results, score_threshold=0.7, top_k=8)
```

联网搜索里：

```python
rerank_web_results = reranker(user_question, choice_web_results, score_threshold=0.7, top_k=None)
```

为什么 rerank 很重要：

- 第一阶段召回追求“别漏掉”，候选数量会多。
- 第二阶段 rerank 追求“把最相关的放前面”。
- 很多 RAG 失败不是因为没召回，而是正确证据排在后面，没进入最终 prompt。

从零设计时推荐的标准流程：

```text
用户问题
  -> BM25 top 20
  -> 向量 top 15
  -> HyDE 向量 top 15
  -> 合并去重
  -> rerank
  -> score_threshold 过滤
  -> top_k 截断
  -> 拼接 evidence
```

推荐保留的调试字段：

```text
candidate_count
bm25_count
query_vector_count
hyde_vector_count
dedup_count
rerank_top_score
rerank_min_score
selected_count
```

如果目前没有 rerank 服务，替代思路：

1. 规则 rerank：
   - 标题命中加分。
   - 完整关键词命中加分。
   - 来源权威性加分。
   - chunk 长度过短或过长减分。

2. LLM rerank：
   - 把候选片段编号。
   - 让模型输出最相关的编号和理由。
   - 成本较高，适合候选较少时使用。

3. Cross Encoder 本地 rerank：
   - 本地部署文本匹配模型。
   - 输入 query + chunk。
   - 输出相关性分。

推荐分数融合：

```text
final_score = 0.2 * bm25_score + 0.3 * vector_score + 0.5 * rerank_score
```

当前项目使用的是 rerank 分数作为最终筛选依据。后续如果要更稳定，可以把 BM25、向量和 rerank 分数都保留，方便分析。

### Step 0.26: 实现联网搜索 RAG

当前文件：

```text
backend/qa_engine/app/web_search_async.py
backend/qa_engine/app/routers.py
```

对应路由：

```python
router_E()
```

当前做法：

1. 先让模型判断用户问题是否需要联网。
2. 如果需要联网，调用 `web_search_rag()`。
3. 对搜索结果网页抓取正文。
4. 切分网页正文。
5. 计算 query 和 chunk 的相似度。
6. 返回相关网页片段。
7. 再用 `reranker()` 对网页片段重排。
8. 拼成网络查询内容和来源。

为什么不是所有 E 类都联网：

- 联网搜索慢。
- 外部搜索不稳定。
- 有些普通问题模型本身可以回答。
- 所以先让模型判断是否需要搜索。

当前不足：

- 搜索来源可信度没有分级。
- 没有对网页发布时间做统一排序。
- 没有黑白名单站点策略。
- 对高风险问题，联网结果也应该只作为参考，不直接给最终判断。

### Step 0.27: 设计最终回答 Prompt

当前文件：

```text
backend/qa_engine/app/prompt_templates.py
```

核心模板：

```python
DEFAULT_ANSWER_PROMPT
```

输入：

- 用户原问题。
- 拆分后的子问题。
- 每个子问题的检索结果。

模板约束：

- 多子问题要整合回答。
- 不要输出 `router_X` 字样。
- A 类只输出重点结构化信息。
- B 类按推荐排序方式回答。
- C 类实时招标结果超过 5 条要简化。
- D 类风险问题需要报告或总结。
- E 类根据强相关联网片段回答。
- F 类法规问题要结合检索片段，不要随意回答。
- 如果所有子问题都没有检索到信息，则回复未检索到相关信息。
- 答案紧扣原问题，不要扩展未检索出的供应商或事实。

为什么最终还要一个统一 prompt：

- 各路由返回的是检索材料，不一定适合直接给用户看。
- 最终回答需要结构化、自然语言、面向用户。
- 多子问题需要综合，而不是简单拼接。

### Step 0.28: 实现流式生成

当前文件：

```text
backend/qa_engine/main.py
backend/qa_engine/main_api_with_memory.py
frontend1/src/composables/useChat.ts
```

后端生成：

- `response_stream()` 调用 LLM 的 stream。
- 每个 chunk 通过 `yield content` 返回。
- `main_stream()` 把 pipeline 的最终回答 chunk 继续 yield。
- FastAPI `StreamingResponse` 把 chunk 发给浏览器。

前端接收：

- `fetch('/api/chat/stream')`。
- `response.body.getReader()`。
- `TextDecoder('utf-8')` 解码。
- 每个 chunk 更新 assistant 消息。

为什么要流式：

- 检索和生成可能耗时。
- 用户可以更早看到输出。
- 企业风险报告、法规解释通常较长，不适合等待完整结果后再显示。

### Step 0.29: 实现停止生成

当前文件：

```text
frontend1/src/composables/useChat.ts
frontend1/src/components/ChatArea.vue
frontend1/src/views/ChatView.vue
```

当前做法：

- 前端创建 `AbortController`。
- 用户点击停止按钮。
- 调用 `abortController.abort()`。
- `sendMessage()` 捕获 `AbortError`。
- 返回当前已生成内容并追加“已停止生成”。

为什么只在前端停止：

- 浏览器可以立即中断 HTTP 请求。
- 用户体验上能马上停止页面继续更新。

当前不足：

- 后端是否立即取消正在运行的 LLM 或检索任务，取决于底层连接和服务。
- 从零做更完整的取消机制，应给每次生成分配 request id，并在后端维护取消状态。

### Step 0.30: 编写一键启动脚本

当前文件：

```text
start_all.py
```

做了什么：

- 启动后端：

```text
backend/run_api.py
```

- 启动前端：

```text
frontend1 npm run dev
```

- 捕获 Ctrl+C 后同时终止前后端进程。

为什么需要：

- 前后端分离项目本地启动要开两个进程。
- 对学习和演示来说，一键启动更方便。
- Windows 环境下 `shell=True` 用于启动 npm。

## 1. 当前项目总体架构

### 1.1 一句话说明

这是一个面向招投标场景的多源智能问答系统。它不是单纯聊天机器人，而是先判断问题类型，再调用 SQL、实时招标 API、企业风险工具、法规知识库、联网搜索等不同工具，最后基于检索结果生成答案。

### 1.2 技术栈

前端：

- Vue3
- TypeScript
- Vite
- Pinia
- Vue Router
- Marked

后端：

- FastAPI
- Uvicorn
- Pydantic
- OpenAI-compatible LLM SDK
- LangChain
- SQLAlchemy
- pandas
- MySQL
- Milvus
- Redis
- BM25
- jieba
- BGE-M3 embedding
- BGE reranker
- SimHash

外部数据/工具：

- 剑鱼招标接口。
- 企查查 MCP 工具。
- Web 搜索 RAG。
- 本地法规知识库。

### 1.3 主链路

```text
用户输入
  -> Vue 聊天页面
  -> /api/chat/stream
  -> 读取会话历史
  -> 问题改写
  -> 分类与拆分
  -> A/B/C/D/E/F 路由检索
  -> 汇总检索结果
  -> 最终回答 prompt
  -> LLM 流式生成
  -> 前端实时展示
  -> 保存会话
```

## 2. 当前实现 Trace

### Step 1: 前端聊天界面

核心文件：

```text
frontend1/src/views/ChatView.vue
frontend1/src/components/ChatArea.vue
frontend1/src/components/MessageItem.vue
```

实现内容：

- 显示欢迎页。
- 显示用户和 AI 消息。
- 输入框支持 Enter 发送、Shift+Enter 换行。
- 生成中显示 loading。
- 支持停止生成。
- 支持复制、重新生成、反馈。

### Step 2: 前端 API 封装

核心文件：

```text
frontend1/src/composables/useChat.ts
frontend1/src/composables/useSessionApi.ts
```

实现内容：

- `useChat()` 负责聊天请求。
- `useSessionApi()` 负责会话 CRUD。
- API base 为空字符串，依赖 Vite proxy 转发。

设计好处：

- 组件不直接写一堆 fetch。
- 聊天 API 和会话 API 分开。
- 后续后端路径变化时，集中修改 composable。

### Step 3: 后端 API 层

核心文件：

```text
backend/qa_engine/main_api_with_memory.py
```

实现内容：

- 创建 FastAPI app。
- 配置 CORS。
- 定义请求和响应模型。
- 提供聊天接口和会话接口。
- 启动时创建会话 collection。
- 聊天完成后保存消息。

### Step 4: 多轮记忆

核心文件：

```text
backend/qa_engine/app/memory_history.py
backend/qa_engine/app/session_manager.py
```

实现内容：

- 根据历史消息改写当前问题。
- 近 10 轮保留完整文本。
- 更早历史按 10 轮一批压缩摘要。
- 消息存 Milvus，近期消息和列表元数据缓存 Redis。

### Step 5: 问题分类

核心文件：

```text
backend/qa_engine/app/questions_classify.py
backend/qa_engine/app/prompt_templates.py
```

实现内容：

- 用 LLM 拆分用户问题。
- 输出 JSON 数组。
- 每个子问题标注 A-F 分类。
- 分类失败时降级到 E 类。

### Step 6: 检索路由

核心文件：

```text
backend/qa_engine/main.py
backend/qa_engine/app/routers.py
```

实现内容：

- `main_stream()` 负责分类、检索、生成。
- `retrieval()` 根据分类调用对应 router。
- `router_A` 到 `router_F` 封装不同数据源。

### Step 7: SQL 查询

核心文件：

```text
backend/qa_engine/app/sql_retrieval_langchain.py
```

实现内容：

- LLM 生成 SQL。
- SQL 执行失败后带错误信息重试。
- 查询结果转 Markdown 表格。
- 返回 SQL 和查询内容。

### Step 8: 法规 RAG

核心文件：

```text
backend/qa_engine/app/vector_bm25_milvus_retrieval.py
backend/qa_engine/data_processing/nodes2pkl.py
```

实现内容：

- BM25 关键词召回。
- BGE-M3 embedding。
- Milvus 向量召回。
- HyDE 生成假答案增强召回。
- SimHash 去重。
- BGE reranker 重排。

### Step 9: 最终回答生成

核心文件：

```text
backend/qa_engine/main.py
backend/qa_engine/app/prompt_templates.py
```

实现内容：

- 把所有子问题检索结果拼成 `retrieval_results`。
- 用 `DEFAULT_ANSWER_PROMPT` 约束回答。
- 调用 LLM 流式生成。
- 没有内容时返回兜底提示。

### Step 10: 会话保存

核心文件：

```text
backend/qa_engine/main_api_with_memory.py
backend/qa_engine/app/session_manager.py
```

实现内容：

- 生成前读取历史。
- 生成后保存用户原问题和完整回答。
- 会话标题可由前端或后端生成。
- 支持收藏、删除、更新标题。

## 3. Rerank 深入说明

### 3.1 当前 rerank 做法

当前 rerank 是真实实现，不只是思路。

代码：

```text
backend/qa_engine/app/vector_bm25_milvus_retrieval.py
```

函数：

```python
reranker(query, candidates, score_threshold=0.7, top_k=None)
```

输入：

- 用户问题 `query`。
- 候选片段 `candidates`。
- 分数阈值 `score_threshold`。
- 最终保留数量 `top_k`。

输出：

- 通过阈值的候选片段。
- 每条包含 index、text、source、score。

### 3.2 rerank 在系统中的位置

法规检索：

```text
BM25 + 向量 + HyDE
  -> 合并去重
  -> rerank
  -> top 8
  -> 最终回答
```

联网搜索：

```text
搜索结果网页
  -> 网页正文切片
  -> 相似度初筛
  -> rerank
  -> 最终回答
```

### 3.3 为什么不是只用向量分数

向量分数的问题：

- 更适合粗召回。
- 对细粒度法律条款不一定排序稳定。
- 可能把语义类似但不能回答问题的片段排前面。

rerank 的优势：

- 输入是 query 和 document pair。
- 更关注这段文本是否能直接回答问题。
- 适合从候选集中选最终 evidence。

### 3.4 从零设计一个更完整的 rerank 模块

如果要把 rerank 做成可维护模块，可以设计：

```python
class Reranker:
    def rerank(
        self,
        query: str,
        candidates: list[dict],
        top_k: int = 8,
        score_threshold: float = 0.7,
    ) -> list[dict]:
        ...
```

建议保留字段：

```json
{
  "text": "...",
  "source": "...",
  "bm25_score": 12.3,
  "vector_score": 0.78,
  "rerank_score": 0.91,
  "retrieval_path": "bm25|vector|hyde"
}
```

这样可以回答：

- 这条证据是 BM25 找到的，还是向量找到的？
- rerank 前排第几，rerank 后排第几？
- 正确证据有没有被召回，只是没排上来？

## 4. 当前没有完整实现但从零应考虑的部分

这一节不是改造要求，只是从零讲项目时必须说明的工程思路。

### 4.1 Trace 记录

当前项目有“开发 trace 文档”，但运行时还没有结构化 trace 对象。

如果从零做完整工程，建议每次问答记录：

```json
[
  {
    "step": "rewrite_question",
    "input": "它有没有风险？",
    "output": "招商局蛇口工业区控股股份有限公司有没有风险？",
    "status": "success",
    "duration_ms": 320
  },
  {
    "step": "classify",
    "output": [["...有没有风险？", "D"]],
    "status": "success",
    "duration_ms": 510
  },
  {
    "step": "retrieve",
    "router": "router_D",
    "status": "success",
    "duration_ms": 2400
  }
]
```

为什么需要运行时 trace：

- 排查问题时知道卡在哪一步。
- 面试或答辩时可以证明系统不是黑盒。
- 可以统计分类错误、检索为空、rerank 低分等问题。

建议新增模块：

```text
TraceRecorder
TraceStep
RetrievalTrace
GenerationTrace
```

### 4.2 Evidence 展示

当前最终回答里会包含来源文本，但前端没有独立 evidence 面板。

从零设计时可以返回：

```json
{
  "answer": "...",
  "evidence": [
    {
      "id": "ev-1",
      "source": "中华人民共和国招标投标法律法规全书",
      "text": "...",
      "score": 0.91
    }
  ]
}
```

好处：

- 用户能复核答案依据。
- 法规问题可以显示引用出处。
- 幻觉问题更容易被发现。

### 4.3 Grounding 检查

当前 prompt 要求“不要随意回答”，但没有单独的 grounding checker。

从零设计时建议：

```text
Answer
  -> 抽取关键结论
  -> 检查每个结论是否能被 evidence 支撑
  -> 无依据结论降级或删除
```

建议规则：

- 没有 evidence 时不能给确定性结论。
- 数字、公司名、项目名必须来自检索结果。
- 法律结论必须带出处。
- 高风险结论必须提示人工复核。

### 4.4 检索评测

当前项目有 model_evaluation 目录，包含 recall、predict、evaluator 相关脚本和结果。

从零完整做法：

1. 准备问题集。
2. 标注标准答案或标准 evidence。
3. 对每个问题运行检索。
4. 计算：
   - hit@1
   - recall@5
   - recall@10
   - MRR
   - no_evidence_rate
5. 比较不同检索策略：
   - BM25 only
   - vector only
   - BM25 + vector
   - BM25 + vector + HyDE
   - BM25 + vector + HyDE + rerank

为什么要做：

- 不能只靠主观感觉判断 RAG 好坏。
- rerank 是否有效，必须通过评测证明。
- 如果正确证据在 top 20 但不在 top 5，说明 rerank 有优化空间。
- 如果 top 20 都没有，说明是切片、embedding、query rewrite 或数据问题。

### 4.5 Agent 运行边界

当前项目不是开放式 Agent，而是固定 pipeline：

```text
rewrite -> classify -> retrieve -> generate
```

这有一个优点：

- 不会无限循环。
- 不会乱调用工具。
- 行为更可控。

如果从零升级成真正 Agent，需要加：

- 最大步骤数。
- 最大工具调用次数。
- 工具白名单。
- 参数校验。
- 连续失败熔断。
- 人工复核兜底。

示例：

```python
class AgentRuntimePolicy:
    max_steps = 8
    max_tool_calls = 10
    max_same_tool_calls = 2
    timeout_seconds = 60
```

### 4.6 高风险问题人工复核

招投标系统会遇到高风险问题：

- 这个评分标准合法吗？
- 这个供应商是否应该淘汰？
- 这个行为是否构成串标？
- 投标人是否可以免责？
- 这家公司是否适合作为供应商？

当前系统会给出基于检索的回答，但没有人工复核队列。

从零生产级设计：

- 法律责任、财务审计、投标承诺、合同责任类问题触发人工复核。
- 系统只整理证据和初步分析。
- 最终结论由人工确认。

返回示例：

```json
{
  "answer": "当前问题涉及法律责任判断，系统已整理相关依据，但不直接给出最终结论。建议人工复核。",
  "requires_human_review": true,
  "evidence": []
}
```

## 5. 如何向别人讲这个项目

可以按下面顺序讲：

1. 这是一个招投标领域问答系统，不是普通聊天机器人。
2. 前端用 Vue3 做聊天和会话管理。
3. 后端用 FastAPI 接收流式聊天请求。
4. 后端先根据历史改写问题，解决“它”“这个公司”等上下文指代。
5. 然后用 LLM 把问题拆成 A-F 类。
6. 不同类别走不同检索器：
   - A 走 SQL。
   - B 做推荐。
   - C 查实时招标。
   - D 查企业风险。
   - E 联网搜索或普通回答。
   - F 查法规知识库。
7. 法规知识库使用 BM25、Milvus 向量、HyDE、SimHash 去重和 rerank。
8. 检索结果进入统一回答 prompt。
9. LLM 流式生成答案。
10. 前端实时展示，并保存会话。

一句话总结：

```text
这个系统的核心是基于问题分类的多路 RAG：先把用户问题拆成子问题，再按类别调用 SQL、法规向量库、企业风险工具、实时招标接口或联网搜索，最后把检索证据整合成流式回答。
```

## 6. 后续从零完善优先级

这些不是当前任务要改代码，而是从零讲项目时可以说明的下一步工程路线。

优先级 1：运行时 trace

- 记录 rewrite、classify、retrieve、rerank、generate 每一步。
- 支持前端展示和后端排查。

优先级 2：Evidence 独立返回

- 不只把来源混在回答里。
- 单独返回 evidence 数组。
- 前端可展开查看来源。

优先级 3：SQL 安全校验

- 只允许 SELECT。
- 限制表名和字段。
- 自动补 LIMIT。
- 拒绝危险 SQL。

优先级 4：检索评测集

- 建立标准问题集。
- 统计 recall@k 和 MRR。
- 用数据判断 BM25、向量、HyDE、rerank 的效果。

优先级 5：Grounding 检查

- 检查回答是否有 evidence 支撑。
- 删除或降级无依据结论。

优先级 6：人工复核

- 对法律责任、财务、投标承诺等高风险问题进入人工复核。

## 7. 文件索引

前端：

```text
frontend1/package.json
frontend1/vite.config.ts
frontend1/src/router/index.ts
frontend1/src/views/ChatView.vue
frontend1/src/components/ChatArea.vue
frontend1/src/components/MessageItem.vue
frontend1/src/stores/session.ts
frontend1/src/composables/useChat.ts
frontend1/src/composables/useSessionApi.ts
```

后端 API：

```text
backend/run_api.py
backend/qa_engine/main_api_with_memory.py
backend/qa_engine/main.py
```

问答引擎：

```text
backend/qa_engine/app/questions_classify.py
backend/qa_engine/app/prompt_templates.py
backend/qa_engine/app/routers.py
backend/qa_engine/app/sql_retrieval_langchain.py
backend/qa_engine/app/vector_bm25_milvus_retrieval.py
backend/qa_engine/app/web_search_async.py
backend/qa_engine/app/memory_history.py
backend/qa_engine/app/session_manager.py
```

数据处理：

```text
backend/qa_engine/data_processing/clean_md.py
backend/qa_engine/data_processing/md2nodes.py
backend/qa_engine/data_processing/nodes2pkl.py
backend/qa_engine/data_processing/nodes2vector_m3_milvus.py
backend/qa_engine/data_processing/create_conversations_collection.py
```

评测：

```text
backend/qa_engine/app/model_evaluation/
```

启动：

```text
start_all.py
```
