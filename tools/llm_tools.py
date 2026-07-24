"""
LangChain 工具包装 — 将项目现有能力封装为 LLM 可调用的工具。
"""

import logging
from uuid import uuid4

from langchain_core.tools import tool

from config import get_settings
from tools.amap_tool import AMapClient
from tools.distance_tool import calculate_distance_matrix
from tools.feishu_tool import FeishuClient
from tools.map_render_tool import generate_map_html, write_map_html

logger = logging.getLogger(__name__)


@tool
def list_feishu_tables() -> list[dict]:
    """列出配置的所有飞书多维表格，帮助匹配用户的意图到具体的表格。

    遍历所有已配置的飞书应用，获取每个应用下的多维表格列表。
    返回每个表格的名称、ID 以及所属应用信息，供用户选择后续要操作的表格。
    """
    settings = get_settings()
    app_tokens = settings.get_app_tokens()
    results: list[dict] = []

    logger.info("list_feishu_tables: found %d app tokens to query", len(app_tokens))

    for app_info in app_tokens:
        app_token = app_info.get("app_token", "")
        app_name = app_info.get("name", app_token)
        try:
            client = FeishuClient(
                app_id=settings.feishu_app_id, app_secret=settings.feishu_app_secret
            )
            tables = client.list_tables(app_token)
            for table in tables:
                results.append(
                    {
                        "app_name": app_name,
                        "app_token": app_token,
                        "table_id": table.get("table_id", ""),
                        "table_name": table.get("name", ""),
                    }
                )
        except Exception as e:
            logger.warning("获取应用 %s (token=%s) 的表格列表失败: %s", app_name, app_token, e, exc_info=True)
            continue

    logger.info("list_feishu_tables: returning %d tables total", len(results))
    return results


@tool
def read_feishu_records(app_token: str, table_id: str) -> list[dict]:
    """读取指定飞书多维表格中的地点记录。

    根据提供的应用 token 和表格 ID，从飞书多维表格中读取所有地点数据，
    每条记录包含名称和地址信息。

    Args:
        app_token: 飞书应用的 app_token（从 list_feishu_tables 的结果中获取）
        table_id: 多维表格的 table_id（从 list_feishu_tables 的结果中获取）
    """
    settings = get_settings()
    try:
        client = FeishuClient(
            app_id=settings.feishu_app_id, app_secret=settings.feishu_app_secret
        )
        records = client.read_bitable_records(app_token, table_id)
        return records
    except Exception as e:
        logger.error("读取飞书记录失败 (app_token=%s, table_id=%s): %s", app_token, table_id, e)
        return [{"error": str(e), "app_token": app_token, "table_id": table_id}]


@tool
def geocode_addresses_async(locations: list[dict]) -> list[dict]:
    """对地点列表进行批量地理编码，获取经纬度坐标。

    使用高德地图地理编码 API 将地址文本转换为经纬度坐标。

    Args:
        locations: 地点字典列表，每个地点需包含 name 和 address 字段。
                   例如 [{"name": "深圳南山店", "address": "深圳市南山区科技园"}]
    """
    settings = get_settings()
    try:
        client = AMapClient(web_key=settings.amap_web_key)
        geocoded = client.geocode_addresses(locations)
        return geocoded
    except Exception as e:
        logger.error("地理编码失败: %s", e)
        return [{"error": str(e)}]


@tool
def calculate_distances(locations: list[dict]) -> list[dict]:
    """计算地点之间的两两直线距离矩阵。

    为每个地点计算其到其他所有地点的直线距离（基于 Haversine 公式），
    结果以 distances 字段附加到每个地点上，方便后续分析或在地图上展示。

    Args:
        locations: 地点字典列表，每个地点需包含 name、lng、lat 字段。
                   经纬度缺失的地点会被自动跳过。
    """
    try:
        result = calculate_distance_matrix(locations)
        return result
    except Exception as e:
        logger.error("距离计算失败: %s", e)
        return [{"error": str(e)}]


@tool
def render_map(locations: list[dict], title: str = "地址标注地图") -> dict:
    """生成交互式地址标注地图 HTML 页面。

    根据提供的地点数据（含经纬度和距离矩阵）生成一张高德地图，
    在地图上标记所有地点位置，并展示距离矩阵表格。

    Args:
        locations: 地点字典列表，需包含 name、lng、lat 字段，推荐也包含 distances。
        title: 地图标题，默认 "地址标注地图"。
    """
    settings = get_settings()
    task_id = uuid4().hex
    try:
        # Auto-calculate distance matrix if not already present
        if any("distances" not in loc for loc in locations):
            logger.info("render_map: calculating distance matrix for %d locations", len(locations))
            locations = calculate_distance_matrix(locations)
        html = generate_map_html(locations, settings.amap_js_key, title=title)
        write_map_html(html, task_id, settings.map_output_dir)
        url = f"{settings.public_base_url}/maps/{task_id}.html"
        return {"url": url, "task_id": task_id, "count": len(locations)}
    except Exception as e:
        logger.error("生成地图失败: %s", e)
        return {"error": str(e), "task_id": task_id, "count": len(locations)}
