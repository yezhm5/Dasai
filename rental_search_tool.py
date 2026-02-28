#!/usr/bin/env python3
"""
房源搜索工具。基于用户输入的参数调用租房 API，支持按小区、地标附近、多条件平台筛选三种方式。
对应 API 规范：AgentGameFakeAppApi-main/fake_app_agent_tools.json、README.md

推荐以函数方式调用（无需命令行）：
  from tools.rental_search_tool import search_houses, search_houses_from_dict
  result = search_houses(district="海淀", max_price=5000)
  result = search_houses_from_dict({"community": "建清园(南区)"})
"""
import json
import os
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from typing import Any, Optional


# 挂牌平台枚举（与 API 一致）
LISTING_PLATFORMS = ("链家", "安居客", "58同城")


class RentalSearchTool:
    """基于用户输入参数搜索房源的统一工具类。"""

    def __init__(
        self,
        base_url: Optional[str] = None,
        user_id: Optional[str] = None,
    ):
        self.base_url = (base_url or os.environ.get("RENTAL_API_BASE_URL") or "").rstrip("/") or "http://localhost:8080"
        self.user_id = user_id or os.environ.get("X_USER_ID") or ""

    def _request(
        self,
        method: str,
        path: str,
        params: Optional[dict] = None,
        data: Optional[dict] = None,
        need_user_id: bool = False,
    ) -> dict:
        url = f"{self.base_url}{path}"
        if params:
            url += "?" + urlencode({k: v for k, v in params.items() if v is not None})
        headers = {"Content-Type": "application/json"}
        if need_user_id and self.user_id:
            headers["X-User-ID"] = self.user_id
        req = Request(url, data=json.dumps(data).encode() if data else None, headers=headers, method=method)
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

    def _get_landmark_id(self, name_or_id: str) -> Optional[str]:
        """按名称或 ID 解析地标，返回地标 ID。"""
        # 若已是 ID 格式（如 SS_001、LM_002），可直接用于 nearby
        if name_or_id and "_" in name_or_id and len(name_or_id) <= 10:
            r = self._request("GET", f"/api/landmarks/{name_or_id}", need_user_id=False)
            if "error" not in r and r.get("data"):
                return name_or_id
        # 按名称精确查询
        r = self._request("GET", f"/api/landmarks/name/{name_or_id}", need_user_id=False)
        if "error" in r:
            r = self._request("GET", "/api/landmarks/search", params={"q": name_or_id}, need_user_id=False)
        if "error" in r:
            return None
        data = r.get("data")
        if isinstance(data, list) and data:
            return data[0].get("id")
        if isinstance(data, dict):
            return data.get("id")
        return None

    def search(
        self,
        # 路由：小区 / 地标附近 / 平台多条件
        community: Optional[str] = None,
        landmark: Optional[str] = None,
        landmark_id: Optional[str] = None,
        # 平台多条件（by_platform）
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
        # 通用
        listing_platform: Optional[str] = None,
        page: Optional[int] = None,
        page_size: Optional[int] = None,
        # 地标附近专用
        max_distance: Optional[float] = None,
        **kwargs: Any,
    ) -> dict:
        """
        根据用户输入参数搜索房源。自动选择接口：
        - 指定小区名 → 按小区查询（by_community）
        - 指定地标名或地标 ID → 先解析地标再查附近房源（nearby）
        - 其他 → 多条件平台筛选（by_platform）
        房源相关接口需要设置 user_id（构造或环境变量 X_USER_ID）。
        """
        if not self.user_id:
            return {"error": "房源搜索需要设置 user_id（构造参数或环境变量 X_USER_ID）", "data": None}

        # 1）按小区
        if community:
            params = {"community": community.strip()}
            if listing_platform:
                params["listing_platform"] = listing_platform
            if page is not None:
                params["page"] = page
            if page_size is not None:
                params["page_size"] = page_size
            return self._request("GET", "/api/houses/by_community", params=params, need_user_id=True)

        # 2）地标附近
        lid = landmark_id or (self._get_landmark_id(landmark) if landmark else None)
        if lid:
            params = {"landmark_id": lid}
            if max_distance is not None:
                params["max_distance"] = max_distance
            if listing_platform:
                params["listing_platform"] = listing_platform
            if page is not None:
                params["page"] = page
            if page_size is not None:
                params["page_size"] = page_size
            return self._request("GET", "/api/houses/nearby", params=params, need_user_id=True)

        if landmark and not lid:
            return {"error": f"未找到地标：{landmark}", "data": None}

        # 3）多条件平台筛选
        params = {}
        if listing_platform:
            params["listing_platform"] = listing_platform
        if district:
            params["district"] = district
        if area:
            params["area"] = area
        if min_price is not None:
            params["min_price"] = min_price
        if max_price is not None:
            params["max_price"] = max_price
        if bedrooms is not None:
            params["bedrooms"] = bedrooms
        if rental_type:
            params["rental_type"] = rental_type
        if decoration:
            params["decoration"] = decoration
        if orientation:
            params["orientation"] = orientation
        if elevator:
            params["elevator"] = elevator
        if min_area is not None:
            params["min_area"] = min_area
        if max_area is not None:
            params["max_area"] = max_area
        if property_type:
            params["property_type"] = property_type
        if subway_line:
            params["subway_line"] = subway_line
        if max_subway_dist is not None:
            params["max_subway_dist"] = max_subway_dist
        if subway_station:
            params["subway_station"] = subway_station
        if utilities_type:
            params["utilities_type"] = utilities_type
        if available_from_before:
            params["available_from_before"] = available_from_before
        if commute_to_xierqi_max is not None:
            params["commute_to_xierqi_max"] = commute_to_xierqi_max
        if sort_by:
            params["sort_by"] = sort_by
        if sort_order:
            params["sort_order"] = sort_order
        if page is not None:
            params["page"] = page
        if page_size is not None:
            params["page_size"] = page_size

        return self._request("GET", "/api/houses/by_platform", params=params or None, need_user_id=True)

    def search_from_dict(self, params: dict) -> dict:
        """从字典构造搜索参数并调用 search。键与 search() 关键字参数一致。"""
        allowed = {
            "community", "landmark", "landmark_id", "district", "area",
            "min_price", "max_price", "bedrooms", "rental_type", "decoration",
            "orientation", "elevator", "min_area", "max_area", "property_type",
            "subway_line", "max_subway_dist", "subway_station", "utilities_type",
            "available_from_before", "commute_to_xierqi_max", "sort_by", "sort_order",
            "listing_platform", "page", "page_size", "max_distance",
        }
        kwargs = {k: v for k, v in params.items() if k in allowed and v is not None}
        return self.search(**kwargs)


