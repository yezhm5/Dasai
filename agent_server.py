#!/usr/bin/env python3
"""
租房 Agent 服务：可直接运行。
- 交互式 CLI：python agent_server.py
- 单次查询：python agent_server.py "海淀 5000以内 一居 整租 近地铁"
- HTTP 服务：python agent_server.py --serve [--port 8765]
"""
import json
import os
import re
import subprocess
import sys
import threading
import uuid
from http.server import HTTPServer, BaseHTTPRequestHandler

# 多轮对话：按 session_id 维护会话状态
SESSIONS = {}  # session_id -> {"history": [{"role":"user"|"assistant","content":"..."}], "conditions": {...}}
_sessions_lock = threading.Lock()
MAX_HISTORY_TURNS = 10  # 保留最近 N 轮，供大模型上下文

# ---------- 人工配置 ----------
X_USER_ID = "b00897290"                    # 用户工号，房源接口必填
RENTAL_API_BASE_URL = "http://localhost:8080"  # 租房 API 根地址
LLM_API_KEY = ""                         # 大模型 API Key，留空则用规则提取
LLM_BASE_URL = ""                         # 大模型 API 地址，留空则用 OpenAI 默认
LLM_MODEL = "qwen3"               # 模型名
MODEL_SERVICE_PORT = 8888                 # 请求里 model_ip 对应的模型服务端口（与 model_ip 拼成 base_url）
MODEL_SERVICE_PATH = "/v1"                 # 模型服务路径，常为 /v1（OpenAI 兼容）
# ------------------------------

# 大模型客户端（可选）
try:
    from openai import OpenAI
    _OPENAI_AVAILABLE = True
except ImportError:
    _OPENAI_AVAILABLE = False
    OpenAI = None

# 项目根目录
ROOT = os.path.dirname(os.path.abspath(__file__))
RENTAL_API = os.path.join(ROOT, "tools", "rental_api.py")


def _model_base_url_from_ip(model_ip: str):
    """由请求中的 model_ip（模型服务 IP）拼出模型 API 的 base_url。"""
    if not (model_ip or "").strip():
        return None
    ip = (model_ip or "").strip()
    if "://" in ip:
        return ip.rstrip("/")
    return f"http://{ip}:{MODEL_SERVICE_PORT}{MODEL_SERVICE_PATH}".rstrip("/")


def _llm_client(base_url_override=None):
    """返回大模型客户端。base_url_override 不为空时优先使用（如由请求中的 model_ip 拼出）。"""
    if not _OPENAI_AVAILABLE:
        return None
    if base_url_override:
        return OpenAI(api_key=LLM_API_KEY or "dummy", base_url=base_url_override)
    if not LLM_API_KEY and not LLM_BASE_URL:
        return None
    return OpenAI(api_key=LLM_API_KEY or "dummy", base_url=LLM_BASE_URL.rstrip("/") if LLM_BASE_URL else None)


def _has_llm(model_ip=None):
    """当前请求是否可用大模型（代码中配置了 LLM 或请求带了 model_ip）。"""
    if (model_ip or "").strip():
        return _OPENAI_AVAILABLE
    return _llm_client() is not None


EXTRACT_CONDITIONS_SCHEMA = """请从用户的租房需求中提取查询条件，只输出一个 JSON 对象，不要其他文字。
字段说明（没有的填 null）：
- district: 行政区，如 海淀、朝阳（仅北京）
- area: 商圈，如 西二旗、上地、国贸、望京
- min_price, max_price: 月租金范围（整数，单位元）
- bedrooms: 卧室数，字符串如 "1" 或 "1,2"
- rental_type: "整租" 或 "合租"
- max_subway_dist: 离地铁最大距离（米），近地铁填 800
- subway_station: 地铁站名，如 车公庄站
- commute_to_xierqi_max: 到西二旗通勤时间上限（整数，分钟）
- decoration: 装修，如 精装、简装
- orientation: 朝向，如 朝南、南北
- elevator: "true" 或 "false"
- min_area, max_area: 面积范围（整数，平米）
- community: 小区名（用户明确说查某小区时填）
- landmark_nearby: 用户说「xx附近」「xx边上」「靠近xx」时的地标名，如 西二旗站、国贸
示例：用户说「海淀 5000以内 一居 整租 近地铁」→ {"district":"海淀","max_price":5000,"bedrooms":"1","rental_type":"整租","max_subway_dist":800,"area":null,"min_price":null,"community":null,"landmark_nearby":null}
"""

