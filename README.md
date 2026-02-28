# 租房 Agent 服务

基于用户输入自动提取条件并调用租房 API 筛选房源的 Agent，可直接运行。

## 环境要求

- Python 3.7+
- **使用大模型解析用户输入**（推荐）：安装 `openai>=1.0.0`（`pip install -r requirements.txt`），并在代码开头配置 `LLM_API_KEY`；留空则用规则提取。

## 配置（代码开头人工配置）

在 **`agent_server.py`** 文件开头修改：

| 变量 | 必填 | 说明 |
|------|------|------|
| `X_USER_ID` | 是 | 用户工号，房源接口必填（与租房仿真平台一致） |
| `RENTAL_API_BASE_URL` | 否 | 租房 API 根地址，默认 `http://localhost:8080` |
| `LLM_API_KEY` | 否 | 大模型 API Key，留空则用规则提取 |
| `LLM_BASE_URL` | 否 | 大模型 API 地址（如 Azure、本地），留空则用 OpenAI 默认 |
| `LLM_MODEL` | 否 | 模型名，默认 `gpt-3.5-turbo` |
| `MODEL_SERVICE_PORT` | 否 | 请求里 **model_ip** 对应的模型服务端口，与 model_ip 拼成 `http://{model_ip}:{port}{path}`，默认 8000 |
| `MODEL_SERVICE_PATH` | 否 | 模型服务路径，默认 `/v1` |

单独运行 **`tools/rental_api.py`** 时，需在该文件开头配置 `BASE_URL`、`X_USER_ID`。

## 运行方式

### 1. 交互式命令行

```bash
# 先修改 agent_server.py 开头的 X_USER_ID、RENTAL_API_BASE_URL
python agent_server.py
```

输入自然语言需求，例如：`海淀 5000以内 一居 整租 近地铁`，Agent 会提取条件并返回房源列表。输入 `q` 或 `exit` 退出。

### 2. 单次查询

```bash
python agent_server.py "海淀 5000以内 一居 整租 近地铁"
```

### 3. HTTP 服务

```bash
python agent_server.py --serve --port 8765
```

- **POST /api/v1/chat**：请求体 `{"model_ip": "xxx", "session_id": "xxx", "message": "您的租房需求"}`，返回 `{"reply": "...", "session_id": "xxx"}`。**model_ip** 为模型服务 IP。**session_id** 会放在调用大模型时的请求头中（默认 `X-Session-ID`），便于模型侧识别会话。多轮对话请传同一 `session_id`，首轮可不传（服务端会生成并返回）。
- **GET /health**：健康检查，返回 `{"status": "ok", "service": "rental-agent"}`。

示例（多轮）：

```bash
# 第一轮：不传 session_id，返回的 session_id 用于后续
curl -X POST http://localhost:8765/api/v1/chat -H "Content-Type: application/json" \
  -d '{"model_ip": "xxx", "message": "我想在海淀租"}'

# 第二轮：带上上一步返回的 session_id，补充预算和户型
curl -X POST http://localhost:8765/api/v1/chat -H "Content-Type: application/json" \
  -d '{"model_ip": "xxx", "session_id": "<上一步返回的 session_id>", "message": "5000以内 一居 整租 近地铁"}'
```

## 支持的需求表达

Agent 会从输入中识别：

- **区域**：海淀、朝阳、西城、通州等
- **价格**：5000以内、预算3000、2000-4000
- **户型**：一居、两居、1室、2室
- **整租/合租**
- **近地铁**（按 800 米内筛选）
- **西二旗通勤**：如「西二旗 45 分钟」
- **装修/朝向/电梯**：精装、朝南、有电梯
- **小区名**：查指定小区
- **地标附近**：如「西二旗站附近」「国贸附近」

特殊指令：

- 说「重置」或「初始化」会调用房源数据重置接口。
- 说「租 HF_2001」可触发租房操作（需指定房源 ID 与平台）。

## 项目结构

- `agent_server.py`：Agent 服务入口（CLI + HTTP）
- `tools/rental_api.py`：租房 API 命令行封装
- `AGENTS.md`：Agent 行为与工具说明（供 Cursor 等使用）
- `AgentGameFakeAppApi-main/`：租房接口文档与 OpenAPI 定义
