from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, TypedDict
from uuid import uuid4

from langgraph.graph import END, StateGraph

from config import get_settings
from tools.amap_tool import AMapClient
from tools.distance_tool import calculate_distance_matrix
from tools.feishu_tool import FeishuClient
from tools.map_render_tool import generate_map_html, write_map_html


ReadTable = Callable[[str, str], list[dict[str, Any]]]
Geocode = Callable[[list[dict[str, Any]]], list[dict[str, Any]]]


class MapAgentState(TypedDict, total=False):
    app_token: str
    table_id: str
    amap_js_key: str
    output_dir: str
    task_id: str
    raw_locations: list[dict[str, Any]]
    geocoded_locations: list[dict[str, Any]]
    final_locations: list[dict[str, Any]]
    map_path: str
    logs: list[str]
    error: str


@dataclass(frozen=True)
class MapAgentResult:
    task_id: str
    map_path: Path
    success_count: int
    logs: list[str]
    error: str = ""


def build_map_agent(read_table: ReadTable, geocode: Geocode):
    graph = StateGraph(MapAgentState)

    def read_feishu(state: MapAgentState) -> MapAgentState:
        try:
            locations = read_table(state["app_token"], state["table_id"])
            return {
                **state,
                "raw_locations": locations,
                "logs": [*state.get("logs", []), f"已从飞书读取 {len(locations)} 条记录"],
            }
        except Exception as exc:
            return {**state, "error": str(exc)}

    def geocode_locations(state: MapAgentState) -> MapAgentState:
        if state.get("error"):
            return state
        try:
            geocoded = geocode(state.get("raw_locations", []))
            success_count = sum(1 for item in geocoded if item.get("lng") is not None)
            return {
                **state,
                "geocoded_locations": geocoded,
                "logs": [
                    *state.get("logs", []),
                    f"地理编码完成：成功 {success_count} 个，失败 {len(geocoded) - success_count} 个",
                ],
            }
        except Exception as exc:
            return {**state, "error": str(exc)}

    def calculate_distances(state: MapAgentState) -> MapAgentState:
        if state.get("error"):
            return state
        final_locations = calculate_distance_matrix(state.get("geocoded_locations", []))
        if len(final_locations) < 1:
            return {**state, "error": "没有可用于生成地图的有效坐标"}
        return {
            **state,
            "final_locations": final_locations,
            "logs": [*state.get("logs", []), f"距离矩阵计算完成：{len(final_locations)} 个有效地点"],
        }

    def render_map(state: MapAgentState) -> MapAgentState:
        if state.get("error"):
            return state
        try:
            html = generate_map_html(state.get("final_locations", []), state["amap_js_key"])
            path = write_map_html(html, state["task_id"], state["output_dir"])
            return {
                **state,
                "map_path": str(path),
                "logs": [*state.get("logs", []), f"地图已生成：{path}"],
            }
        except Exception as exc:
            return {**state, "error": str(exc)}

    graph.add_node("read_feishu", read_feishu)
    graph.add_node("geocode", geocode_locations)
    graph.add_node("distance", calculate_distances)
    graph.add_node("render", render_map)

    graph.set_entry_point("read_feishu")
    graph.add_edge("read_feishu", "geocode")
    graph.add_edge("geocode", "distance")
    graph.add_edge("distance", "render")
    graph.add_edge("render", END)

    return graph.compile()


def run_map_agent(
    app_token: str,
    table_id: str,
    amap_js_key: str | None = None,
    output_dir: str | Path | None = None,
    read_table: ReadTable | None = None,
    geocode: Geocode | None = None,
) -> MapAgentResult:
    settings = get_settings()
    feishu = FeishuClient(settings.feishu_app_id, settings.feishu_app_secret)
    amap = AMapClient(settings.amap_web_key)

    read_table = read_table or feishu.read_bitable_records
    geocode = geocode or amap.geocode_addresses
    task_id = uuid4().hex
    output_dir = output_dir or settings.map_output_dir
    amap_js_key = amap_js_key or settings.amap_js_key

    agent = build_map_agent(read_table=read_table, geocode=geocode)
    state = agent.invoke(
        {
            "app_token": app_token,
            "table_id": table_id,
            "amap_js_key": amap_js_key,
            "output_dir": str(output_dir),
            "task_id": task_id,
            "logs": [],
            "error": "",
        }
    )

    return MapAgentResult(
        task_id=task_id,
        map_path=Path(state.get("map_path", Path(output_dir) / f"{task_id}.html")),
        success_count=len(state.get("final_locations", [])),
        logs=state.get("logs", []),
        error=state.get("error", ""),
    )
