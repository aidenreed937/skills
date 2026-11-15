# 知乎观察（Zhihu Observer）指南与数据契约

适用于公共事件、重大工程、文化作品（游戏/影视/书籍）、行业争议或热门议题。
核心目标是：**做一页有锋芒、有深度的「知乎深水区观点策展」——先用一手事实立住当前进展，再把知乎内行答主最硬核的拆解、算账与正反交锋原汁原味呈现出来。**

## 核心打法

**知乎深水区策展与观点交锋**：围绕核心争点组织正反阵营与多维视角，突出答主背景、赞同数与原话金句

通用检索方法见 [知乎好回答深挖四步法](zhihu-research-common.md#知乎好回答深挖四步法研究与复杂搜索任务通用)。

## 默认双产物（输出到任务目录 `$RUN_DIR`）

完整专题综述 `report.md` + 观点交锋策展页 `index.html`<br>（调用 `scripts/zhihu-research-render.py`）

---

## 一、怎么搜出知乎的「神回答」与真交锋

1. **先用 `question recommend` 找核心母问题**
   - `zhihu-cli question recommend --query "主题词" --count 10`（若是当下热点，配合 `zhihu-cli hot --limit 30`）。
2. **用 `question answers` + 多路 `search zhihu` 捞出高赞与对立视角**
   - 对 1–2 个最核心的母问题 URL，调用 `zhihu-cli question answers --question-url "..." --limit 20` 横向扫一遍不同答主的切入点。
   - 再用 `zhihu-cli search zhihu --query "..." --count 10` 搜 3–4 个具体切面（工程算账、专业科普、口碑分歧、亲历见闻）。
3. **用 `search global` 锚定客观事实底座**
   - 用 1–2 次 `zhihu-cli search global` 核实关键时间节点、官方公布数据或最新阶段，作为「当前状态」与「进展速览」底座。

### 看点设计原则
- **看点标题直击真问题与真冲突**：不要写《货源情况分析》这种温吞目录，要写《省下 50 亿运费，还是货源根本吃不饱？》。
- **正反交锋并置**：把算账逻辑不同的两派代表作放进同一看点下，用 `"layout": "compare"` 正面对撞，每张卡片亮出**答主姓名 + 身份标签（`role`） + 立场标签（`stance`） + 赞同数（`votes`） + 80–220 字精辟原话选摘**。

---

## 二、双产物交付：`report.md` + `index.html`

1. **生成完整的 `$RUN_DIR/report.md`（专题深度综述）**
   - 包含：一句话现状与核心看点对账表、关键进展时间线、各看点下的多方观点综述与答主原话摘录、仍待观察的悬念及全部原文链接。
2. **编写 `$RUN_DIR/page.json` 并渲染 `$RUN_DIR/index.html`**

### `page.json` 结构规范（单文件内嵌 `sources`）
```json
{
  "type": "observer",
  "title": "主题名",
  "subtitle": "一句话点破本页核心看点与争议",
  "as_of": "2026-11-11",
  "summary_card": {
    "verdict": "一句话总结当前大局与最核心的分歧交锋点",
    "points": [
      {"label": "核心争点 1", "value": "正方怎么算账 vs 反方指出什么死穴"},
      {"label": "核心争点 2", "value": "纸面预期 vs 一线实际体感"},
      {"label": "关键变量", "value": "决定后续走向的 1 个关键指标"}
    ],
    "highlights": [
      {"author": "答主名", "role": "一线从业者/专业背景", "quote": "一句一针见血的原话金句"}
    ],
    "stats": "本页汇集 12 篇知乎深度拆解 × 4 份官方一手通报"
  },
  "current_state": {
    "summary": "当前阶段与核心客观事实底座",
    "source_ids": ["S1"]
  },
  "progress": [
    {"date": "2026-10-20", "text": "关键进展节点", "source_ids": ["S1"]}
  ],
  "viewpoints": [
    {
      "id": "view-1",
      "title": "有锋芒的真问题标题",
      "layout": "compare",
      "summary": "这组讨论在争什么：共同事实是什么，双方分歧的根源在哪",
      "source_ids": ["S1", "S2"],
      "cards": [
        {
          "source_id": "S2",
          "stance": "乐观派 · 算产业转移账",
          "role": "区域经济研究者",
          "votes": 630,
          "text": "答主最硬核的论据或原话选摘（80–220字）"
        }
      ]
    }
  ],
  "open_questions": ["接下来最值得继续观察的悬念"],
  "sources": [
    {
      "id": "S1",
      "title": "来源标题",
      "url": "https://...",
      "author": "作者或机构名",
      "role": "身份标签（可选）",
      "votes": 630,
      "published_at": "2026-10-20"
    },
    {"id": "S2", "title": "知乎回答示例", "url": "https://www.zhihu.com/question/123/answer/456", "author": "答主名"}
  ]
}
```
- 看点 `id` 以英文字母开头，唯一且不与保留字（`top`, `main`, `state`, `progress`, `sources`, `next`）重名。
- 卡片既可通过 `source_id` 关联 `sources`，也可直接在卡片上写 `url`、`title`、`author`。

### 渲染命令
```bash
python3 "$SKILL_ROOT/scripts/zhihu-research-render.py" --page "$RUN_DIR/page.json" --output "$RUN_DIR/index.html"
```
