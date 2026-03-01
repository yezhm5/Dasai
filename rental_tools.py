#!/usr/bin/env python3
"""
租房 API 函数式工具组。覆盖 fake_app_agent_tools.json 与 README 中全部接口，
可通过函数直接调用，供 Agent/服务端使用。房源相关接口需提供 user_id。

合并为三类入口：
- landmarks(operation, **kwargs)  地标：list | by_name | search | by_id | stats
- houses(operation, **kwargs)    房源：init | get | listings | by_community | by_platform | nearby | nearby_landmarks | stats
- house_action(operation, house_id, listing_platform, **kwargs)  操作：rent | terminate | offline
"""
from __future__ import annotations

import json
import os
from typing import Any, Optional
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

# 默认从环境变量读取，函数参数可覆盖
DEFAULT_BASE_URL = os.environ.get("RENTAL_API_BASE_URL", "http://localhost:8080")
DEFAULT_USER_ID = os.environ.get("X_USER_ID", "")

LISTING_PLATFORMS = ("链家", "安居客", "58同城")


def _get_config(
    base_url: Optional[str] = None,
    user_id: Optional[str] = None,
) -> tuple[str, str]:
    base = (base_url or DEFAULT_BASE_URL).rstrip("/")
    uid = user_id if user_id is not None else DEFAULT_USER_ID
    return base, uid


def _request(
    method: str,
    path: str,
    params: Optional[dict[str, Any]] = None,
    data: Optional[dict] = None,
    need_user_id: bool = False,
    base_url: Optional[str] = None,
    user_id: Optional[str] = None,
) -> dict:
    base, uid = _get_config(base_url, user_id)
    url = f"{base}{path}"
    if params:
        url += "?" + urlencode({k: v for k, v in params.items() if v is not None})
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if need_user_id and uid:
        headers["X-User-ID"] = uid
    req = Request(
        url,
        data=json.dumps(data).encode() if data else None,
        headers=headers,
        method=method,
    )
    try:
        with urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode())
    except HTTPError as e:
        body = e.read().decode() if e.fp else ""
        return {"error": f"HTTP {e.code}", "body": body}
    except URLError as e:
        return {"error": str(e.reason)}
    except json.JSONDecodeError as e:
        return {"error": f"JSON decode: {e}"}


# ---------- 合并入口：地标 landmarks(operation, **kwargs) ----------


def landmarks(
    operation: str,
    *,
    name: Optional[str] = None,
    q: Optional[str] = None,
    landmark_id: Optional[str] = None,
    category: Optional[str] = None,
    district: Optional[str] = None,
    base_url: Optional[str] = None,
    **kwargs: Any,
) -> dict:
    """
    地标统一入口。operation 取值：
    - list: 获取地标列表，可选 category(subway/company/landmark)、district
    - by_name: 按名称精确查询，必填 name
    - search: 关键词模糊搜索，必填 q，可选 category、district
    - by_id: 按 id 查详情，必填 landmark_id
    - stats: 地标统计
    """
    op = operation.strip().lower()
    if op == "list":
        params = {}
        if category is not None:
            params["category"] = category
        if district is not None:
            params["district"] = district
        return _request("GET", "/api/landmarks", params=params or None, need_user_id=False, base_url=base_url)
    if op == "by_name":
        n = name or kwargs.get("name")
        if not n:
            return {"error": "请提供地标名称 name"}
        return _request("GET", f"/api/landmarks/name/{n}", need_user_id=False, base_url=base_url)
    if op == "search":
        keyword = q or kwargs.get("q")
        if not keyword:
            return {"error": "请提供搜索关键词 q"}
        params: dict[str, Any] = {"q": keyword}
        if category is not None:
            params["category"] = category
        if district is not None:
            params["district"] = district
        return _request("GET", "/api/landmarks/search", params=params, need_user_id=False, base_url=base_url)
    if op == "by_id":
        lid = landmark_id or kwargs.get("landmark_id") or kwargs.get("id")
        if not lid:
            return {"error": "请提供地标 ID landmark_id"}
        return _request("GET", f"/api/landmarks/{lid}", need_user_id=False, base_url=base_url)
    if op == "stats":
        return _request("GET", "/api/landmarks/stats", need_user_id=False, base_url=base_url)
    return {"error": f"未知地标操作: {operation}，可选: list, by_name, search, by_id, stats"}


# ---------- 合并入口：房源 houses(operation, **kwargs) ----------