EXTRACT_CONDITIONS_MULTI_TURN = """请根据以下多轮对话，提取用户当前的全部租房查询条件（后面的消息可能补充、修改或取消前面的需求）。
只输出一个 JSON 对象，不要其他文字。字段同单轮说明：district, area, min_price, max_price, bedrooms, rental_type, max_subway_dist, subway_station, commute_to_xierqi_max, decoration, orientation, elevator, min_area, max_area, community, landmark_nearby。没有的填 null。
"""

# 行政区（北京），用于正则整词匹配
DISTRICTS_RE = "海淀|朝阳|西城|东城|丰台|通州|昌平|大兴|房山|顺义|石景山"
# 常见商圈/地标（用于“某附近”）
LANDMARK_NAMES = "西二旗|上地|国贸|望京|中关村|五道口|西二旗站|车公庄站|国贸站"


def run_tool(*args, **env_add) -> dict:
    """调用 tools/rental_api.py，返回解析后的 JSON。配置来自代码开头 RENTAL_API_BASE_URL、X_USER_ID。"""
    cmd = [sys.executable, RENTAL_API]
    if RENTAL_API_BASE_URL:
        cmd.extend(["--base-url", RENTAL_API_BASE_URL])
    if X_USER_ID:
        cmd.extend(["--user-id", X_USER_ID])
    cmd.extend(list(args))
    env = os.environ.copy()
    env.update(env_add)
    try:
        out = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            cwd=ROOT,
            env=env,
        )
        if out.returncode != 0 and not out.stdout:
            return {"error": out.stderr or f"exit code {out.returncode}"}
        try:
            return json.loads(out.stdout) if out.stdout.strip() else {}
        except json.JSONDecodeError:
            return {"error": "工具返回非 JSON", "raw": out.stdout[:500]}
    except subprocess.TimeoutExpired:
        return {"error": "请求超时"}
    except FileNotFoundError:
        return {"error": f"未找到 {RENTAL_API}"}


def extract_conditions(text: str) -> dict:
    """从用户输入中提取查询条件。"""
    t = text.strip()
    conditions = {}

    # 行政区（整词匹配）
    for m in re.finditer(rf"({DISTRICTS_RE})", t):
        district = m.group(1)
        if "district" not in conditions:
            conditions["district"] = district
        else:
            conditions["district"] = ",".join(dict.fromkeys(conditions["district"].split(",") + [district]))
    if "district" in conditions and "," in conditions["district"]:
        conditions["district"] = ",".join(dict.fromkeys(conditions["district"].split(",")))

    # 商圈/地标（整词匹配）
    for m in re.finditer(rf"({LANDMARK_NAMES})", t):
        name = m.group(1)
        if "附近" in t or "边上" in t or "周边" in t:
            conditions["landmark_nearby"] = name if "站" in name else f"{name}"
        if "area" not in conditions and "landmark_nearby" not in conditions:
            conditions["area"] = name

    # 价格：5000以内、预算3000、2000-4000、不超过6000
    m = re.search(r"(?:预算|租金?|价格?)?\s*(\d+)\s*以内|不超过\s*(\d+)|(\d+)\s*元?(?:/月)?", t)
    if m:
        conditions["max_price"] = int(next(x for x in m.groups() if x))
    m = re.search(r"(\d+)\s*[-~到]\s*(\d+)\s*元?", t)
    if m:
        conditions["min_price"], conditions["max_price"] = int(m.group(1)), int(m.group(2))

    # 户型：一居/两居/三居、1室/2室、一室一厅（两→2）
    m = re.search(r"([一二两三])\s*居|(\d)\s*室|([一二两三])\s*室", t)
    if m:
        n = m.group(1) or m.group(3)
        if n:
            num_map = {"一": 1, "二": 2, "两": 2, "三": 3}
            n = num_map.get(n) or int(m.group(2))
            conditions["bedrooms"] = str(n)
        else:
            conditions["bedrooms"] = m.group(2)

    # 整租/合租
    if "整租" in t:
        conditions["rental_type"] = "整租"
    if "合租" in t:
        conditions["rental_type"] = "合租"

    # 近地铁
    if "近地铁" in t or "离地铁近" in t or "地铁附近" in t:
        conditions["max_subway_dist"] = 800

    # 西二旗通勤：西二旗 45 分钟、到西二旗 30 分钟内
    m = re.search(r"西二旗\s*(\d+)\s*分钟|到西二旗\s*(\d+)\s*分钟|通勤\s*(\d+)\s*分钟", t)
    if m:
        conditions["commute_to_xierqi_max"] = int(next(x for x in m.groups() if x))

    # 装修/朝向/电梯
    if "精装" in t:
        conditions["decoration"] = "精装"
    if "简装" in t:
        conditions["decoration"] = "简装"
    if "朝南" in t or "南向" in t:
        conditions["orientation"] = "朝南"
    if "有电梯" in t or "带电梯" in t:
        conditions["elevator"] = "true"
    if "无电梯" in t:
        conditions["elevator"] = "false"

    # 面积：50平、50-80平
    m = re.search(r"(\d+)\s*平(?:米)?\s*以内|不超过\s*(\d+)\s*平", t)
    if m:
        conditions["max_area"] = int(next(x for x in m.groups() if x))
    m = re.search(r"(\d+)\s*[-~到]\s*(\d+)\s*平", t)
    if m:
        conditions["min_area"], conditions["max_area"] = int(m.group(1)), int(m.group(2))

    # 小区名：小区 xxx、查 xxx 小区
    m = re.search(r"(?:小区|小区名)\s*[「\"']?([^」\"'\s]+)|([^\s]+)\s*小区", t)
    if m:
        conditions["community"] = (m.group(1) or m.group(2) or "").strip("「」\"'")

    return conditions


