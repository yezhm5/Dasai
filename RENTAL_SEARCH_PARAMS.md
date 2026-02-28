# 房源搜索工具 · 完整参数指南

适用于 `tools/rental_search_tool.py` 中的 `search_houses()`、`search_houses_from_dict()` 及 `RentalSearchTool.search()`。对应 API：`AgentGameFakeAppApi-main/fake_app_agent_tools.json`、`README.md`。

---

## 一、查询方式与路由规则

工具根据参数**自动选择**接口，优先级如下：

| 优先级 | 触发条件 | 调用接口 | 说明 |
|--------|----------|----------|------|
| 1 | 传入了 `community` | `GET /api/houses/by_community` | 按小区名查该小区下可租房源 |
| 2 | 传入了 `landmark` 或 `landmark_id` | `GET /api/houses/nearby` | 先解析地标再查附近房源（地标名会查地标接口取 id） |
| 3 | 其他情况 | `GET /api/houses/by_platform` | 多条件组合筛选（行政区、价格、户型、地铁等） |

**注意**：房源相关接口必须带 `X-User-ID`（通过 `user_id` 或环境变量 `X_USER_ID` 设置），否则 API 返回 400。

---

## 二、环境与配置参数

在**函数调用**时，可作为 `search_houses(base_url=..., user_id=..., ...)` 或 `RentalSearchTool(base_url=..., user_id=...)` 传入；不传则从环境变量读取。

| 参数 | 类型 | 说明 | 环境变量 | 默认 |
|------|------|------|----------|------|
| `base_url` | str | API 根地址 | `RENTAL_API_BASE_URL` | `http://localhost:8080` |
| `user_id` | str | 用户工号，房源接口必填 | `X_USER_ID` | 空，未设置时搜索会返回错误提示 |

---

## 三、搜索参数总表

### 3.1 路由相关（决定走哪种查询）

| 参数 | 类型 | 适用接口 | 说明 | 示例 |
|------|------|----------|------|------|
| `community` | str | by_community | 小区名，与数据一致 | `"建清园(南区)"`、`"保利锦上(二期)"` |
| `landmark` | str | nearby | 地标名称，工具会先查地标再 nearby | `"西二旗站"`、`"国贸"`、`"百度"` |
| `landmark_id` | str | nearby | 地标 ID，已知时可直接传，不再查名称 | `"SS_001"`、`"LM_002"` |

### 3.2 平台多条件（仅 by_platform）

| 参数 | 类型 | 说明 | 示例/取值 |
|------|------|------|-----------|
| `district` | str | 行政区，多区逗号分隔 | `"海淀"`、`"海淀,朝阳"` |
| `area` | str | 商圈，多商圈逗号分隔 | `"西二旗,上地"`、`"国贸"` |
| `min_price` | int | 最低月租金（元） | `2000` |
| `max_price` | int | 最高月租金（元） | `5000` |
| `bedrooms` | str | 卧室数，多选逗号分隔 | `"1"`、`"1,2"` |
| `rental_type` | str | 整租 或 合租 | `"整租"`、`"合租"` |
| `decoration` | str | 装修 | 精装、简装、豪华、毛坯、空房 |
| `orientation` | str | 朝向 | 朝南、朝北、朝东、朝西、南北、东西 |
| `elevator` | str | 是否有电梯 | `"true"`、`"false"` |
| `min_area` | int | 最小面积（㎡） | `50` |
| `max_area` | int | 最大面积（㎡） | `100` |
| `property_type` | str | 物业类型 | `"住宅"` |
| `subway_line` | str | 地铁线路 | `"13号线"` |
| `max_subway_dist` | int | 到最近地铁站最大距离（米），近地铁建议 800 | `800`、`1000` |
| `subway_station` | str | 地铁站名 | `"车公庄站"` |
| `utilities_type` | str | 水电类型 | `"民水民电"` |
| `available_from_before` | str | 可入住日期上限（含当日） | `"2026-03-10"`（YYYY-MM-DD） |
| `commute_to_xierqi_max` | int | 到西二旗通勤时间上限（分钟） | `45` |
| `sort_by` | str | 排序字段 | `"price"`、`"area"`、`"subway"` |
| `sort_order` | str | 排序方向 | `"asc"`、`"desc"` |

### 3.3 分页与挂牌平台（三种方式通用）

| 参数 | 类型 | 说明 | 默认 |
|------|------|------|------|
| `listing_platform` | str | 挂牌平台，不传则默认安居客 | 安居客 |
| `page` | int | 页码 | 1 |
| `page_size` | int | 每页条数，最大 10000 | 10 |

**挂牌平台取值**：`"链家"`、`"安居客"`、`"58同城"`。

### 3.4 地标附近专用（仅 nearby）

| 参数 | 类型 | 说明 | 默认 |
|------|------|------|------|
| `max_distance` | float | 地标为圆心的最大直线距离（米） | 2000 |

---

## 四、按查询方式汇总

### 按小区（by_community）

- **必填**：`community`
- **可选**：`listing_platform`、`page`、`page_size`

### 地标附近（nearby）

- **必填**：`landmark` 或 `landmark_id`（二选一）
- **可选**：`max_distance`、`listing_platform`、`page`、`page_size`

### 多条件平台筛选（by_platform）

- **可选**：除 `community`、`landmark`、`landmark_id`、`max_distance` 外的上表所有搜索与分页参数。

---

## 五、概念说明（与 README 一致）

- **近地铁**：指房源到**最近地铁站**的直线距离。`max_subway_dist=800` 即 800 米内，1000 米内可视为地铁可达。
- **地标附近**：以地标为圆心按**直线距离**筛选；返回中会带 `distance_to_landmark`、`walking_distance`、`walking_duration`（分钟）。
- **数据范围**：北京行政区；月租约 500–25000 元；到西二旗通勤约 8–95 分钟；地铁距离约 200–5500 米。

---

## 六、函数调用示例

```python
from tools.rental_search_tool import search_houses, search_houses_from_dict, get_tool

# 按小区
search_houses(community="建清园(南区)", page_size=5)

# 地标附近（自动解析「西二旗站」）
search_houses(landmark="西二旗站", max_distance=2000, user_id="your_uid")

# 多条件
search_houses(
    district="海淀",
    max_price=5000,
    bedrooms="1,2",
    rental_type="整租",
    max_subway_dist=800,
    commute_to_xierqi_max=45,
    page=1,
    page_size=10,
)

# 从字典调用（如 NLU 解析结果）
search_houses_from_dict({
    "district": "海淀,朝阳",
    "min_price": 2000,
    "max_price": 6000,
    "rental_type": "整租",
    "available_from_before": "2026-03-10",
}, user_id="your_uid")

# 复用工具实例
tool = get_tool(user_id="your_uid")
tool.search(area="西二旗", max_price=4500)
tool.search_from_dict({"community": "建清园(南区)"})
```

---

## 七、search_from_dict 允许的键

使用 `search_houses_from_dict(params)` 或 `tool.search_from_dict(params)` 时，`params` 中仅以下键会被识别（其余忽略）：

`community`, `landmark`, `landmark_id`, `district`, `area`, `min_price`, `max_price`, `bedrooms`, `rental_type`, `decoration`, `orientation`, `elevator`, `min_area`, `max_area`, `property_type`, `subway_line`, `max_subway_dist`, `subway_station`, `utilities_type`, `available_from_before`, `commute_to_xierqi_max`, `sort_by`, `sort_order`, `listing_platform`, `page`, `page_size`, `max_distance`

值需与上表类型一致；`None` 会被过滤掉。
