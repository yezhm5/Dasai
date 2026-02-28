#!/usr/bin/env python3
"""
租房 API 命令行工具。供租房 Agent 通过子命令调用，实现地标查询、房源筛选、租房/退租/下架等。
"""
import argparse
import json
import os
import sys
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

# ---------- 人工配置 ----------
BASE_URL = "http://localhost:8080"  # 租房 API 根地址
X_USER_ID = ""                        # 用户工号，房源接口必填
# ------------------------------


def request(method: str, path: str, params: dict = None, data: dict = None, need_user_id: bool = False) -> dict:
    url = f"{BASE_URL.rstrip('/')}{path}"
    if params:
        url += "?" + urlencode({k: v for k, v in params.items() if v is not None})
    headers = {"Content-Type": "application/json"}
    if need_user_id and X_USER_ID:
        headers["X-User-ID"] = X_USER_ID
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


def _parse_common_list_args(args) -> dict:
    params = {}
    if getattr(args, "page", None) is not None:
        params["page"] = args.page
    if getattr(args, "page_size", None) is not None:
        params["page_size"] = args.page_size
    if getattr(args, "listing_platform", None):
        params["listing_platform"] = args.listing_platform
    return params


# ---------- 地标（无需 X-User-ID） ----------
def cmd_landmarks(args):
    params = _parse_common_list_args(args)
    if getattr(args, "category", None):
        params["category"] = args.category
    if getattr(args, "district", None):
        params["district"] = args.district
    return request("GET", "/api/landmarks", params=params or None, need_user_id=False)


def cmd_landmark_by_name(args):
    name = getattr(args, "name", None) or getattr(args, "landmark_name", None)
    if not name:
        return {"error": "请提供地标名称，例如: landmark-by-name 西二旗站"}
    return request("GET", f"/api/landmarks/name/{name}", need_user_id=False)


def cmd_search_landmarks(args):
    params = {"q": args.q}
    if getattr(args, "category", None):
        params["category"] = args.category
    if getattr(args, "district", None):
        params["district"] = args.district
    return request("GET", "/api/landmarks/search", params=params, need_user_id=False)


def cmd_landmark_by_id(args):
    return request("GET", f"/api/landmarks/{args.id}", need_user_id=False)


def cmd_landmark_stats(args):
    return request("GET", "/api/landmarks/stats", need_user_id=False)


# ---------- 房源（需 X-User-ID） ----------
def cmd_house_init(args):
    return request("POST", "/api/houses/init", need_user_id=True)


def cmd_house_by_id(args):
    return request("GET", f"/api/houses/{args.house_id}", need_user_id=True)


def cmd_house_listings(args):
    return request("GET", f"/api/houses/listings/{args.house_id}", need_user_id=True)


def cmd_houses_by_community(args):
    params = {"community": args.community}
    params.update(_parse_common_list_args(args))
    return request("GET", "/api/houses/by_community", params=params, need_user_id=True)


def cmd_houses_by_platform(args):
    params = _parse_common_list_args(args)
    for key in ("district", "area", "min_price", "max_price", "bedrooms", "rental_type",
                "decoration", "orientation", "elevator", "min_area", "max_area", "property_type",
                "subway_line", "max_subway_dist", "subway_station", "utilities_type",
                "available_from_before", "commute_to_xierqi_max", "sort_by", "sort_order"):
        v = getattr(args, key, None)
        if v is not None:
            params[key] = v
    return request("GET", "/api/houses/by_platform", params=params or None, need_user_id=True)


def cmd_houses_nearby(args):
    params = {"landmark_id": args.landmark_id}
    if getattr(args, "max_distance", None) is not None:
        params["max_distance"] = args.max_distance
    params.update(_parse_common_list_args(args))
    return request("GET", "/api/houses/nearby", params=params, need_user_id=True)


def cmd_nearby_landmarks(args):
    params = {"community": args.community}
    if getattr(args, "type", None):
        params["type"] = args.type
    if getattr(args, "max_distance_m", None) is not None:
        params["max_distance_m"] = args.max_distance_m
    return request("GET", "/api/houses/nearby_landmarks", params=params, need_user_id=True)


def cmd_house_stats(args):
    return request("GET", "/api/houses/stats", need_user_id=True)


def cmd_rent(args):
    return request("POST", f"/api/houses/{args.house_id}/rent", params={"listing_platform": args.listing_platform}, need_user_id=True)


def cmd_terminate(args):
    return request("POST", f"/api/houses/{args.house_id}/terminate", params={"listing_platform": args.listing_platform}, need_user_id=True)


def cmd_offline(args):
    return request("POST", f"/api/houses/{args.house_id}/offline", params={"listing_platform": args.listing_platform}, need_user_id=True)


