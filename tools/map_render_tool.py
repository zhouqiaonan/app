import html
import json
from pathlib import Path
from typing import Any


def generate_map_html(locations: list[dict[str, Any]], amap_js_key: str, title: str = "地址标注地图") -> str:
    data_json = json.dumps(locations, ensure_ascii=False)
    safe_key = html.escape(amap_js_key, quote=True)
    count = len(locations)

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <script src="https://webapi.amap.com/maps?v=2.0&key={safe_key}"></script>
  <style>
    body {{ margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei", sans-serif; color: #1f2937; }}
    .header {{ height: 56px; padding: 0 20px; display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid #e5e7eb; }}
    .header h1 {{ margin: 0; font-size: 18px; font-weight: 700; }}
    .badge {{ font-size: 13px; color: #4b5563; background: #f3f4f6; border-radius: 999px; padding: 5px 10px; }}
    #map {{ width: 100%; height: calc(58vh - 56px); min-height: 360px; }}
    .table-wrap {{ height: 42vh; min-height: 260px; overflow: auto; padding: 16px 20px; background: #f9fafb; border-top: 1px solid #e5e7eb; }}
    h2 {{ margin: 0 0 12px; font-size: 16px; }}
    table {{ border-collapse: collapse; width: 100%; background: white; font-size: 13px; }}
    th, td {{ border: 1px solid #e5e7eb; padding: 8px 10px; text-align: center; white-space: nowrap; }}
    th {{ background: #1d4ed8; color: white; font-weight: 650; }}
    td:first-child {{ background: #f3f4f6; font-weight: 650; }}
    .near {{ color: #047857; }}
    .mid {{ color: #b45309; }}
    .far {{ color: #b91c1c; }}
  </style>
</head>
<body>
  <header class="header">
    <h1>{html.escape(title)}</h1>
    <span class="badge">共 {count} 个地点</span>
  </header>
  <main>
    <div id="map"></div>
    <section class="table-wrap">
      <h2>距离矩阵</h2>
      <div id="distance-table"></div>
    </section>
  </main>
  <script>
    const locationsData = {data_json};

    function formatDistance(meters) {{
      if (meters === 0) return "-";
      return meters >= 1000 ? (meters / 1000).toFixed(1) + "km" : Math.round(meters) + "m";
    }}

    function distanceClass(meters) {{
      if (meters > 0 && meters < 5000) return "near";
      if (meters >= 5000 && meters < 20000) return "mid";
      if (meters >= 20000) return "far";
      return "";
    }}

    function renderTable() {{
      const names = locationsData.map((item) => item.name);
      let markup = "<table><thead><tr><th>地点</th>";
      names.forEach((name) => markup += `<th>${{name}}</th>`);
      markup += "</tr></thead><tbody>";
      locationsData.forEach((row) => {{
        markup += `<tr><td>${{row.name}}</td>`;
        locationsData.forEach((col) => {{
          const distance = row.distances[col.name] || 0;
          markup += `<td class="${{distanceClass(distance)}}">${{formatDistance(distance)}}</td>`;
        }});
        markup += "</tr>";
      }});
      markup += "</tbody></table>";
      document.getElementById("distance-table").innerHTML = markup;
    }}

    const initialCenter = locationsData.length ? [locationsData[0].lng, locationsData[0].lat] : [116.397, 39.908];
    const map = new AMap.Map("map", {{ zoom: 11, center: initialCenter }});
    const markers = [];
    locationsData.forEach((item) => {{
      const marker = new AMap.Marker({{
        position: [item.lng, item.lat],
        title: item.name,
        label: {{
          content: `<div style="background:#fff;padding:3px 8px;border:1px solid #1d4ed8;border-radius:4px;font-size:12px;font-weight:700;">${{item.name}}</div>`,
          direction: "top"
        }}
      }});
      markers.push(marker);
      map.add(marker);
    }});
    if (markers.length) map.setFitView(markers);
    renderTable();
  </script>
</body>
</html>
"""


def write_map_html(html_content: str, task_id: str, output_dir: str | Path) -> Path:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    map_path = output_path / f"{task_id}.html"
    map_path.write_text(html_content, encoding="utf-8")
    return map_path