def houses(
    operation: str,
    *,
    house_id: Optional[str] = None,
    community: Optional[str] = None,
    landmark_id: Optional[str] = None,
    listing_platform: Optional[str] = None,
    page: Optional[int] = None,
    page_size: Optional[int] = None,
    max_distance: Optional[float] = None,
    max_distance_m: Optional[float] = None,
    type: Optional[str] = None,
    district: Optional[str] = None,
    area: Optional[str] = None,
    min_price: Optional[int] = None,
    max_price: Optional[int] = None,
    bedrooms: Optional[str] = None,
    rental_type: Optional[str] = None,
    decoration: Optional[str] = None,
    orientation: Optional[str] = None,
    elevator: Optional[str] = None,
    min_area: Optional[int] = None,
    max_area: Optional[int] = None,
    property_type: Optional[str] = None,
    subway_line: Optional[str] = None,
    max_subway_dist: Optional[int] = None,
    subway_station: Optional[str] = None,
    utilities_type: Optional[str] = None,
    available_from_before: Optional[str] = None,
    commute_to_xierqi_max: Optional[int] = None,
    sort_by: Optional[str] = None,
    sort_order: Optional[str] = None,
    base_url: Optional[str] = None,
    user_id: Optional[str] = None,
    **kwargs: Any,
) -> dict:
    """
    房源统一入口。operation 取值：
    - init: 房源数据重置
    - get: 单套房源详情，必填 house_id
    - listings: 房源各平台挂牌记录，必填 house_id
    - by_community: 按小区查可租房源，必填 community，可选 listing_platform, page, page_size
    - by_platform: 多条件筛选，可选 district, area, min/max_price, bedrooms, rental_type, 地铁/通勤等
    - nearby: 地标附近房源，必填 landmark_id，可选 max_distance, listing_platform, page, page_size
    - nearby_landmarks: 小区周边地标(商超/公园)，必填 community，可选 type(shopping/park), max_distance_m
    - stats: 房源统计
    """
    op = operation.strip().lower()
    hid = house_id or kwargs.get("house_id")
    uid = user_id if user_id is not None else kwargs.get("user_id")
    base = base_url or kwargs.get("base_url")

    if op == "init":
        return _request("POST", "/api/houses/init", need_user_id=True, base_url=base, user_id=uid)

    if op == "get":
        if not hid:
            return {"error": "请提供房源 ID house_id"}
        return _request("GET", f"/api/houses/{hid}", need_user_id=True, base_url=base, user_id=uid)

    if op == "listings":
        if not hid:
            return {"error": "请提供房源 ID house_id"}
        return _request("GET", f"/api/houses/listings/{hid}", need_user_id=True, base_url=base, user_id=uid)

    if op == "by_community":
        c = community or kwargs.get("community")
        if not c:
            return {"error": "请提供小区名 community"}
        params: dict[str, Any] = {"community": c}
        if listing_platform is not None:
            params["listing_platform"] = listing_platform
        if page is not None:
            params["page"] = page
        if page_size is not None:
            params["page_size"] = page_size
        return _request("GET", "/api/houses/by_community", params=params, need_user_id=True, base_url=base, user_id=uid)

    if op == "by_platform":
        params = {}
        if listing_platform is not None:
            params["listing_platform"] = listing_platform
        if district is not None:
            params["district"] = district
        if area is not None:
            params["area"] = area
        if min_price is not None:
            params["min_price"] = min_price
        if max_price is not None:
            params["max_price"] = max_price
        if bedrooms is not None:
            params["bedrooms"] = bedrooms
        if rental_type is not None:
            params["rental_type"] = rental_type
        if decoration is not None:
            params["decoration"] = decoration
        if orientation is not None:
            params["orientation"] = orientation
        if elevator is not None:
            params["elevator"] = elevator
        if min_area is not None:
            params["min_area"] = min_area
        if max_area is not None:
            params["max_area"] = max_area
        if property_type is not None:
            params["property_type"] = property_type
        if subway_line is not None:
            params["subway_line"] = subway_line
        if max_subway_dist is not None:
            params["max_subway_dist"] = max_subway_dist
        if subway_station is not None:
            params["subway_station"] = subway_station
        if utilities_type is not None:
            params["utilities_type"] = utilities_type
        if available_from_before is not None:
            params["available_from_before"] = available_from_before
        if commute_to_xierqi_max is not None:
            params["commute_to_xierqi_max"] = commute_to_xierqi_max
        if sort_by is not None:
            params["sort_by"] = sort_by
        if sort_order is not None:
            params["sort_order"] = sort_order
        if page is not None:
            params["page"] = page
        if page_size is not None:
            params["page_size"] = page_size
        return _request("GET", "/api/houses/by_platform", params=params or None, need_user_id=True, base_url=base, user_id=uid)

    if op == "nearby":
        lid = landmark_id or kwargs.get("landmark_id")
        if not lid:
            return {"error": "请提供地标 ID 或名称 landmark_id"}
        params = {"landmark_id": lid}
        if max_distance is not None:
            params["max_distance"] = max_distance
        if listing_platform is not None:
            params["listing_platform"] = listing_platform
        if page is not None:
            params["page"] = page
        if page_size is not None:
            params["page_size"] = page_size
        return _request("GET", "/api/houses/nearby", params=params, need_user_id=True, base_url=base, user_id=uid)

    if op == "nearby_landmarks":
        c = community or kwargs.get("community")
        if not c:
            return {"error": "请提供小区名 community"}
        params = {"community": c}
        if type is not None:
            params["type"] = type
        if max_distance_m is not None:
            params["max_distance_m"] = max_distance_m
        return _request("GET", "/api/houses/nearby_landmarks", params=params, need_user_id=True, base_url=base, user_id=uid)

    if op == "stats":
        return _request("GET", "/api/houses/stats", need_user_id=True, base_url=base, user_id=uid)

    return {"error": f"未知房源操作: {operation}，可选: init, get, listings, by_community, by_platform, nearby, nearby_landmarks, stats"}


