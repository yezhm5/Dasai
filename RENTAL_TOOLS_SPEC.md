# 租房工具参数说明（供大模型使用）

工具入口来自 `tools.rental_tools`，共三类：**landmarks**（地标）、**houses**（房源查询/初始化）、**house_action**（租房/退租/下架）。  
房源相关接口需传 `user_id`（用户工号）；可选传 `base_url` 覆盖 API 地址。

挂牌平台固定为：`链家`、`安居客`、`58同城`。

---

## 1. landmarks(operation, **kwargs)

地标类接口，**不需要** user_id。

### 参数总表

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| operation | string | 是 | 操作类型，见下表 |
| name | string | 依 operation | 地标名称（如「西二旗站」「百度」），by_name 时必填 |
| q | string | 依 operation | 搜索关键词，search 时必填 |
| landmark_id | string | 依 operation | 地标 ID（如 SS_001），by_id 时必填 |
| category | string | 否 | 地标类别：`subway`(地铁) / `company`(公司) / `landmark`(商圈等) |
| district | string | 否 | 行政区，如 海淀、朝阳 |
| base_url | string | 否 | API 根地址，默认从环境变量 RENTAL_API_BASE_URL 读取 |

### operation 取值与对应参数

| operation | 说明 | 必填参数 | 可选参数 |
|-----------|------|----------|----------|
| list | 获取地标列表 | 无 | category, district |
| by_name | 按名称精确查地标（用于后续 nearby 查房） | name | - |
| search | 关键词模糊搜索地标 | q | category, district |
| by_id | 按地标 ID 查详情 | landmark_id | - |
| stats | 地标统计（总数、按类别分布） | 无 | - |

### 调用示例

```python
landmarks("list", category="subway", district="海淀")
landmarks("by_name", name="西二旗站")
landmarks("search", q="国贸", category="landmark")
landmarks("by_id", landmark_id="SS_001")
landmarks("stats")
```

---

## 2. houses(operation, **kwargs)

房源查询与初始化，**需要** user_id（不传则用环境变量 X_USER_ID）。

### 参数总表

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| operation | string | 是 | 操作类型，见下表 |
| house_id | string | 依 operation | 房源 ID（如 HF_2001） |
| community | string | 依 operation | 小区名，如 建清园(南区)、保利锦上(二期) |
| landmark_id | string | 依 operation | 地标 ID 或地标名称（nearby 时必填） |
| listing_platform | string | 否 | 挂牌平台：`链家` / `安居客` / `58同城`，不传默认安居客 |
| page | int | 否 | 页码，默认 1 |
| page_size | int | 否 | 每页条数，默认 10，最大 10000 |
| max_distance | number | 否 | 地标附近房源最大直线距离（米），默认 2000 |
| max_distance_m | number | 否 | 小区周边地标最大距离（米），默认 3000 |
| type | string | 否 | 周边地标类型：`shopping`(商超) / `park`(公园) |
| district | string | 否 | 行政区，多区逗号分隔，如 海淀,朝阳 |
| area | string | 否 | 商圈，多商圈逗号分隔，如 西二旗,上地 |
| min_price | int | 否 | 最低月租金（元） |
| max_price | int | 否 | 最高月租金（元） |
| bedrooms | string | 否 | 卧室数，逗号分隔，如 1,2 |
| rental_type | string | 否 | 整租 或 合租 |
| decoration | string | 否 | 装修：精装/简装/豪华/毛坯/空房 |
| orientation | string | 否 | 朝向，如 朝南、南北 |
| elevator | string | 否 | 是否有电梯：true / false |
| min_area | int | 否 | 最小面积（㎡） |
| max_area | int | 否 | 最大面积（㎡） |
| property_type | string | 否 | 物业类型，如 住宅 |
| subway_line | string | 否 | 地铁线路，如 13号线 |
| max_subway_dist | int | 否 | 到最近地铁站最大距离（米），近地铁建议 800 |
| subway_station | string | 否 | 地铁站名，如 车公庄站 |
| utilities_type | string | 否 | 水电类型，如 民水民电 |
| available_from_before | string | 否 | 可入住日期上限，格式 YYYY-MM-DD（如 2026-03-10） |
| commute_to_xierqi_max | int | 否 | 到西二旗通勤时间上限（分钟） |
| sort_by | string | 否 | 排序字段：price / area / subway |
| sort_order | string | 否 | 排序方向：asc / desc |
| base_url | string | 否 | API 根地址 |
| user_id | string | 房源接口建议传 | 用户工号，房源相关必填 |