def main():
    global BASE_URL, X_USER_ID
    parser = argparse.ArgumentParser(description="租房 API 命令行工具")
    parser.add_argument("--base-url", default=BASE_URL, help="API 根地址")
    parser.add_argument("--user-id", default=X_USER_ID, help="X-User-ID（房源接口必填）")
    sub = parser.add_subparsers(dest="command", required=True)

    # 地标
    p = sub.add_parser("landmarks", help="获取地标列表")
    p.add_argument("--category", choices=["subway", "company", "landmark"], help="地标类别")
    p.add_argument("--district", help="行政区，如 海淀、朝阳")
    p.set_defaults(func=cmd_landmarks)

    p = sub.add_parser("landmark-by-name", help="按名称精确查询地标")
    p.add_argument("name", nargs="?", help="地标名称")
    p.add_argument("--name", dest="landmark_name", help="地标名称（可选）")
    p.set_defaults(func=cmd_landmark_by_name)

    p = sub.add_parser("search-landmarks", help="关键词模糊搜索地标")
    p.add_argument("q", help="搜索关键词")
    p.add_argument("--category", choices=["subway", "company", "landmark"])
    p.add_argument("--district", help="行政区")
    p.set_defaults(func=cmd_search_landmarks)

    p = sub.add_parser("landmark-by-id", help="按 id 查地标")
    p.add_argument("id", help="地标 ID")
    p.set_defaults(func=cmd_landmark_by_id)

    p = sub.add_parser("landmark-stats", help="地标统计")
    p.set_defaults(func=cmd_landmark_stats)

    # 房源
    p = sub.add_parser("house-init", help="房源数据重置")
    p.set_defaults(func=cmd_house_init)

    p = sub.add_parser("house", help="根据房源 ID 获取详情")
    p.add_argument("house_id", help="房源 ID")
    p.set_defaults(func=cmd_house_by_id)

    p = sub.add_parser("house-listings", help="获取房源各平台挂牌记录")
    p.add_argument("house_id", help="房源 ID")
    p.set_defaults(func=cmd_house_listings)

    p = sub.add_parser("by-community", help="按小区名查可租房源")
    p.add_argument("community", help="小区名")
    p.add_argument("--listing_platform", choices=["链家", "安居客", "58同城"])
    p.add_argument("--page", type=int)
    p.add_argument("--page_size", type=int)
    p.set_defaults(func=cmd_houses_by_community)

    p = sub.add_parser("by-platform", help="按条件筛选可租房源（主查询接口）")
    p.add_argument("--listing_platform", choices=["链家", "安居客", "58同城"])
    p.add_argument("--district", help="行政区，逗号分隔，如 海淀,朝阳")
    p.add_argument("--area", help="商圈，逗号分隔，如 西二旗,上地")
    p.add_argument("--min_price", type=int, help="最低月租金")
    p.add_argument("--max_price", type=int, help="最高月租金")
    p.add_argument("--bedrooms", help="卧室数，逗号分隔，如 1,2")
    p.add_argument("--rental_type", choices=["整租", "合租"])
    p.add_argument("--decoration", help="精装/简装/豪华/毛坯/空房")
    p.add_argument("--orientation", help="朝向，如 朝南、南北")
    p.add_argument("--elevator", choices=["true", "false"])
    p.add_argument("--min_area", type=int)
    p.add_argument("--max_area", type=int)
    p.add_argument("--property_type", help="如 住宅")
    p.add_argument("--subway_line", help="如 13号线")
    p.add_argument("--max_subway_dist", type=int, help="最大地铁距离（米），近地铁建议 800")
    p.add_argument("--subway_station", help="地铁站名，如 车公庄站")
    p.add_argument("--utilities_type", help="如 民水民电")
    p.add_argument("--available_from_before", help="可入住日期上限 YYYY-MM-DD")
    p.add_argument("--commute_to_xierqi_max", type=int, help="到西二旗通勤时间上限（分钟）")
    p.add_argument("--sort_by", choices=["price", "area", "subway"])
    p.add_argument("--sort_order", choices=["asc", "desc"])
    p.add_argument("--page", type=int)
    p.add_argument("--page_size", type=int)
    p.set_defaults(func=cmd_houses_by_platform)

    p = sub.add_parser("nearby", help="以地标为圆心查附近房源")
    p.add_argument("landmark_id", help="地标 ID 或名称")
    p.add_argument("--max_distance", type=float, default=2000, help="最大直线距离（米）")
    p.add_argument("--listing_platform", choices=["链家", "安居客", "58同城"])
    p.add_argument("--page", type=int)
    p.add_argument("--page_size", type=int)
    p.set_defaults(func=cmd_houses_nearby)

    p = sub.add_parser("nearby-landmarks", help="查询小区周边地标（商超/公园）")
    p.add_argument("community", help="小区名")
    p.add_argument("--type", choices=["shopping", "park"], dest="type")
    p.add_argument("--max_distance_m", type=float)
    p.set_defaults(func=cmd_nearby_landmarks)

    p = sub.add_parser("house-stats", help="房源统计")
    p.set_defaults(func=cmd_house_stats)

    p = sub.add_parser("rent", help="租房")
    p.add_argument("house_id", help="房源 ID")
    p.add_argument("listing_platform", choices=["链家", "安居客", "58同城"])
    p.set_defaults(func=cmd_rent)

    p = sub.add_parser("terminate", help="退租")
    p.add_argument("house_id", help="房源 ID")
    p.add_argument("listing_platform", choices=["链家", "安居客", "58同城"])
    p.set_defaults(func=cmd_terminate)

    p = sub.add_parser("offline", help="下架")
    p.add_argument("house_id", help="房源 ID")
    p.add_argument("listing_platform", choices=["链家", "安居客", "58同城"])
    p.set_defaults(func=cmd_offline)

    args = parser.parse_args()
    BASE_URL = args.base_url or BASE_URL
    X_USER_ID = args.user_id or X_USER_ID

    if getattr(args.func, "__name__", "").startswith("cmd_house") or args.command in (
        "by-community", "by-platform", "nearby", "nearby-landmarks", "house-stats", "rent", "terminate", "offline",
        "house", "house-listings", "house-init"
    ):
        if not X_USER_ID and args.command != "house-init":
            print(json.dumps({"error": "房源相关接口需要设置 X_USER_ID（请在代码开头配置或使用 --user-id 参数）"}, ensure_ascii=False), file=sys.stderr)
            sys.exit(1)

    out = args.func(args)
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