# 调用大模型时在请求头中传递的 session_id 的 header 名
SESSION_ID_HEADER = "X-Session-ID"


def extract_conditions_with_llm(text: str, history_for_llm=None, model_ip=None, session_id=None):
    """使用大模型从用户输入中提取查询条件。session_id 会放在模型请求的 headers 中（X-Session-ID）。"""
    base_url = _model_base_url_from_ip(model_ip) if model_ip else None
    client = _llm_client(base_url_override=base_url) if base_url else _llm_client()
    if not client:
        return None
    model = LLM_MODEL
    if history_for_llm:
        sys_prompt = EXTRACT_CONDITIONS_SCHEMA + "\n" + EXTRACT_CONDITIONS_MULTI_TURN
        conv = "\n".join(
            ("用户" if m["role"] == "user" else "助手") + "：" + (m.get("content") or "")
            for m in history_for_llm
        )
        user_content = (conv + "\n用户：" + (text or "无").strip()).strip()
    else:
        sys_prompt = EXTRACT_CONDITIONS_SCHEMA
        user_content = text.strip() or "无"
    extra_headers = {SESSION_ID_HEADER: session_id} if (session_id or "").strip() else {}
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user_content},
            ],
            temperature=0.1,
            extra_headers=extra_headers,
        )
        content = (resp.choices[0].message.content or "").strip()
        if "```" in content:
            for part in content.split("```"):
                part = part.strip()
                if part.startswith("json"):
                    part = part[4:].strip()
                if part.startswith("{"):
                    content = part
                    break
        data = json.loads(content)
        return _normalize_llm_conditions(data)
    except Exception:
        return None


def _merge_conditions(previous: dict, new: dict) -> dict:
    """合并多轮条件：新消息提取的条件覆盖或补充前一轮。"""
    if not new:
        return dict(previous) if previous else {}
    merged = dict(previous or {})
    for k, v in new.items():
        if v is None or (isinstance(v, str) and v.strip() == ""):
            continue
        merged[k] = v
    return merged


def _normalize_llm_conditions(raw: dict) -> dict:
    """将大模型返回的 JSON 规范为 build_and_run_query 可用的字段与类型。"""
    allowed = {
        "district", "area", "min_price", "max_price", "bedrooms", "rental_type",
        "max_subway_dist", "subway_station", "commute_to_xierqi_max",
        "decoration", "orientation", "elevator", "min_area", "max_area",
        "community", "landmark_nearby",
    }
    conditions = {}
    for k, v in (raw or {}).items():
        if k not in allowed or v is None or v == "" or (isinstance(v, str) and v.strip() == ""):
            continue
        if k in ("min_price", "max_price", "max_subway_dist", "commute_to_xierqi_max", "min_area", "max_area"):
            try:
                conditions[k] = int(float(v)) if v is not None else None
            except (TypeError, ValueError):
                continue
        elif k == "bedrooms" and v is not None:
            conditions[k] = str(int(v)) if isinstance(v, (int, float)) else str(v).strip()
        else:
            conditions[k] = str(v).strip() if isinstance(v, str) else v
    return conditions