# ---------- 合并入口：房源操作 house_action(operation, house_id, listing_platform, **kwargs) ----------


def house_action(
    operation: str,
    house_id: str,
    listing_platform: str,
    *,
    base_url: Optional[str] = None,
    user_id: Optional[str] = None,
    **kwargs: Any,
) -> dict:
    """
    房源操作统一入口。operation 取值：rent(租房) | terminate(退租) | offline(下架)。
    listing_platform 必填：链家 / 安居客 / 58同城。
    """
    if not house_id:
        return {"error": "请提供房源 ID"}
    if not listing_platform or listing_platform not in LISTING_PLATFORMS:
        return {"error": "请提供挂牌平台：链家、安居客、58同城"}
    op = operation.strip().lower()
    uid = user_id if user_id is not None else kwargs.get("user_id")
    base = base_url or kwargs.get("base_url")
    params = {"listing_platform": listing_platform}
    if op == "rent":
        return _request("POST", f"/api/houses/{house_id}/rent", params=params, need_user_id=True, base_url=base, user_id=uid)
    if op == "terminate":
        return _request("POST", f"/api/houses/{house_id}/terminate", params=params, need_user_id=True, base_url=base, user_id=uid)
    if op == "offline":
        return _request("POST", f"/api/houses/{house_id}/offline", params=params, need_user_id=True, base_url=base, user_id=uid)
    return {"error": f"未知操作: {operation}，可选: rent, terminate, offline"}


# ---------- 便捷别名（委托到合并入口，兼容旧用法） ----------


def get_landmarks(
    category: Optional[str] = None,
    district: Optional[str] = None,
    base_url: Optional[str] = None,
) -> dict:
    """获取地标列表。"""
    return landmarks("list", category=category, district=district, base_url=base_url)


def get_landmark_by_name(name: str, base_url: Optional[str] = None) -> dict:
    """按名称精确查询地标。"""
    return landmarks("by_name", name=name, base_url=base_url)


def search_landmarks(
    q: str,
    category: Optional[str] = None,
    district: Optional[str] = None,
    base_url: Optional[str] = None,
) -> dict:
    """关键词模糊搜索地标。"""
    return landmarks("search", q=q, category=category, district=district, base_url=base_url)


def get_landmark_by_id(landmark_id: str, base_url: Optional[str] = None) -> dict:
    """按地标 id 查询地标详情。"""
    return landmarks("by_id", landmark_id=landmark_id, base_url=base_url)


def get_landmark_stats(base_url: Optional[str] = None) -> dict:
    """获取地标统计信息。"""
    return landmarks("stats", base_url=base_url)


def house_init(base_url: Optional[str] = None, user_id: Optional[str] = None) -> dict:
    """房源数据重置。"""
    return houses("init", base_url=base_url, user_id=user_id)


def get_house(
    house_id: str,
    base_url: Optional[str] = None,
    user_id: Optional[str] = None,
) -> dict:
    """根据房源 ID 获取单套房源详情。"""
    return houses("get", house_id=house_id, base_url=base_url, user_id=user_id)


def get_house_listings(
    house_id: str,
    base_url: Optional[str] = None,
    user_id: Optional[str] = None,
) -> dict:
    """根据房源 ID 获取各平台挂牌记录。"""
    return houses("listings", house_id=house_id, base_url=base_url, user_id=user_id)


def get_houses_by_community(
    community: str,
    listing_platform: Optional[str] = None,
    page: Optional[int] = None,
    page_size: Optional[int] = None,
    base_url: Optional[str] = None,
    user_id: Optional[str] = None,
) -> dict:
    """按小区名查询可租房源。"""
    return houses(
        "by_community",
        community=community,
        listing_platform=listing_platform,
        page=page,
        page_size=page_size,
        base_url=base_url,
        user_id=user_id,
    )


