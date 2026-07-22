# Skill: 飞书地图智能体开发规范

飞书地图智能体项目的开发规范、踩坑记录和最佳实践。
当修改地图生成、地理编码、飞书 API 调用、LLM Agent 工具相关代码时，
AI 应自动遵循本规范。

## When to Use

- 添加或修改地理编码逻辑
- 对接飞书多维表格 API
- 修改 LLM Agent 的工具定义或 System Prompt
- 调试地图显示、地址解析、权限相关问题
- 修改 HTML 地图模板样式

## 高德地图（AMap）API 规范

### Key 类型
- `AMAP_WEB_KEY`：服务端地理编码 API，用于 Python 调用
- `AMAP_JS_KEY`：前端地图 JS SDK，嵌入 HTML `<script>` 标签
- 两个 Key 必须分别申请，不能混用
- Secret 不需要，本项目不使用签名模式

### QPS 限制
- 个人开发者 Key：约 3-5 QPS
- 并发地理编码时，`max_concurrency` 不得超过 **3**
- 每个请求完成后需 `await asyncio.sleep(0.2)` 避免突发
- 单次请求超时设为 15 秒

### 返回格式
```python
{"name": str, "address": str, "lng": float | None, "lat": float | None, "error"?: str}
```

## 飞书多维表格集成规范

### 权限配置流程
1. 飞书开放平台 → 权限管理 → 勾选 `bitable:app` + `bitable:app:table`
2. 版本管理与发布 → 创建版本 → 发布 → 等待管理员审核
3. 审核通过后，将机器人添加为多维表格协作者（分享 → 搜索应用名称）
4. 如果搜不到机器人，先把机器人拉进任意群聊，再搜

### 字段自动识别
- **禁止硬编码字段名**（如 `fields.get("名称")`）
- 必须先调 `GET /bitable/v1/apps/{app_token}/tables/{table_id}/fields` 获取字段列表
- 通过关键词匹配自动识别：
  - 名称关键词：`名称、名字、name、title、标题、姓名、地点、位置名`
  - 地址关键词：`地址、address、位置、location、所在地、详细地址`
- ⚠️ **记录的 key 是 `field_name`，不是 `field_id`**（高频踩坑点）
- 识别失败时 fallback 到硬编码字段名

## LLM Agent 规范

### 工具定义
- 所有 LangChain `@tool` 必须写中文 docstring
- 工具返回错误时应返回结构化数据（含 `error` 字段），不抛异常
- 同步 `@tool` 中禁止调用 `asyncio.run()`

### DeepSeek 配置
- `base_url`：`https://api.deepseek.com/v1`（官方 API）
- `model`：`deepseek-chat`
- `temperature`：`0.1`（地图相关任务需确定性）

### System Prompt 准则
- 用中文编写
- 明确工具调用顺序约束
- 包含「永远先查表再读数据」等强制规则

## 地图 HTML 模板规范

- 使用 flex 布局让地图撑满全屏
- 地图区域：`flex: 1`，表格区域：`max-height: 35vh`
- 距离颜色编码：绿色 <5km，橙色 5-20km，红色 >20km

## 环境变量规范

- 所有配置通过 `.env` + `pydantic-settings` 管理
- `.env` 在 `.gitignore` 中，不提交到 Git
- `config.py` 中每个配置项有默认值（通常是空字符串）
- ⚠️ `.env` 中的值**不要用引号包裹**（pydantic-settings 会原样读入）