def build_and_run_query(conditions: dict) -> dict:
    """根据条件选择接口并执行，返回 API 结果。"""
    # 1) 指定小区
    if conditions.get("community"):
        return run_tool("by-community", conditions["community"], "--page_size", "20")

    # 2) 地标附近（用户说 xx 附近、xx 边上）
    landmark = conditions.get("landmark_nearby")
    if landmark:
        # 先查地标名（补“站”尝试）
        name = landmark if "站" in landmark else f"{landmark}站"
        lm_res = run_tool("landmark-by-name", name)
        if lm_res.get("error"):
            lm_res = run_tool("landmark-by-name", landmark)
        if lm_res.get("error"):
            return run_tool("search-landmarks", landmark)
        lid = (lm_res.get("data") or lm_res) if isinstance(lm_res.get("data"), dict) else lm_res
        lid = lid.get("id") or (lm_res.get("data", {}).get("id") if isinstance(lm_res.get("data"), dict) else None)
        if not lid and isinstance(lm_res.get("data"), list) and lm_res["data"]:
            lid = lm_res["data"][0].get("id")
        if not lid:
            lid = name  # 接口支持按名称查
        return run_tool("nearby", lid, "--max_distance", "2000", "--page_size", "20")

    # 3) 多条件：by-platform
    args = ["by-platform", "--page_size", "20"]
    if conditions.get("district"):
        args.extend(["--district", conditions["district"]])
    if conditions.get("area") and not conditions.get("landmark_nearby"):
        args.extend(["--area", conditions["area"]])
    if conditions.get("min_price") is not None:
        args.extend(["--min_price", str(conditions["min_price"])])
    if conditions.get("max_price") is not None:
        args.extend(["--max_price", str(conditions["max_price"])])
    if conditions.get("bedrooms"):
        args.extend(["--bedrooms", conditions["bedrooms"]])
    if conditions.get("rental_type"):
        args.extend(["--rental_type", conditions["rental_type"]])
    if conditions.get("max_subway_dist"):
        args.extend(["--max_subway_dist", str(conditions["max_subway_dist"])])
    if conditions.get("subway_station"):
        args.extend(["--subway_station", conditions["subway_station"]])
    if conditions.get("commute_to_xierqi_max") is not None:
        args.extend(["--commute_to_xierqi_max", str(conditions["commute_to_xierqi_max"])])
    if conditions.get("decoration"):
        args.extend(["--decoration", conditions["decoration"]])
    if conditions.get("orientation"):
        args.extend(["--orientation", conditions["orientation"]])
    if conditions.get("elevator"):
        args.extend(["--elevator", conditions["elevator"]])
    if conditions.get("min_area") is not None:
        args.extend(["--min_area", str(conditions["min_area"])])
    if conditions.get("max_area") is not None:
        args.extend(["--max_area", str(conditions["max_area"])])

    return run_tool(*args)


def format_reply(result: dict, conditions: dict) -> str:
    """将 API 结果格式化为可读回复。"""
    if result.get("error"):
        return f"查询出错：{result['error']}"

    data = result.get("data")
    if data is None:
        data = result

    # 列表类：data 为 list 或 data.items
    items = None
    total = 0
    if isinstance(data, list):
        items = data
        total = len(data)
    elif isinstance(data, dict):
        items = data.get("items") or data.get("list")
        total = data.get("total", len(items) if items else 0)

    if items:
        lines = [f"根据您的条件共找到 {total} 套房源："]
        for i, h in enumerate(items[:10], 1):
            if isinstance(h, dict):
                addr = h.get("address") or h.get("community") or h.get("title") or ""
                price = h.get("rent") or h.get("price") or h.get("monthly_rent") or ""
                layout = h.get("layout") or h.get("rooms") or h.get("bedrooms") or ""
                hid = h.get("house_id") or h.get("id") or ""
                lines.append(f"{i}. {addr} | {layout} | {price}元/月 | 房源ID: {hid}")
            else:
                lines.append(f"{i}. {h}")
        if total > 10:
            lines.append(f"… 仅展示前 10 条，共 {total} 条。可补充条件或指定小区/地标缩小范围。")
        return "\n".join(lines)

    # 单条（详情等）
    if isinstance(data, dict):
        addr = data.get("address") or data.get("community") or ""
        price = data.get("rent") or data.get("price") or ""
        return f"房源：{addr}，月租 {price} 元。"
    return json.dumps(data, ensure_ascii=False, indent=2)