def get_houses_by_platform(
    listing_platform: Optional[str] = None,
    district: Optional[str] = None,
    area: Optional[str] = None,
    min_price: Optional[int] = None,
    max_price: Optional[int] = None,
    bedrooms: Optional[str] = None,
    rental_type: Optional[str] = None,
    decoration: Optional[str] = None,
    orientation: Optional[str] = None,
    elevator: Optional[str] = None,
    min_area: Optional[int] = None,
    max_area: Optional[int] = None,
    property_type: Optional[str] = None,
    subway_line: Optional[str] = None,
    max_subway_dist: Optional[int] = None,
    subway_station: Optional[str] = None,
    utilities_type: Optional[str] = None,
    available_from_before: Optional[str] = None,
    commute_to_xierqi_max: Optional[int] = None,
    sort_by: Optional[str] = None,
    sort_order: Optional[str] = None,
    page: Optional[int] = None,
    page_size: Optional[int] = None,
    base_url: Optional[str] = None,
    user_id: Optional[str] = None,
) -> dict:
    """按挂牌平台及多条件筛选可租房源。"""
    return houses(
        "by_platform",
        listing_platform=listing_platform,
        district=district,
        area=area,
        min_price=min_price,
        max_price=max_price,
        bedrooms=bedrooms,
        rental_type=rental_type,
        decoration=decoration,
        orientation=orientation,
        elevator=elevator,
        min_area=min_area,
        max_area=max_area,
        property_type=property_type,
        subway_line=subway_line,
        max_subway_dist=max_subway_dist,
        subway_station=subway_station,
        utilities_type=utilities_type,
        available_from_before=available_from_before,
        commute_to_xierqi_max=commute_to_xierqi_max,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        page_size=page_size,
        base_url=base_url,
        user_id=user_id,
    )


def get_houses_nearby(
    landmark_id: str,
    max_distance: Optional[float] = None,
    listing_platform: Optional[str] = None,
    page: Optional[int] = None,
    page_size: Optional[int] = None,
    base_url: Optional[str] = None,
    user_id: Optional[str] = None,
) -> dict:
    """以地标为圆心查附近房源。"""
    return houses(
        "nearby",
        landmark_id=landmark_id,
        max_distance=max_distance,
        listing_platform=listing_platform,
        page=page,
        page_size=page_size,
        base_url=base_url,
        user_id=user_id,
    )


def get_nearby_landmarks(
    community: str,
    type: Optional[str] = None,
    max_distance_m: Optional[float] = None,
    base_url: Optional[str] = None,
    user_id: Optional[str] = None,
) -> dict:
    """查询小区周边地标（商超/公园）。"""
    return houses(
        "nearby_landmarks",
        community=community,
        type=type,
        max_distance_m=max_distance_m,
        base_url=base_url,
        user_id=user_id,
    )


def get_house_stats(
    base_url: Optional[str] = None,
    user_id: Optional[str] = None,
) -> dict:
    """获取房源统计信息。"""
    return houses("stats", base_url=base_url, user_id=user_id)


def rent_house(
    house_id: str,
    listing_platform: str,
    base_url: Optional[str] = None,
    user_id: Optional[str] = None,
) -> dict:
    """租房。"""
    return house_action("rent", house_id, listing_platform, base_url=base_url, user_id=user_id)


def terminate_rental(
    house_id: str,
    listing_platform: str,
    base_url: Optional[str] = None,
    user_id: Optional[str] = None,
) -> dict:
    """退租。"""
    return house_action("terminate", house_id, listing_platform, base_url=base_url, user_id=user_id)


def take_offline(
    house_id: str,
    listing_platform: str,
    base_url: Optional[str] = None,
    user_id: Optional[str] = None,
) -> dict:
    """下架。"""
    return house_action("offline", house_id, listing_platform, base_url=base_url, user_id=user_id)


# ---------- 导出 ----------

__all__ = [
    "landmarks",
    "houses",
    "house_action",
    "get_landmarks",
    "get_landmark_by_name",
    "search_landmarks",
    "get_landmark_by_id",
    "get_landmark_stats",
    "house_init",
    "get_house",
    "get_house_listings",
    "get_houses_by_community",
    "get_houses_by_platform",
    "get_houses_nearby",
    "get_nearby_landmarks",
    "get_house_stats",
    "rent_house",
    "terminate_rental",
    "take_offline",
    "LISTING_PLATFORMS",
    "DEFAULT_BASE_URL",
    "DEFAULT_USER_ID",
]
