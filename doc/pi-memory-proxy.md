# pi-memory API 代理方案

> 在 pi-llm-server 中增加 pi-memory 服务的 API 代理，通过统一网关暴露记忆管理和知识库搜索能力。

---

## 一、可行性结论

**完全可行。** pi-llm-server 已有成熟的 `Client + Router` 代理模式（embedding / reranker / ASR / MinerU），pi-memory 可以直接套用该模式。

---

## 二、核心差异分析

现有服务 vs pi-memory 的关键区别：

| 维度 | 现有服务 (embedding/ASR等) | pi-memory |
|------|--------------------------|-----------|
| API 风格 | OpenAI 兼容 (`/v1/*`) | 自定义 REST (`/api/*` + `/health`) |
| HTTP 方法 | 主要是 POST | GET / POST / DELETE / PATCH |
| 响应格式 | 直接返回业务数据 | 统一包裹 `{ "success": bool, "data": {...}, "error": "..." }` |
| 认证 | 网关统一处理 | 后端自有 API Key (`Authorization: Bearer <key>`) |
| 健康检查 | 各服务有 `/health` 端点 | 有 `/health` 端点 |
| 路由数量 | 1-2 个端点 | 9 个端点 |

**结论**：pi-memory 比现有服务更像一个 "完整的小型 API 网关"，需要处理多种 HTTP 方法和更多端点，但不需要改造响应格式 —— **原样透传**即可。

---

## 三、架构设计

### 3.1 请求流转

```
用户请求 → pi-llm-server (:8090)
           │
           ├─ Auth Middleware (网关 Bearer Token)
           │
           └─ MemoryService proxy
               │ 注入 Authorization: Bearer <memory_api_key>
               ▼
           pi-memory (http://agent.adv-ci.com:9873)
               │
               └─ 返回 { success, data } 原样透传给客户端
```

### 3.2 路由映射

网关前缀: `/memory`

| 网关路由 | 方法 | → 后端路由 | 说明 |
|----------|------|-----------|------|
| `/memory/api/memory/search` | POST | `/api/memory/search` | 混合检索 |
| `/memory/api/memory/store` | POST | `/api/memory/store` | 存储记忆 |
| `/memory/api/memory/{id}` | DELETE | `/api/memory/{id}` | 删除记忆 |
| `/memory/api/memory/{id}` | PATCH | `/api/memory/{id}` | 更新记忆 |
| `/memory/api/memory/list` | GET | `/api/memory/list` | 列表+分页 |
| `/memory/api/memory/stats` | GET | `/api/memory/stats` | 统计信息 |
| `/memory/api/knowledge/search` | POST | `/api/knowledge/search` | 知识库搜索 |
| `/memory/api/knowledge/index` | POST | `/api/knowledge/index` | 重建索引 |
| `/memory/api/knowledge/stats` | GET | `/api/knowledge/stats` | 知识库统计 |

**设计原则**：路径直接映射，不在网关层做路径变换，保持与 pi-memory API 文档一致。

### 3.3 认证设计

采用 **双层认证**：
1. **网关层**：用户通过 pi-llm-server 的 Bearer Token 认证（现有机制，无需改动）
2. **后端注入**：网关转发请求时自动注入 pi-memory 的 API Key

用户在 YAML 中配置 `api_key`，网关负责注入。客户端不需要知道 pi-memory 的 key。

---

## 四、实现详情

### 4.1 文件变更清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `pi_llm_server/config.py` | 修改 | `ServiceConfig` 加 `api_key` 字段；`ServicesConfig` 加 `memory` |
| `pi_llm_server/services/memory.py` | 新增 | MemoryService 类（Client + Router） |
| `pi_llm_server/services/__init__.py` | 修改 | 导出 memory 模块 |
| `pi_llm_server/server.py` | 修改 | 导入、lifespan shutdown、init、register |

### 4.2 config.py 变更

- `ServiceConfig` 新增 `api_key: Optional[str] = None` — memory 服务复用 `ServiceConfig`
- `ServicesConfig` 新增 `memory: Optional[ServiceConfig] = None`
- `_build_service_configs` 加入 `self.services.memory`

### 4.3 services/memory.py

`MemoryService` 类遵循项目既有的 `Client + Router` 模式：

- `__init__`：创建 `httpx.AsyncClient`，配置 `base_url`/`timeout`/`limits`
- `_proxy_request`：通用代理方法，字典映射 GET/POST/DELETE/PATCH，统一重试循环
- `health_check`：调用后端 `/health`，供健康监控使用
- `get_models`：返回 memory/knowledge 服务标识
- `_register_routes`：注册 9 个端点（6 个记忆管理 + 3 个知识库）
- `close`：关闭 httpx 客户端

### 4.4 server.py 变更

4 处修改：
1. 导入 `init_memory_service` / `get_memory_service`
2. `lifespan` shutdown 中加入 memory 客户端关闭
3. `initialize_services` 中加入 memory 初始化
4. `register_services` 和 `list_models` 中加入 memory

### 4.5 services/__init__.py 变更

新增导出 `MemoryService`、`init_memory_service`、`get_memory_service`

---

## 五、YAML 配置示例

```yaml
services:
  memory:
    enabled: true
    base_url: http://agent.adv-ci.com:9873
    timeout_seconds: 30
    max_retries: 3
    api_key: "your-memory-api-key"  # 可选，如果 pi-memory 没开认证则不需要
```

---

## 六、不需要做的事情

1. **不需要队列集成**（memory 搜索/存储操作轻量，不需要排队）
2. **不需要守护进程管理**（pi-memory 是独立 Node.js 服务，不由 pi-llm-server 启动）
3. **不需要改造响应格式**（原样透传 `{ success, data }` 格式）
4. **不需要 MCP 代理**（只代理 REST API，MCP 端点保持独立访问）
5. **不需要 `/v1/` 前缀**（保持 `/memory/` 前缀区分于现有 OpenAI 兼容 API）

---

## 七、风险点

1. **路径冲突**：`/memory/*` 路由不会与现有 `/health`、`/v1/*` 等冲突
2. **API Key 存储**：`api_key` 存在 YAML 配置中，明文存储，与现有服务保持一致
3. **业务错误透传**：pi-memory 返回 HTTP 200 + `{ "success": false, "error": "..." }` 时原样返回，网关不额外包装