def agent_reply(user_text: str) -> str:
    """Agent 主逻辑：提取条件 → 调用接口 → 格式化回复。"""
    text = (user_text or "").strip()
    if not text:
        return "请描述您的租房需求，例如：区域、预算、户型、整租/合租、是否近地铁、到西二旗通勤时间等。"

    # 重置 / 初始化
    if "重置" in text or "初始化" in text or "init" in text.lower():
        r = run_tool("house-init")
        if r.get("error"):
            return f"重置失败：{r['error']}"
        return "房源数据已重置。"

    # 租房/退租/下架（简单匹配：租 HF_xxx、退租 HF_xxx）
    m = re.search(r"(?:租|租赁)\s*([A-Z]+_\d+)", text)
    if m and ("租" in text and "退" not in text):
        house_id = m.group(1)
        platform = "安居客"
        if "链家" in text:
            platform = "链家"
        elif "58" in text or "58同城" in text:
            platform = "58同城"
        r = run_tool("rent", house_id, platform)
        if r.get("error"):
            return f"租房操作失败：{r['error']}"
        return f"已为您办理租房，房源 {house_id}（{platform}）。"

    m = re.search(r"退租\s*([A-Z]+_\d+)", text)
    if m:
        house_id = m.group(1)
        platform = "安居客"
        if "链家" in text:
            platform = "链家"
        elif "58" in text:
            platform = "58同城"
        r = run_tool("terminate", house_id, platform)
        if r.get("error"):
            return f"退租失败：{r['error']}"
        return f"已退租房源 {house_id}（{platform}）。"

    # 查房源详情：HF_xxx、房源 xxx
    m = re.search(r"(?:房源|房子)\s*([A-Z]+_\d+)|([A-Z]+_\d+)", text)
    if m and ("详情" in text or "介绍" in text or "看看" in text or len(text) < 30):
        house_id = (m.group(1) or m.group(2)).strip()
        r = run_tool("house", house_id)
        if r.get("error"):
            return f"查询失败：{r['error']}"
        return format_reply(r, {})

    # 条件查询：优先使用大模型解析，未配置或失败时用规则提取
    conditions = extract_conditions_with_llm(text) if _llm_client() else None
    if not conditions:
        conditions = extract_conditions(text)
    if not conditions:
        return "未识别到具体条件，请说明区域、预算、户型（如：海淀 5000以内 一居 整租 近地铁）。"

    result = build_and_run_query(conditions)
    return format_reply(result, conditions)


def _is_special_intent(text: str) -> str:
    """判断是否为重置/租房/退租/详情等单轮意图，返回意图名或空。"""
    t = (text or "").strip()
    if "重置" in t or "初始化" in t or "init" in t.lower():
        return "reset"
    if re.search(r"(?:租|租赁)\s*([A-Z]+_\d+)", t) and "退" not in t:
        return "rent"
    if re.search(r"退租\s*([A-Z]+_\d+)", t):
        return "terminate"
    if re.search(r"(?:房源|房子)\s*([A-Z]+_\d+)|([A-Z]+_\d+)", t) and ("详情" in t or "介绍" in t or "看看" in t or len(t) < 30):
        return "detail"
    return ""