### operation 取值与对应参数

| operation | 说明 | 必填参数 | 可选参数 |
|-----------|------|----------|----------|
| init | 房源数据重置（新 session 建议先调） | 无 | user_id, base_url |
| get | 单套房源详情 | house_id | user_id, base_url |
| listings | 该房源在各平台挂牌记录 | house_id | user_id, base_url |
| by_community | 按小区查可租房源 | community | listing_platform, page, page_size, user_id, base_url |
| by_platform | 多条件筛选可租房源 | 无 | listing_platform, district, area, min_price, max_price, bedrooms, rental_type, decoration, orientation, elevator, min_area, max_area, property_type, subway_line, max_subway_dist, subway_station, utilities_type, available_from_before, commute_to_xierqi_max, sort_by, sort_order, page, page_size, user_id, base_url |
| nearby | 地标为圆心查附近可租房源 | landmark_id | max_distance, listing_platform, page, page_size, user_id, base_url |
| nearby_landmarks | 小区周边地标（商超/公园） | community | type, max_distance_m, user_id, base_url |
| stats | 房源统计（总数、状态/行政区/户型/价格分布） | 无 | user_id, base_url |

### 调用示例

```python
houses("init", user_id="工号")
houses("get", house_id="HF_2001", user_id="工号")
houses("listings", house_id="HF_2001", user_id="工号")
houses("by_community", community="建清园(南区)", user_id="工号")
houses("by_platform", district="海淀", max_price=5000, bedrooms="1", rental_type="整租", max_subway_dist=800, user_id="工号")
houses("nearby", landmark_id="西二旗站", max_distance=2000, user_id="工号")
houses("nearby_landmarks", community="建清园(南区)", type="shopping", user_id="工号")
houses("stats", user_id="工号")
```

---

## 3. house_action(operation, house_id, listing_platform, **kwargs)

房源操作：租房、退租、下架。**需要** user_id。

### 参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| operation | string | 是 | 操作：`rent`(租房) / `terminate`(退租) / `offline`(下架) |
| house_id | string | 是 | 房源 ID，如 HF_2001 |
| listing_platform | string | 是 | 挂牌平台：链家 / 安居客 / 58同城 |
| base_url | string | 否 | API 根地址 |
| user_id | string | 是 | 用户工号 |

### 调用示例

```python
house_action("rent", "HF_2001", "安居客", user_id="工号")
house_action("terminate", "HF_2001", "链家", user_id="工号")
house_action("offline", "HF_2001", "58同城", user_id="工号")
```

---

## 使用约定（供大模型推理时参考）

1. **user_id**：房源相关接口（houses 除地标外、house_action）必须带用户工号，否则 API 返回 400。
2. **新 session**：建议先调用 `houses("init", user_id=...)` 做房源数据重置。
3. **租房/退租/下架**：必须通过 `house_action` 调用接口才生效，仅对话中说「已租」无效。
4. **近地铁**：按到最近地铁站直线距离（米）筛选，`max_subway_dist=800` 表示 800 米内。
5. **地标附近房源**：先用 `landmarks("by_name", name="西二旗站")` 或 `landmarks("search", q="...")` 拿到地标信息，再用 `houses("nearby", landmark_id=...)`；landmark_id 也可直接传地标名称（如「西二旗站」）。
6. **指定小区**：用 `houses("by_community", community="小区名", ...)`。
7. **多条件筛选**：用 `houses("by_platform", ...)`，把能从用户意图中确定的参数都带上，不确定的不传。