# ---------- 模块级函数接口（支持直接函数调用，无需命令行） ----------

def search_houses(
    base_url: Optional[str] = None,
    user_id: Optional[str] = None,
    *,
    community: Optional[str] = None,
    landmark: Optional[str] = None,
    landmark_id: Optional[str] = None,
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
    listing_platform: Optional[str] = None,
    page: Optional[int] = None,
    page_size: Optional[int] = None,
    max_distance: Optional[float] = None,
    **kwargs: Any,
) -> dict:
    """
    按参数搜索房源（函数调用入口）。不传 base_url/user_id 时从环境变量读取。
    用法示例：
        from tools.rental_search_tool import search_houses
        result = search_houses(district="海淀", max_price=5000, page_size=10)
        result = search_houses(community="建清园(南区)")
        result = search_houses(landmark="西二旗站", max_distance=2000)
    """
    tool = RentalSearchTool(base_url=base_url, user_id=user_id)
    return tool.search(
        community=community,
        landmark=landmark,
        landmark_id=landmark_id,
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
        listing_platform=listing_platform,
        page=page,
        page_size=page_size,
        max_distance=max_distance,
        **kwargs,
    )


def search_houses_from_dict(
    params: dict,
    base_url: Optional[str] = None,
    user_id: Optional[str] = None,
) -> dict:
    """
    从字典参数搜索房源（函数调用入口）。适合从 NLU/配置中拿到参数字典后直接调用。
    用法示例：
        from tools.rental_search_tool import search_houses_from_dict
        result = search_houses_from_dict({"district": "海淀", "max_price": 5000})
    """
    tool = RentalSearchTool(base_url=base_url, user_id=user_id)
    return tool.search_from_dict(params)


def get_tool(base_url: Optional[str] = None, user_id: Optional[str] = None) -> RentalSearchTool:
    """获取一个 RentalSearchTool 实例，便于多次调用时复用。"""
    return RentalSearchTool(base_url=base_url, user_id=user_id)


def main():
    """命令行简单演示：从 JSON 或键值对读入参数并搜索。"""
    import argparse
    parser = argparse.ArgumentParser(description="房源搜索工具类演示")
    parser.add_argument("--base-url", default=os.environ.get("RENTAL_API_BASE_URL", "http://localhost:8080"))
    parser.add_argument("--user-id", default=os.environ.get("X_USER_ID"))
    parser.add_argument("--params", type=str, help='JSON 对象，如 {"district":"海淀","max_price":5000}')
    parser.add_argument("--community", help="按小区名搜索")
    parser.add_argument("--landmark", help="按地标名查附近房源")
    parser.add_argument("--district", help="行政区")
    parser.add_argument("--max-price", type=int, dest="max_price")
    parser.add_argument("--page", type=int)
    parser.add_argument("--page-size", type=int, dest="page_size")
    args = parser.parse_args()

    tool = RentalSearchTool(base_url=args.base_url, user_id=args.user_id)
    if args.params:
        params = json.loads(args.params)
        result = tool.search_from_dict(params)
    else:
        kwargs = {}
        if args.community:
            kwargs["community"] = args.community
        if args.landmark:
            kwargs["landmark"] = args.landmark
        if args.district:
            kwargs["district"] = args.district
        if args.max_price is not None:
            kwargs["max_price"] = args.max_price
        if args.page is not None:
            kwargs["page"] = args.page
        if args.page_size is not None:
            kwargs["page_size"] = args.page_size
        result = tool.search(**kwargs)

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