def agent_reply_with_session(session_id: str, message: str, model_ip: str = ""):
    """多轮对话：按 session 合并历史条件，逐步完善需求。model_ip 为请求中的模型服务 IP，用于调用大模型。返回 (reply, session_id)。"""
    if not (session_id or "").strip():
        session_id = uuid.uuid4().hex
    with _sessions_lock:
        session = SESSIONS.get(session_id, {"history": [], "conditions": {}})
        session = {"history": list(session.get("history", [])), "conditions": dict(session.get("conditions", {}))}

    intent = _is_special_intent(message)
    if intent == "reset":
        with _sessions_lock:
            SESSIONS[session_id] = {"history": [], "conditions": {}}
        r = run_tool("house-init")
        reply = "房源数据已重置。" if not r.get("error") else f"重置失败：{r['error']}"
        _append_session_history(session_id, message, reply)
        return reply, session_id
    if intent in ("rent", "terminate", "detail"):
        reply = agent_reply(message)
        _append_session_history(session_id, message, reply)
        return reply, session_id

    # 条件查询：合并本轮与历史条件（model_ip 为模型服务 IP，用于大模型 base_url）
    prev_conditions = session.get("conditions") or {}
    history = session.get("history") or []
    if _has_llm(model_ip) and history:
        new_conditions = extract_conditions_with_llm(
            message,
            history_for_llm=history[-MAX_HISTORY_TURNS * 2 :],
            model_ip=model_ip,
            session_id=session_id,
        )
    else:
        new_conditions = (
            extract_conditions_with_llm(message, model_ip=model_ip, session_id=session_id)
            if _has_llm(model_ip)
            else None
        )
    if not new_conditions:
        new_conditions = extract_conditions(message)
    conditions = _merge_conditions(prev_conditions, new_conditions)

    if not conditions:
        reply = "未识别到具体条件，您可以分多轮说，例如先讲「海淀」，再说「5000以内」「一居」「整租」「近地铁」。"
        _append_session_history(session_id, message, reply)
        return reply, session_id

    result = build_and_run_query(conditions)
    reply = format_reply(result, conditions)
    with _sessions_lock:
        s = SESSIONS.get(session_id, {"history": [], "conditions": {}})
        s["conditions"] = conditions
        SESSIONS[session_id] = s
    _append_session_history(session_id, message, reply)
    return reply, session_id


def _append_session_history(session_id: str, user_msg: str, assistant_msg: str):
    with _sessions_lock:
        s = SESSIONS.get(session_id, {"history": [], "conditions": {}})
        s["history"] = s.get("history", []) + [
            {"role": "user", "content": user_msg},
            {"role": "assistant", "content": assistant_msg},
        ]
        s["history"] = s["history"][-(MAX_HISTORY_TURNS * 2) :]
        SESSIONS[session_id] = s


class ChatHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/" or self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok", "service": "rental-agent"}).encode("utf-8"))
            return
        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        if self.path != "/api/v1/chat":
            self.send_response(404)
            self.end_headers()
            return
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8", errors="replace") if length else "{}"
        try:
            data = json.loads(body) if body.strip() else {}
        except json.JSONDecodeError:
            data = {}
        # 接口格式：{"model_ip": "xxx", "session_id": "xxx", "message": "xxx"}；model_ip 为模型服务 IP，多轮对话请传同一 session_id
        message = data.get("message") or data.get("text") or ""
        model_ip = (data.get("model_ip") or "").strip()
        session_id = (data.get("session_id") or "").strip()
        reply, session_id = agent_reply_with_session(session_id, message, model_ip=model_ip)
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps({"reply": reply, "session_id": session_id}, ensure_ascii=False).encode("utf-8"))


def main():
    import argparse
    p = argparse.ArgumentParser(description="租房 Agent 服务")
    p.add_argument("--serve", action="store_true", help="启动 HTTP 服务")
    p.add_argument("--port", type=int, default=8765, help="HTTP 端口，默认 8765")
    p.add_argument("message", nargs="*", help="直接输入一句查询（不传则进入交互）")
    args = p.parse_args()

    if not X_USER_ID or X_USER_ID == "你的工号":
        print("请在 agent_server.py 代码开头配置 X_USER_ID（用户工号），房源接口需要。", file=sys.stderr)
        if not args.serve:
            sys.exit(1)

    if args.serve:
        server = HTTPServer(("", args.port), ChatHandler)
        print(f"租房 Agent HTTP 服务已启动: http://0.0.0.0:{args.port}")
        print("  POST /api/v1/chat  Body: {\"model_ip\": \"xxx\", \"session_id\": \"xxx\", \"message\": \"您的需求\"}")
        print("  GET  /health 健康检查")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\n已停止")
        return

    if args.message:
        text = " ".join(args.message)
        print(agent_reply(text))
        return

    # 交互式
    print("租房 Agent（输入需求查询房源，输入 q 或 exit 退出）")
    print("示例：海淀 5000以内 一居 整租 近地铁\n")
    while True:
        try:
            line = input("您> ").strip()
        except EOFError:
            break
        if not line:
            continue
        if line.lower() in ("q", "quit", "exit"):
            break
        print("Agent>", agent_reply(line), "\n")


if __name__ == "__main__":
    main()
