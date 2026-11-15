# 知乎数据开放平台

核验时间：2026-08-25

## 平台是什么

知乎数据开放平台向开发者和 Agent 提供知乎搜索、全网搜索、知乎热榜和知乎直答能力。使用者可以通过统一 CLI、原始 HTTP API 或平台已经提供的 MCP 服务调用。

## 注册和领取 Access Secret

1. 访问知乎开放平台个人中心：<https://developer.zhihu.com/profile>
2. 使用知乎账号登录。
3. 点击「申请新 Access Secret」。
4. 获取 Access Secret 后，通过 Agent 执行：

```bash
zhihu-cli auth set --secret-stdin
```

Agent 应通过进程标准输入传入用户在对话中提供的 Access Secret，不要求用户介入终端交互。

开放平台后台的鉴权凭证统一称为 **Access Secret**。HTTP 请求使用：

```http
Authorization: Bearer <your_access_secret>
X-Request-Timestamp: <Unix 秒级时间戳>
```

不要在回答、日志或文件中重复完整 Access Secret。CLI 配置完成后只显示脱敏信息和验证状态。

## 查询额度与用量

额度以当前账号的实时查询结果为准：

- 网页：打开[个人中心](https://developer.zhihu.com/profile)，查看「用量统计」。
- CLI：运行 `zhihu-cli quota` 查看当前账号的各项 API 额度；只查全网搜索时运行 `zhihu-cli quota --api-id global_search`。更多筛选方式见 [CLI 使用文档](cli.md#查询额度)。

CLI 返回的 `TotalQuota`、`TotalUsed`、`RemainingQuota` 分别表示当前自然日总额度、已用额度和剩余额度；查询本身不消耗业务额度。

- 同一账号下所有 Access Secret 共享该账号的额度。
- 页面效果测试与 API 直接调用共享该账号的额度。
- 免费额度用完后，是否可继续付费调用及计费方式请查看[服务价格文档](https://developer.zhihu.com/docs?key=billing_price)。

## Access Secret 使用规则

- 单个账号最多可申请 20 个 Access Secret。
- Access Secret 是账号的 API 调用凭证，不要泄露给无关人员；可调用范围以账号实际授权为准。
- 删除 Access Secret 后无法恢复；相关调用记录仍保留用于额度计算。

## 常见问题

### 如何申请 API 访问权限？

通过邮件联系开放平台，提供使用场景和预估调用量。平台将在 1 个工作日内处理申请。

### API 如何计费？

服务价格及计费说明请查看[服务价格文档](https://developer.zhihu.com/docs?key=billing_price)。

### 是否支持流式输出？

知乎直答 API 支持流式输出，在请求参数中设置 `stream: true`。知乎搜索、全网搜索和热榜暂不支持流式输出。

### Access Secret 无效或需要更换怎么办？

在个人中心申请或管理 Access Secret，然后重新执行：

```bash
zhihu-cli auth set --secret-stdin
```

CLI 应先在线验证新 Access Secret，再替换系统密钥链中的旧 Access Secret。

## 联系方式

- 邮箱：<openplatform@zhihu.com>
- 工作时间：周一至周五 09:00-18:00（北京时间）
- 回复时效：1 个工作日内

适用场景：API 接入咨询、访问权限申请、商务合作和技术问题。

## 相关入口

- 开放平台：<https://developer.zhihu.com/>
- 文档中心：<https://developer.zhihu.com/docs>
- 个人中心与 Access Secret 申请：<https://developer.zhihu.com/profile>
