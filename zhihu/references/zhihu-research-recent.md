# 近况速览（Recent Brief）指南与数据契约

适用于追踪某个明确产品、技术、开源项目、公司或行业议题在最近一段时间（默认最近 30 天，或用户指定窗口）的**关键新动作与社区风向**。
核心目标是：**用全网实时检索抓「官方/行业刚发布了什么新变化」，用知乎检索抓「一线开发者与内行对这些变化怎么看、实测踩了什么坑」。**

## 核心打法

**全网抓近期新动作 × 知乎抓深解读与实测反馈**：先用全网实时索引锁定近期新动作，再去知乎搜内行拆解与实测反馈

通用检索方法见 [知乎好回答深挖四步法](zhihu-research-common.md#知乎好回答深挖四步法研究与复杂搜索任务通用)。

## 默认双产物（输出到任务目录 `$RUN_DIR`）

近期动态综述 `report.md` + 时间线动态速览页 `index.html`<br>（调用 `scripts/zhihu-research-render.py`）

---

## 一、两段式检索法：全网抓「新」，知乎抓「深」

`zhihu-cli search global` 支持 `--search-db realtime` 抓取全网最新网页与公告；而 `zhihu-cli search zhihu` 按相关性与内容质量召回。因此要采用**「先全网定新事件，再知乎搜深评价」**两段法：

1. **第一步：用全网搜索锁定窗口内的真实新动作**
   - 读取系统日期，确定观察窗口（如默认过去 30 天）。
   - 调用 `zhihu-cli search global --query "主题 关键词" --search-db realtime --count 20`（可配合 `--filter 'host=="..."'`），找出窗口内发生的重要发布、版本更新、财报或临床/政策进展。
2. **第二步：带着具体的新特性/新事件名称，去知乎搜内行解读与实测**
   - 拿到第一步的具体事件/特性词后，调用 `zhihu-cli question recommend`、`zhihu-cli question answers` 和 `zhihu-cli search zhihu --count 10`，检索知乎内行对该新动作的源码拆解、临床/工程实测与背景对比（若为大众热点可配合 `zhihu-cli hot`）。
   - 提炼 3–5 项**真正改变使用方式、技术取舍或行业格局的核心变化**，每项讲清：① 到底变了什么（附日期）；② 为什么重要；③ 知乎内行给出了什么实测反馈或边界提醒。

---

## 二、双产物交付：`report.md` + `index.html`

1. **生成完整的 `$RUN_DIR/report.md`（近期动态与风向报告）**
   - 包含：观察窗口与一句话风向综述、本期关键变化与内行对账总表、逐项变化深度解读与知乎代表观点、关键时间线、后续关注点及完整来源链接。
2. **编写 `$RUN_DIR/page.json` 并渲染 `$RUN_DIR/index.html`**

### `page.json` 结构规范（单文件内嵌 `sources`）
```json
{
  "type": "recent-brief",
  "title": "主题近况标题",
  "subtitle": "核心变化切面说明",
  "as_of": "2026-11-11",
  "window": {"start": "2026-10-13", "end": "2026-11-11"},
  "status": "active",
  "lead": "用两三句话概括本期最重要的动作与社区实测风向",
  "summary_card": {
    "verdict": "一句话点透本期最重要的风向变化",
    "points": [
      {"label": "关键动作 1", "value": "发生了什么 + 对用户的直接影响"},
      {"label": "关键动作 2", "value": "发生了什么 + 对用户的直接影响"},
      {"label": "内行实测风向", "value": "知乎高赞实测揭示的最大亮点或隐患"}
    ],
    "highlights": [
      {"author": "答主名", "role": "专业背景", "quote": "一句代表性内行评价"}
    ],
    "stats": "覆盖 2026-10-13 至 11-11 · 核对 5 份官方发布 × 8 篇知乎实测拆解"
  },
  "changes": [
    {
      "id": "change-1",
      "title": "具体变化标题（直指核心动作与影响）",
      "what_changed": "完整说明变了什么、为什么重要、在实际使用中要注意什么",
      "date": "2026-10-29",
      "source_ids": ["S1"],
      "feedback": [
        {
          "source_id": "S2",
          "role": "大模型推理工程师",
          "votes": 200,
          "stance": "源码实测",
          "text": "知乎答主针对该变化的实测反馈、源码拆解或踩坑提醒"
        }
      ],
      "uncertainty": "可选：适用版本或边界条件提醒"
    }
  ],
  "timeline": [
    {"date": "2026-10-29", "title": "关键节点简述", "source_ids": ["S1"]}
  ],
  "background": [
    {"text": "理解本期变化所需的历史背景或技术前提", "source_ids": ["S3"]}
  ],
  "next_checks": ["接下来值得继续跟踪的节点"],
  "sources": [
    {
      "id": "S1",
      "title": "官方发布或知乎回答标题",
      "url": "https://...",
      "author": "作者或机构名",
      "role": "身份标签（可选）",
      "votes": 200,
      "published_at": "2026-10-29"
    },
    {"id": "S2", "title": "知乎回答示例", "url": "https://www.zhihu.com/question/123/answer/456", "author": "答主名"},
    {"id": "S3", "title": "背景资料示例", "url": "https://example.com/background"}
  ]
}
```
- `changes` 中的日期可直接填 `"date": "YYYY-MM-DD"`（同时向下兼容 `time_basis` + `event_date` / `published_at` / `updated_at`）。
- `timeline` 中的 `time_type` 可选（默认 `"event"`）。

### 渲染命令
```bash
python3 "$SKILL_ROOT/scripts/zhihu-research-render.py" --page "$RUN_DIR/page.json" --output "$RUN_DIR/index.html"
```
