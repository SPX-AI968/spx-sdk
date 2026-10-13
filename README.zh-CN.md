# Simplex AI Python SDK

用于调用 Simplex CD 决策模型，支持同步与异步请求、四类决策、图片编码、参数校验和结构化返回值。

[English](README.md) · [API 文档](https://simplexai.net/zh/platform/docs) · [创建 Access Token](https://simplexai.net/zh/platform/keys)

## 安装

需要 Python 3.10 或更新版本。首次发布到 PyPI 前，请从仓库安装：

```bash
pip install git+https://github.com/SPX-AI968/spx-sdk.git
```

发布后使用 `pip install simplex-ai-sdk`，导入名为 `simplex_ai`。不要安装 `spx-sdk`，该 PyPI 名称属于其他项目。

## 快速开始

在服务端环境设置 `SIMPLEX_API_TOKEN`，然后调用：

```python
from simplex_ai import Choice, ChoiceAnswer, SimplexClient

with SimplexClient() as client:
    result = client.system_one(
        model="spx-cd-auto",
        state={"message": "订单重复扣款，请退回多扣的金额。"},
        questions={
            "route": Choice(
                instructions="选择处理部门。",
                criteria={"billing": "账单与退款", "support": "技术支持"},
            )
        },
    )
    answer = result.answers["route"]
    if isinstance(answer, ChoiceAnswer):
        print(answer.choice, answer.probabilities)
    print(result.usage)
```

也可通过 `SimplexClient(api_key="…")` 显式传入 Token。不要把 Token 放入浏览器代码或提交到仓库。默认地址为 `https://api.simplexai.net`，可用 `base_url` 或 `SIMPLEX_API_BASE` 修改；只填写源地址，不带 `/v1`。远程地址须使用 HTTPS。

## 决策类型

| 类型 | 输入 | 返回字段 |
| --- | --- | --- |
| `Choice` | 候选名称到说明的字典 | `choice`：单个候选名称 |
| `MultiChoice` | 候选字典，可设 `min_choices` / `max_choices` | `choices`：候选名称列表 |
| `Noul` | 判断问题，可设 true/false 的说明 | `noul`：是的概率 |
| `Score` | 从低到高的有序说明列表 | `score`：从 0 开始的期望索引 |

`questions` 也支持带 `type` 字段的普通字典。Simplex CD 的 `state` 支持任意 JSON 值。概率与置信度原样保留，不重新计算；用量未知时保留 `None`，不当作 0。完整返回值可用 `result.model_dump()` 获取。

支持 `spx-cd`（默认）、`spx-cd-auto`、`spx-cd-flash`、`spx-cd-pro`。调用 `client.models()` 查看服务端当前模型与限制。Jev 使用 `typesafe-ai/jev`，支持文本单选、判断与评分，不支持图片、多选或推理；评分至少需要两个候选档位。

## 图片与限制

```python
from simplex_ai import Image

image = Image.from_file("scene.png")
# 在 system_one 中传入 images=[image]
# 内存图片：Image.from_bytes(data, media_type="image/png")
```

最多 4 张，支持 PNG、JPEG、WebP、GIF；单张不超过 2,000,000 字节，包含 base64 的完整 JSON 请求不超过 15,000,000 字节。超限会在发送前报错，不会悄悄压缩或删除图片。不抓取远程图片 URL。SDK 校验大小与编码，不检查图片是否能解码或像素尺寸。

每次请求 1–64 道问题，每道单选、多选或评分问题最多 1024 个候选。多选最多返回 10 项。上下文 token 限制由服务端检查；字节数不等于 token 数。

## 异步与异常

使用 `AsyncSimplexClient`，通过 `async with` 管理连接，`await client.system_one(...)` 发起请求。接口参数与同步客户端一致。默认超时 120 秒，可通过 `timeout` 调整。

参数错误抛出 `ValueError` / Pydantic `ValidationError`。HTTP 错误为 `APIError`，含 `status_code`、`request_id` 和 `body`；401/403 为 `AuthenticationError`，429 为 `RateLimitError`，可读取 `retry_after`。连接或超时错误为 `APIConnectionError` / `APITimeoutError`，无法解析响应为 `APIResponseError`。

SDK 不自动重试、不跟随重定向。超时不代表模型一定未执行，重试前应核对调用记录。自定义网络 transport 的重试策略由调用方负责。

<details>
<summary>高级参数：effort（日常使用不推荐）</summary>

`effort` 接受 1–5 的整数，默认 1。日常使用不推荐提高 effort：更高值增加候选顺序评估次数与延迟，输入用量按相应 1–5 倍计费，不保证效果更好。仅在明确的实验中设置更高值，SDK 会发出提醒。返回的 `usage.input_tokens` 已包含全部评估轮次，不要再次乘以 effort。该参数适用于 SPX-CD；Jev 仅接受 1。旧的 `reasoning`、`reasoning_max_tokens` 参数已移除。

</details>

完整同步、多问题、图片与异步示例见 [英文文档](README.md)。开发及手动发布步骤见 [RELEASING.md](RELEASING.md)。
