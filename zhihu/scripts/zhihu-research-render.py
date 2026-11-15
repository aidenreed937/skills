#!/usr/bin/env python3
"""Unified HTML renderer for Zhihu Research (deep-research articles, observer pages, and recent-brief pages).

Usage:
  1) Deep Research Article (Markdown + optional visuals.json -> HTML):
     python3 zhihu-research-render.py report.md index.html --as-of YYYY-MM-DD [--visuals visuals.json] [--markdown-link report.md]

  2) Observer / Recent Brief Page (page.json -> HTML):
     python3 zhihu-research-render.py --page page.json --output index.html
     (or positional: python3 zhihu-research-render.py page.json index.html)
"""
from __future__ import annotations
import argparse
from datetime import date, datetime
import hashlib
import html
from html.parser import HTMLParser
import ipaddress
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit

ASSETS = Path(__file__).resolve().parents[1] / "assets"
PAGE_TYPES = ("observer", "recent-brief")
VISUAL_KINDS = {"process", "comparison", "scenario", "mechanism", "timeline", "spatial", "chart", "evidence", "custom"}
LABELS = {"event": "事件时间", "publication": "发布时间", "edit": "更新时间"}


class Invalid(ValueError):
    pass


def require(value, message):
    if not value:
        raise Invalid(message)
    return value


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def esc(value):
    return html.escape(str(value if value is not None else ""), quote=True)


e = esc


def render_summary_card(summary_card, scenario_name="深度研究"):
    if not isinstance(summary_card, dict) or not summary_card.get("verdict"):
        return ""
    verdict = esc(summary_card["verdict"])
    points_html = ""
    if isinstance(summary_card.get("points"), list) and summary_card["points"]:
        items = []
        for pt in summary_card["points"]:
            if isinstance(pt, dict) and pt.get("label") and pt.get("value"):
                items.append(
                    f'<div class="summary-point"><span class="summary-point-label">{esc(pt["label"])}</span>'
                    f'<div class="summary-point-value">{esc(pt["value"])}</div></div>'
                )
        if items:
            points_html = f'<div class="summary-points">{"".join(items)}</div>'
    highlights_html = ""
    if isinstance(summary_card.get("highlights"), list) and summary_card["highlights"]:
        hl_items = []
        for hl in summary_card["highlights"]:
            if isinstance(hl, dict) and hl.get("quote"):
                who = esc(hl.get("author") or "知乎答主")
                role = f'（{esc(hl["role"])}）' if hl.get("role") else ""
                hl_items.append(f'<div class="summary-highlight"><strong>@{who}{role}：</strong>“{esc(hl["quote"])}”</div>')
        if hl_items:
            highlights_html = f'<div class="summary-highlights">{"".join(hl_items)}</div>'
    stats = esc(summary_card.get("stats") or f"知乎研究 · {scenario_name}")
    return (
        f'<section class="summary-card" aria-label="核心看点与对账速览">'
        f'<div class="summary-eyebrow"><span>核心看点与对账速览</span><span>{esc(scenario_name)}</span></div>'
        f'<p class="summary-verdict">{verdict}</p>{points_html}{highlights_html}'
        f'<div class="summary-footer"><span>{stats}</span><span>知乎开放平台 · 智能搜索</span></div></section>'
    )


# ============================================================================
# Part 1: Observer & Recent Brief JSON Page Renderer
# ============================================================================

def author_name(source):
    if nonempty(source.get("author")):
        return source["author"].strip()
    return "知乎用户"


def format_votes(val):
    if val is None or val == "":
        return ""
    if isinstance(val, (int, float)):
        if int(val) <= 0:
            return ""
        return f"▲ {int(val):,} 赞"
    s = str(val).strip()
    if not s or s == "0":
        return ""
    if s.isdigit():
        return f"▲ {int(s):,} 赞"
    return s if "赞" in s or "▲" in s else f"▲ {s} 赞"


def string(obj, key, where, optional=False):
    value = obj.get(key)
    if optional and (value is None or value == ""):
        return ""
    require(nonempty(value), f"{where}.{key}: expected nonempty text")
    return value.strip()


def seq(obj, key, where, optional=False):
    value = obj.get(key, [] if optional else None)
    require(isinstance(value, list), f"{where}.{key}: expected array")
    return value


def object_(value, where):
    require(isinstance(value, dict), f"{where}: expected object")
    return value


def iso(value, where):
    require(nonempty(value), f"{where}: expected ISO date or timestamp")
    try:
        if len(value) == 10:
            return date.fromisoformat(value)
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.date()
    except ValueError:
        raise Invalid(f"{where}: invalid ISO date or timestamp {value!r}") from None


def display_time(value):
    if len(value) == 10:
        return value
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    zone = parsed.strftime("%z")
    zone = " " + zone[:3] + ":" + zone[3:] if zone else ""
    return parsed.strftime("%Y-%m-%d %H:%M") + zone


def time_tag(value):
    return f'<time datetime="{esc(value)}" title="{esc(value)}">{esc(display_time(value))}</time>'


def public_url(value, where):
    require(nonempty(value), f"{where}: missing URL")
    parsed = urlsplit(value)
    require(
        parsed.scheme in ("https", "http") and parsed.hostname and not parsed.username and not parsed.password,
        f"{where}: expected public http(s) URL without credentials",
    )
    host = parsed.hostname.lower()
    require(
        host not in ("localhost", "localhost.localdomain") and "." in host and not host.endswith((".local", ".internal")),
        f"{where}: expected public hostname",
    )
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    require(address is None or address.is_global, f"{where}: private IP is not a public source")
    return value


def resolve_change_date(item, where="changes"):
    basis = item.get("time_basis") or "event"
    require(basis in ("event", "publication", "edit"), f"{where}.time_basis: expected event, publication or edit")
    date_key = {"event": "event_date", "publication": "published_at", "edit": "updated_at"}[basis]
    raw = item.get("date") or item.get(date_key) or item.get("event_date") or item.get("published_at") or item.get("updated_at")
    require(nonempty(raw), f"{where}: expected 'date' (or {date_key}) in ISO format")
    iso(raw, where + ".date")
    return basis, raw


def load_sources(page, path):
    # 1、读取来源并检查标识、链接和日期，避免报告引用无法追溯的记录。
    data = json.loads(path.read_text(encoding="utf-8")) if path else page.get("sources", [])
    if isinstance(data, dict):
        data = data.get("sources", [])
    require(isinstance(data, list), "provide --sources SOURCES_JSON or page.sources array")
    result = {}
    for n, source in enumerate(data):
        where = f"sources[{n}]"
        object_(source, where)
        sid = string(source, "id", where)
        require(sid not in result, f"{where}: duplicate ID {sid}")
        public_url(source.get("url"), where + ".url")
        string(source, "title", where)
        require(source.get("author") is None or isinstance(source.get("author"), str), f"{where}.author: expected text or null")
        for key in ("published_at", "updated_at", "retrieved_at"):
            if source.get(key):
                iso(source[key], where + "." + key)
        result[sid] = source

    # 2、将卡片内联来源统一登记，后续校验与渲染复用同一份来源表。
    auto_idx = 1

    def register_inline(item, where):
        nonlocal auto_idx
        if not isinstance(item, dict):
            return
        if not item.get("source_id") and item.get("url") and item.get("title"):
            public_url(item.get("url"), where + ".url")
            sid = f"inline-{auto_idx}"
            while sid in result:
                auto_idx += 1
                sid = f"inline-{auto_idx}"
            auto_idx += 1
            result[sid] = {
                "id": sid,
                "url": item["url"].strip(),
                "title": item["title"].strip(),
                "author": item.get("author"),
                "role": item.get("role") or item.get("author_role"),
                "votes": item.get("votes") if item.get("votes") is not None else item.get("voteup_count"),
            }
            item["source_id"] = sid

    for vp in page.get("viewpoints", []) if isinstance(page.get("viewpoints"), list) else []:
        if isinstance(vp, dict) and isinstance(vp.get("cards"), list):
            for idx, c in enumerate(vp["cards"]):
                register_inline(c, f"viewpoints.cards[{idx}]")
    for ch in page.get("changes", []) if isinstance(page.get("changes"), list) else []:
        if isinstance(ch, dict) and isinstance(ch.get("feedback"), list):
            for idx, c in enumerate(ch["feedback"]):
                register_inline(c, f"changes.feedback[{idx}]")
    return result


def validate_page(page, sources):
    # 1、检查页面类型、截止日期与公共字段，引用必须对应已登记来源。
    require(page.get("type") in PAGE_TYPES, f"page.type must be one of {PAGE_TYPES!r}")
    page_type = page["type"]
    string(page, "title", "page")
    as_of = iso(page.get("as_of"), "page.as_of")
    seen = set()

    def refs(obj, where, optional=True):
        values = seq(obj, "source_ids", where, optional=True)
        require(optional or values, f"{where}.source_ids: at least one citation required")
        for sid in values:
            require(isinstance(sid, str) and sid in sources, f"{where}: unresolved source ID {sid!r}")
        return values

    def card(item, where):
        object_(item, where)
        sid = string(item, "source_id", where)
        require(sid in sources, f"{where}: unresolved source ID {sid!r}")
        mode = item.get("mode", "quote")
        require(mode in ("quote", "excerpt", "summary"), f"{where}.mode: expected quote, excerpt or summary")
        string(item, "text", where)

    def unique_id(item, where):
        identity = string(item, "id", where)
        require(re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_-]*", identity), f"{where}.id: use ASCII letter followed by letters, digits, _ or -")
        require(identity not in seen, f"{where}.id: duplicate section ID {identity}")
        require(
            identity not in ("top", "main", "state", "progress", "sources", "background", "timeline", "next", "collection-search", "collection-results")
            and not identity.startswith("source-"),
            f"{where}.id: reserved ID or source namespace {identity}",
        )
        seen.add(identity)

    for key in ("subtitle", "edition_label", "scope_note"):
        if page.get(key) is not None:
            require(isinstance(page[key], str), f"page.{key}: expected text")
    for key in ("open_questions", "next_checks"):
        for n, item in enumerate(seq(page, key, "page", True)):
            require(nonempty(item), f"page.{key}[{n}]: expected text")
    # 2、按场景验证观点、观察窗口和日期；事件时间不得晚于报告截止日期。
    if page_type == "observer":
        state = object_(page.get("current_state"), "current_state")
        string(state, "summary", "current_state")
        refs(state, "current_state", optional=True)
        viewpoints = seq(page, "viewpoints", "page")
        require(viewpoints, "page.viewpoints: include material-driven viewpoints")
        for n, item in enumerate(viewpoints):
            where = f"viewpoints[{n}]"
            object_(item, where)
            unique_id(item, where)
            string(item, "title", where)
            require(item.get("layout", "list") in ("list", "compare"), f"{where}.layout: expected list or compare")
            string(item, "summary", where, True)
            refs(item, where, optional=True)
            cards = seq(item, "cards", where)
            require(cards, f"{where}.cards: at least one source card required")
            for j, value in enumerate(cards):
                card(value, f"{where}.cards[{j}]")
        for n, item in enumerate(seq(page, "progress", "page", True)):
            where = f"progress[{n}]"
            object_(item, where)
            require(iso(item.get("date"), where + ".date") <= as_of, f"{where}: date is after as_of")
            tt = item.get("time_type", "event")
            require(tt in ("event", "publication", "edit"), f"{where}.time_type: expected event, publication or edit")
            string(item, "text", where)
            refs(item, where, optional=True)
    else:
        window = object_(page.get("window"), "window")
        start = iso(window.get("start"), "window.start")
        end = iso(window.get("end"), "window.end")
        require(start <= end <= as_of, "window must satisfy start <= end <= as_of")
        status = page.get("status", "active")
        require(status in ("active", "quiet", "thin"), "page.status: expected active, quiet or thin")
        string(page, "lead", "page")
        changes = seq(page, "changes", "page")
        require(status != "active" or changes, "active brief requires at least one change")
        for n, item in enumerate(changes):
            where = f"changes[{n}]"
            object_(item, where)
            unique_id(item, where)
            string(item, "title", where)
            string(item, "what_changed", where)
            refs(item, where, optional=True)
            _, raw_date = resolve_change_date(item, where)
            require(iso(raw_date, where + ".date") <= as_of, f"{where}.date: after as_of")
            if item.get("uncertainty") is not None:
                string(item, "uncertainty", where, True)
            for j, value in enumerate(seq(item, "feedback", where, True)):
                card(value, f"{where}.feedback[{j}]")
        for n, item in enumerate(seq(page, "timeline", "page", True)):
            where = f"timeline[{n}]"
            object_(item, where)
            when = iso(item.get("date"), where + ".date")
            require(when <= as_of, f"{where}: timeline date is after as_of")
            tt = item.get("time_type", "event")
            require(tt in ("event", "publication", "edit"), f"{where}.time_type: expected event, publication or edit")
            string(item, "title", where)
            refs(item, where, optional=True)
        for n, item in enumerate(seq(page, "background", "page", True)):
            where = f"background[{n}]"
            object_(item, where)
            string(item, "text", where)
            refs(item, where, optional=True)


def update_dates(item, timeline):
    basis, raw_date = resolve_change_date(item)
    values = {iso(raw_date, "date")}
    ids = set(item.get("source_ids") or [])
    for row in timeline or []:
        row_type = row.get("time_type", "event")
        if row_type == basis and ids and ids.intersection(row.get("source_ids") or []):
            values.add(iso(row["date"], "timeline.date"))
    return min(values).isoformat(), max(values).isoformat()


class PageRenderer:
    def __init__(self, page, sources):
        self.page = page
        selected = set()

        def collect(value):
            if isinstance(value, dict):
                if isinstance(value.get("source_id"), str):
                    selected.add(value["source_id"])
                if isinstance(value.get("source_ids"), list):
                    selected.update(x for x in value["source_ids"] if isinstance(x, str))
                for key, child in value.items():
                    if key != "sources":
                        collect(child)
            elif isinstance(value, list):
                for child in value:
                    collect(child)

        collect(page)
        self.sources = {sid: source for sid, source in sources.items() if sid in selected}
        self.numbers = {sid: n + 1 for n, sid in enumerate(self.sources)}

    def citations(self, values):
        if not values:
            return ""
        return (
            '<span class="citations" aria-label="来源">'
            + "".join(
                f'<a href="#source-{self.numbers[sid]}" aria-label="来源 {self.numbers[sid]}">[{self.numbers[sid]}]</a>'
                for sid in values
                if sid in self.numbers
            )
            + "</span>"
        )

    def source_links(self, values):
        if not values:
            return ""
        cards = []
        for sid in values:
            if sid not in self.sources:
                continue
            source = self.sources[sid]
            role = source.get("role") or source.get("author_role")
            byline = f"{author_name(source)} · {role}" if role else author_name(source)
            cards.append(
                f'<a class="reference-card" href="{esc(source["url"])}" target="_blank" rel="noopener noreferrer" '
                f'aria-label="阅读原文：{esc(source["title"])}"><span class="reference-byline">{esc(byline)}</span>'
                f'<strong class="reference-title">{esc(source["title"])}</strong>'
                f'<span class="reference-bottom"><span>{esc(urlsplit(source["url"]).hostname)}</span>'
                f'<span>阅读原文 <b aria-hidden="true">↗</b></span></span></a>'
            )
        return '<div class="evidence-links">' + "".join(cards) + "</div>" if cards else ""

    def card(self, card):
        source = self.sources[card["source_id"]]
        mode = card.get("mode", "quote")
        tag = "blockquote" if mode == "quote" else "p"
        text = esc(card["text"])
        author = author_name(source)
        role = card.get("role") or card.get("author_role") or source.get("role") or source.get("author_role")
        stance = card.get("stance")
        votes = (
            card.get("votes")
            if card.get("votes") is not None
            else (
                card.get("voteup_count")
                if card.get("voteup_count") is not None
                else (source.get("votes") if source.get("votes") is not None else source.get("voteup_count"))
            )
        )
        role_html = f'<span class="role-badge">{esc(role)}</span>' if nonempty(role) else ""
        stance_html = f'<span class="stance-badge">{esc(stance)}</span>' if nonempty(stance) else ""
        vote_str = format_votes(votes)
        vote_html = f'<span class="vote-badge">{esc(vote_str)}</span>' if vote_str else ""
        return (
            f'<a class="source-card {mode}" href="{esc(source["url"])}" target="_blank" rel="noopener noreferrer" '
            f'aria-label="阅读原文：{esc(source["title"])}">'
            f'<div class="card-byline"><span class="author">{esc(author)}</span>{role_html}{stance_html}{vote_html}</div>'
            f'<h3>{esc(source["title"])}</h3><{tag} class="card-text">{text}</{tag}>'
            f'<div class="card-bottom"><span>{esc(urlsplit(source["url"]).hostname)}</span><span>阅读原文 ↗</span></div></a>'
        )

    def toc(self, entries):
        return (
            '<details class="contents topic-navigation" open><summary>浏览主题</summary><nav aria-label="专题分区">'
            + "".join(f'<a href="#{esc(key)}">{esc(title)}</a>' for key, title in entries)
            + "</nav></details>"
        )

    def browse_tools(self, count, noun):
        return (
            f'<div class="browse-tools" hidden><div class="search-field"><label for="collection-search">在本页查找</label>'
            f'<input id="collection-search" type="search" autocomplete="off" placeholder="搜索标题、作者或内容" aria-controls="collection-results">'
            f'<button type="button" class="clear-search" hidden>清除</button></div>'
            f'<p class="result-count" role="status" aria-live="polite" data-total="{count}" data-noun="{noun}">{count} {noun}</p></div>'
            f'<p class="search-empty" hidden role="status">没有匹配的内容。换一个关键词，或清除搜索查看全部。</p>'
        )

    def sources_drawer(self):
        rows = []
        for sid, source in self.sources.items():
            n = self.numbers[sid]
            dates = "".join(
                f'<span>{label} {time_tag(source[key])}</span>'
                for key, label in (("published_at", "发布"), ("updated_at", "更新"))
                if source.get(key)
            )
            role = source.get("role") or source.get("author_role")
            meta_parts = [author_name(source)]
            if nonempty(role):
                meta_parts.append(role.strip())
            v_str = format_votes(source.get("votes") if source.get("votes") is not None else source.get("voteup_count"))
            if v_str:
                meta_parts.append(v_str)
            rows.append(
                f'<details id="source-{n}" class="source-detail"><summary><span class="source-index">{n:02d}</span>'
                f'<span>{esc(source["title"])}<small>{esc(" · ".join(meta_parts))}</small></span>'
                f'<span class="details-sign" aria-hidden="true">+</span></summary>'
                f'<div class="source-detail-body"><div class="source-dates">{dates}</div>'
                f'<a class="original-url" href="{esc(source["url"])}" target="_blank" rel="noopener noreferrer">{esc(source["url"])} ↗</a></div></details>'
            )
        if not rows:
            rows.append('<p class="empty-sources">暂无参考来源记录。</p>')
        return (
            f'<section id="sources" class="sources-section"><div class="section-heading"><h2>参考来源与原文链接</h2>'
            f'<p>点击展开查看作者与原始链接。</p></div><div class="source-list">{"".join(rows)}</div></section>'
        )

    def next_section(self, values, title):
        if not values:
            return ""
        return f'<section id="next" class="next-section"><h2>{title}</h2><ul>' + "".join(f"<li>{esc(x)}</li>" for x in values) + "</ul></section>"

    def observer(self):
        # 1、组织当前状态、进展与观点卡片，并关联各自来源。
        p = self.page
        topics = p["viewpoints"]
        entries = [(x["id"], x["title"]) for x in topics]
        if p.get("open_questions"):
            entries.append(("next", "仍待观察"))
        entries.append(("sources", "参考来源"))
        state = p["current_state"]
        progress = ""
        if p.get("progress"):
            rows = "".join(
                f'<li><div class="progress-date">{time_tag(x["date"])}<span>{LABELS[x.get("time_type", "event")]}</span></div>'
                f'<p>{esc(x["text"])} {self.citations(x.get("source_ids", []))}</p></li>'
                for x in p["progress"]
            )
            progress = (
                f'<section id="progress" class="progress-section"><details class="progress-disclosure" open>'
                f'<summary><h2>进展速览</h2><span class="expand-sign" aria-hidden="true">+</span></summary>'
                f'<ol class="progress-list">{rows}</ol></details></section>'
            )
        sections = []
        for n, item in enumerate(topics, 1):
            summary = f'<p class="view-summary">{esc(item.get("summary", ""))} {self.citations(item.get("source_ids", []))}</p>' if item.get("summary") else ""
            sections.append(
                f'<section id="{esc(item["id"])}" class="viewpoint topic-group" data-topic="{esc(item["title"])}">'
                f'<header class="view-guide"><div class="view-heading"><span class="view-number" aria-hidden="true">{n:02d}</span>'
                f'<h2>{esc(item["title"])}</h2></div>{summary}</header>'
                f'<div class="card-grid {esc(item.get("layout", "list"))}">'
                + "".join(self.card(x) for x in item["cards"])
                + "</div></section>"
            )
        count = sum(len(x["cards"]) for x in topics)
        summary_html = render_summary_card(p.get("summary_card"), "知乎观察")
        return (
            f'<main id="main">{summary_html}<div class="topic-overview{" has-progress" if progress else ""}">'
            f'<section id="state" class="state-panel"><h2>当前状态</h2>'
            f'<p class="state-text">{esc(state["summary"])} {self.citations(state.get("source_ids", []))}</p></section>{progress}</div>'
            f'{self.toc(entries)}{self.browse_tools(count, "条选材")}'
            f'<div id="collection-results" class="topic-collection">{"".join(sections)}</div>'
            f'{self.next_section(p.get("open_questions", []), "仍待观察")}{self.sources_drawer()}</main>'
        )

    def recent(self):
        # 1、按已校验的观察窗口组织变化、反馈和时间线。
        p = self.page
        entries = [(x["id"], x["title"]) for x in p["changes"]]
        timeline = p.get("timeline")
        if timeline is None:
            timeline = [
                {
                    "date": resolve_change_date(x)[1],
                    "time_type": resolve_change_date(x)[0],
                    "title": x["title"],
                    "source_ids": x.get("source_ids", []),
                }
                for x in p["changes"]
            ]
        if timeline:
            entries.append(("timeline", "时间线"))
        if p.get("background"):
            entries.append(("background", "背景资料"))
        if p.get("next_checks"):
            entries.append(("next", "后续关注"))
        entries.append(("sources", "参考来源"))
        status_key = p.get("status", "active")
        statuses = {
            "active": ("近期核心动向", "本期变化"),
            "quiet": ("近期平稳", "窗口内无重大突变"),
            "thin": ("公开动态较少", "当前公开渠道披露有限"),
        }
        status, note = statuses[status_key]
        status_note = f"<small>{note}</small>" if status_key != "active" else ""
        lead = f'<section id="state" class="brief-lead {esc(status_key)}"><p class="eyebrow">{status}</p><p>{esc(p["lead"])}</p>{status_note}</section>'
        changes = []
        for n, item in enumerate(p["changes"], 1):
            basis, _ = resolve_change_date(item)
            date_rows = "".join(
                f'<span><b>{label}</b>{time_tag(item[key])}</span>'
                for key, label in (("date", "日期"), ("event_date", "事件"), ("published_at", "发布"), ("updated_at", "更新"))
                if item.get(key)
            )
            feedback = (
                '<div class="feedback"><h3>知乎实测与内行反馈</h3><div class="card-grid">'
                + "".join(self.card(x) for x in item["feedback"])
                + "</div></div>"
                if item.get("feedback")
                else ""
            )
            uncertainty = f'<p class="uncertainty"><b>适用边界</b> {esc(item["uncertainty"])}</p>' if item.get("uncertainty") else ""
            first_date, last_date = update_dates(item, p.get("timeline", []))
            date_label = {"event": "事件时间", "publication": "发布时间", "edit": "更新时间"}[basis]
            same_year = first_date[:4] == last_date[:4] == p["window"]["end"][:4]
            first_display = first_date[5:] if same_year else first_date
            last_display = last_date[5:] if same_year else last_date
            date_html = f'<time datetime="{esc(first_date)}" title="{esc(first_date)}">{esc(first_display)}</time>'
            if first_date != last_date:
                date_html += f'<span class="date-range-separator" aria-hidden="true">—</span><time datetime="{esc(last_date)}" title="{esc(last_date)}">{esc(last_display)}</time>'
                date_label += "范围"
            text = item["what_changed"]
            badge = '<span class="condition-indicator">含适用边界说明</span>' if uncertainty else ""
            changes.append(
                f'<article id="{esc(item["id"])}" class="change update-item">'
                f'<div class="update-date"><div class="date-span{" full-dates" if not same_year else ""}" '
                f'aria-label="{esc(date_label)}：{esc(first_date)}{" 至 " + esc(last_date) if first_date != last_date else ""}">{date_html}</div>'
                f'<span>{date_label}</span></div>'
                f'<div class="update-content"><div class="change-heading"><h2>{esc(item["title"])}</h2></div>'
                f'<p class="change-preview">{esc(text)}</p>{self.source_links(item.get("source_ids", []))}'
                f'<details class="update-details" open><summary><span>时间节点与知乎讨论</span>{badge}<span class="expand-sign" aria-hidden="true">+</span></summary>'
                f'<div class="update-detail-body"><div class="date-row">{date_rows}</div>{uncertainty}{feedback}</div></details></div></article>'
            )
        timeline_html = ""
        if timeline:
            rows = "".join(
                f'<li><div>{time_tag(x["date"])}<span>{LABELS[x.get("time_type", "event")]}</span></div>'
                f'<p>{esc(x["title"])} {self.citations(x.get("source_ids", []))}</p></li>'
                for x in sorted(timeline, key=lambda x: x["date"], reverse=True)
            )
            timeline_html = f'<section id="timeline" class="timeline-section"><h2>时间线</h2><ol class="timeline">{rows}</ol></section>'
        background = ""
        if p.get("background"):
            paragraphs = "".join(f'<p>{esc(x["text"])} {self.citations(x.get("source_ids", []))}</p>' for x in p["background"])
            background = f'<section id="background" class="background-section"><p class="eyebrow">背景基准</p><h2>理解本期变化的背景</h2>{paragraphs}</section>'
        empty = '<p class="no-updates">本窗口期内未检索到重大正式更新，可结合下方背景资料了解现状。</p>' if not changes else ""
        summary_html = render_summary_card(p.get("summary_card"), "近况速览")
        return (
            f'<main id="main">{summary_html}{lead}{self.toc(entries)}{self.browse_tools(len(changes), "项变化")}'
            f'<div class="updates-layout{chr(32) + "has-timeline" if timeline_html else ""}">'
            f'<div id="collection-results" class="updates-list">{"".join(changes)}{empty}</div>{timeline_html}</div>'
            f'{background}{self.next_section(p.get("next_checks", []), "后续关注")}{self.sources_drawer()}</main>'
        )

    def render(self):
        # 1、读取随Skill分发的样式和交互资源，生成不依赖外部资源的页面。
        css = (ASSETS / "zhihu-research.css").read_text(encoding="utf-8")
        js = (ASSETS / "zhihu-research.js").read_text(encoding="utf-8")
        p = self.page
        page_type = p["type"]
        brief = page_type == "recent-brief"
        name = "近况速览" if brief else "知乎观察"
        window = f'<div class="window"><span>观察窗口</span><strong>{esc(p["window"]["start"])} <em>—</em> {esc(p["window"]["end"])}</strong></div>' if brief else ""
        subtitle = f'<p class="subtitle">{esc(p["subtitle"])}</p>' if p.get("subtitle") else ""
        scope = f'<p class="scope-note">{esc(p["scope_note"])}</p>' if p.get("scope_note") else ""
        body = self.recent() if brief else self.observer()
        return (
            f'<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="light">'
            f'<title>{esc(p["title"])} · {name}</title><style>{css}</style></head>'
            f'<body class="curation {page_type}"><a class="skip-link" href="#main">跳到正文</a><div class="page-shell">'
            f'<header id="top"><div class="masthead"><a href="#top" class="brand"><span class="brand-name">知乎研究</span>'
            f'<span class="brand-section">{name}</span></a><div class="edition"><span>{esc(p.get("edition_label") or "专题选读")}</span>'
            f'<span>截至 {time_tag(p["as_of"])}</span></div></div><div class="hero"><h1>{esc(p["title"])}</h1>{subtitle}{window}</div></header>'
            f'<div class="curation-layout">{body}</div>{scope}'
            f'<footer><span>{name}</span><a href="#top">回到顶部 ↑</a><button type="button" class="print-button">打印 / 保存 PDF</button></footer>'
            f'</div><script>{js}</script></body></html>'
        )


# ============================================================================
# Part 2: Deep Research Article (Markdown + Visuals) Renderer
# ============================================================================

def normalize_inline_strong(value):
    marker = "￰CODE"
    while marker in value:
        marker += "_"
    chunks, code, index = [], [], 0
    while index < len(value):
        if value[index] == "\\" and index + 1 < len(value):
            chunks.append(value[index : index + 2])
            index += 2
            continue
        if value[index] != "`":
            chunks.append(value[index])
            index += 1
            continue
        end = index + 1
        while end < len(value) and value[end] == "`":
            end += 1
        run = value[index:end]
        close = re.search(r"(?<!`)" + re.escape(run) + r"(?!`)", value[end:])
        if close is None:
            chunks.append(run)
            index = end
            continue
        finish = end + close.end()
        key = marker + str(len(code)) + "￱"
        code.append((key, value[index:finish]))
        chunks.append(key)
        index = finish
    normalized = re.sub(r"\*\*([^\n]+?)\*\*", r" **\1** ", "".join(chunks))
    for key, original in code:
        normalized = normalized.replace(key, original)
    return normalized


def _strip_md(text):
    s = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)
    return re.sub(r"[*_`~]+", "", s)


class FragmentCheck(HTMLParser):
    def handle_starttag(self, tag, attrs):
        if tag in {"iframe", "object", "embed", "link", "base"}:
            raise ValueError("Visual HTML must not contain <" + tag + ">.")
        for name, value in attrs:
            value = (value or "").strip()
            if name in {"src", "srcset", "poster", "data"} and value and not value.startswith(("data:", "#")):
                raise ValueError("Visual resources must be embedded (SVG/data), not loaded from " + value)
            if name in {"href", "xlink:href"}:
                if value.lower().startswith(("javascript:", "vbscript:")):
                    raise ValueError("Executable links are not allowed in visual HTML.")
                if tag != "a" and value and not value.startswith(("#", "data:")):
                    raise ValueError("Visual SVG resources must be embedded, not loaded from " + value)

    handle_startendtag = handle_starttag


def _local_file(root, relative):
    if not isinstance(relative, str) or not relative.strip():
        raise ValueError("A visual file path must be a nonempty relative string.")
    path = Path(relative)
    if path.is_absolute():
        raise ValueError("Visual files must be inside the manifest directory: " + relative)
    path = (root / path).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ValueError("Visual file escapes the manifest directory: " + relative) from exc
    if not path.is_file():
        raise ValueError("Visual file does not exist: " + relative)
    return path


def _check_fragment(fragment):
    FragmentCheck(convert_charrefs=True).feed(fragment)
    if re.search(r"@import\b", fragment, re.IGNORECASE):
        raise ValueError("Visual CSS must not import external styles.")
    for resource in re.findall(r'url\(\s*[\"\']?([^\)\"\']+)', fragment, re.IGNORECASE):
        if not resource.strip().startswith(("#", "data:")):
            raise ValueError("Visual CSS resources must be embedded: " + resource)


def prepare_visuals(manifest_path, candidates, title_indices):
    # 1、读取可选图解清单，按正文锚点定位插入位置。
    if not manifest_path:
        return "", None, {}, {}, [], None
    manifest_path = Path(manifest_path).resolve()
    manifest_text = manifest_path.read_text(encoding="utf-8")
    manifest = json.loads(manifest_text)
    if not isinstance(manifest, dict) or not isinstance(manifest.get("blocks", []), list):
        raise ValueError("Visual manifest must be an object with a blocks array.")
    deck = manifest.get("deck", "")
    if not isinstance(deck, str):
        raise ValueError("Visual manifest deck must be plain text.")
    summary_card = manifest.get("summary_card")
    before, after, scripts, ids, files = {}, {}, [], set(), []
    generated_ids = set()
    for block in manifest.get("blocks", []):
        if not isinstance(block, dict):
            raise ValueError("Every visual block must be an object.")
        block_id = block.get("id", "")
        if not isinstance(block_id, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*", block_id):
            raise ValueError("Visual id must begin with a letter and use letters, digits, - or _.")
        if block_id in ids:
            raise ValueError("Duplicate visual id: " + block_id)
        dom_ids = {"visual-" + block_id, "visual-title-" + block_id}
        if generated_ids.intersection(dom_ids):
            raise ValueError("Visual figure and title IDs collide: " + block_id)
        generated_ids.update(dom_ids)
        ids.add(block_id)
        kind = block.get("kind")
        placement = block.get("placement", "after")
        width = block.get("width", "reading")
        if kind not in VISUAL_KINDS or placement not in {"before", "after"} or width not in {"reading", "wide"}:
            raise ValueError("Invalid kind, placement, or width in visual " + block_id)
        anchor = block.get("anchor")
        if not isinstance(anchor, str) or not anchor:
            raise ValueError("Visual anchor must be a nonempty original Markdown substring: " + block_id)
        matches = [(start, end) for start, end, content in candidates if anchor in content]
        if not matches:
            plain_anchor = _strip_md(anchor)
            matches = [(start, end) for start, end, content in candidates if plain_anchor and plain_anchor in _strip_md(content)]
        if not matches:
            raise ValueError("Visual anchor not found in top-level paragraph/heading content for " + block_id + ": " + anchor)
        start, end = matches[0]
        if start in title_indices:
            raise ValueError("Anchor a body paragraph or heading, not the document title: " + block_id)
        for field in ("title", "caption"):
            if not isinstance(block.get(field), str) or not block[field].strip():
                raise ValueError("Visual " + block_id + " needs a nonempty " + field)
        sources = block.get("sources", [])
        if not isinstance(sources, list):
            raise ValueError("Visual sources must be an array: " + block_id)
        source_markup = []
        for source in sources:
            if not isinstance(source, dict) or not isinstance(source.get("label"), str) or not source["label"].strip():
                raise ValueError("Visual source needs a label and url: " + block_id)
            url = source.get("url", "")
            if not isinstance(url, str) or not url.startswith(("https://", "http://")):
                raise ValueError("Visual source must be an http(s) link: " + str(url))
            source_markup.append('<a href="' + e(url) + '" target="_blank" rel="noopener noreferrer">' + e(source["label"]) + "</a>")
        # 2、图解只读取清单目录内的文件，检查资源边界后内嵌并登记摘要。
        fragment_path = _local_file(manifest_path.parent, block.get("html_file"))
        fragment = fragment_path.read_text(encoding="utf-8")
        _check_fragment(fragment)
        files.append({"file": str(fragment_path.relative_to(manifest_path.parent)), "sha256": hashlib.sha256(fragment.encode("utf-8")).hexdigest()})
        if block.get("script_file"):
            script_path = _local_file(manifest_path.parent, block["script_file"])
            script = script_path.read_text(encoding="utf-8")
            if re.search(r"</script(?=[\s/>])", script, re.IGNORECASE):
                raise ValueError("Author JavaScript must not contain a literal closing script tag: " + block_id)
            scripts.append("/* Authored visual: " + block_id + " */\n(() => {\n" + script + "\n})();")
            files.append({"file": str(script_path.relative_to(manifest_path.parent)), "sha256": hashlib.sha256(script.encode("utf-8")).hexdigest()})
        source_line = '<div class="visual-sources">依据：' + "；".join(source_markup) + "</div>" if source_markup else ""
        figure = (
            '<figure id="visual-'
            + block_id
            + '" class="article-visual visual-'
            + width
            + '" data-visual-kind="'
            + kind
            + '" aria-labelledby="visual-title-'
            + block_id
            + '"><header class="visual-heading"><h3 id="visual-title-'
            + block_id
            + '">'
            + e(block["title"])
            + '</h3></header><div class="visual-canvas">'
            + fragment
            + "</div><figcaption><p>"
            + e(block["caption"])
            + "</p>"
            + source_line
            + "</figcaption></figure>\n"
        )
        positions = before if placement == "before" else after
        positions.setdefault(start if placement == "before" else end, []).append(figure)
    metadata = {
        "manifest_sha256": hashlib.sha256(manifest_text.encode("utf-8")).hexdigest(),
        "block_count": len(ids),
        "block_ids": [block["id"] for block in manifest.get("blocks", [])],
        "authored_script_count": len(scripts),
        "files": files,
    }
    return deck, summary_card, before, after, scripts, metadata


def _inline_stdlib(text):
    code_map = {}

    def save_code(m):
        k = f"￰C{len(code_map)}￱"
        inner = m.group(2).replace("\n", " ")
        if inner.startswith(" ") and inner.endswith(" ") and len(inner) > 2:
            inner = inner[1:-1]
        code_map[k] = f"<code>{e(inner)}</code>"
        return k

    s = re.sub(r"(`+)([\s\S]+?)(?<!`)\1(?!`)", save_code, text)
    s = e(s)
    s = re.sub(r"\[([^\]]+)\]\((https?://[^\s\)]+)\)", r'<a href="\2">\1</a>', s)
    s = re.sub(r"\*\*([^\n*]+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<!\*)\*([^\n*]+?)\*(?!\*)", r"<em>\1</em>", s)
    for k, val in code_map.items():
        s = s.replace(e(k), val)
    return s


def _parse_stdlib_markdown(text, visuals):
    # 1、没有可选Markdown库时解析基础块，原始HTML按文本转义。
    lines = text.splitlines()
    blocks = []
    i, n = 0, len(lines)
    while i < n:
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        m_fence = re.match(r"^(`{3,}|~{3,})\s*(\S*)", line)
        if m_fence:
            fence, lang = m_fence.group(1), m_fence.group(2)
            i += 1
            buf = []
            while i < n and not re.match(r"^" + re.escape(fence) + r"\s*$", lines[i]):
                buf.append(lines[i])
                i += 1
            i += 1
            cls = f' class="language-{e(lang)}"' if lang else ""
            blocks.append(("code", "", f"<pre><code{cls}>{e(chr(10).join(buf) + chr(10))}</code></pre>"))
            continue
        if line.startswith("    ") or line.startswith("\t"):
            buf = []
            while i < n and (lines[i].startswith("    ") or lines[i].startswith("\t") or not lines[i].strip()):
                buf.append(lines[i][4:] if lines[i].startswith("    ") else lines[i].lstrip("\t"))
                i += 1
            while buf and not buf[-1].strip():
                buf.pop()
            blocks.append(("code", "", f"<pre><code>{e(chr(10).join(buf) + chr(10))}</code></pre>"))
            continue
        m_h = re.match(r"^(#{1,4})\s+(.+?)\s*$", line)
        if m_h:
            level, raw = len(m_h.group(1)), m_h.group(2)
            blocks.append((f"h{level}", raw, _inline_stdlib(raw)))
            i += 1
            continue
        if re.match(r"^(-{3,}|\*{3,}|_{3,})\s*$", line.strip()):
            blocks.append(("hr", "", "<hr>"))
            i += 1
            continue
        if "|" in line and i + 1 < n and re.match(r"^\s*\|?[\s:-]+\|[\s|:-]*$", lines[i + 1]):
            header_cells = [c.strip() for c in line.strip().strip("|").split("|")]
            i += 2
            rows = []
            while i < n and "|" in lines[i] and lines[i].strip():
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            th_html = "".join(f"<th>{_inline_stdlib(c)}</th>" for c in header_cells)
            tr_html = "".join("<tr>" + "".join(f"<td>{_inline_stdlib(c)}</td>" for c in r) + "</tr>" for r in rows)
            blocks.append(("table", "", f"<table><thead><tr>{th_html}</tr></thead><tbody>{tr_html}</tbody></table>"))
            continue
        if line.lstrip().startswith(">"):
            buf = []
            while i < n and lines[i].lstrip().startswith(">"):
                buf.append(re.sub(r"^\s*>\s?", "", lines[i]))
                i += 1
            blocks.append(("blockquote", "", f'<blockquote><p>{_inline_stdlib(" ".join(buf))}</p></blockquote>'))
            continue
        m_ul = re.match(r"^\s*([-*+])\s+(.+)$", line)
        m_ol = re.match(r"^\s*(\d+)\.\s+(.+)$", line)
        if m_ul or m_ol:
            tag = "ul" if m_ul else "ol"
            items = []
            while i < n:
                m_item = re.match(r"^\s*[-*+]\s+(.+)$", lines[i]) if tag == "ul" else re.match(r"^\s*\d+\.\s+(.+)$", lines[i])
                if not m_item:
                    break
                items.append(f"<li>{_inline_stdlib(m_item.group(1))}</li>")
                i += 1
            blocks.append((tag, "", f'<{tag}>{"".join(items)}</{tag}>'))
            continue
        buf = []
        while i < n and lines[i].strip() and not re.match(r"^(#{1,4}\s|```|~~~|    |\t|\s*[-*+]\s|\s*\d+\.\s|\s*>)", lines[i]):
            if "|" in lines[i] and i + 1 < n and re.match(r"^\s*\|?[\s:-]+\|[\s|:-]*$", lines[i + 1]):
                break
            buf.append(lines[i].strip())
            i += 1
        raw_p = "\n".join(buf)
        blocks.append(("p", raw_p, f"<p>{_inline_stdlib(raw_p)}</p>"))

    title, title_markup, toc = "研究报告", "研究报告", []
    title_indices = set()
    candidates = []
    for idx, (btype, raw, html_str) in enumerate(blocks):
        if btype == "h1" and not title_indices:
            title = raw
            title_markup = html_str
            title_indices = {idx}
        elif btype == "h2":
            anchor = f"section-{len(toc) + 1}"
            toc.append((anchor, raw))
            blocks[idx] = (btype, raw, f'<h2 id="{anchor}" tabindex="-1">{html_str}</h2>')
        elif btype in ("h3", "h4"):
            blocks[idx] = (btype, raw, f"<{btype}>{html_str}</{btype}>")
        if btype in ("p", "h1", "h2", "h3", "h4"):
            candidates.append((idx, idx, raw))

    # 2、生成目录与图解插入结果，保持源报告的阅读顺序。
    deck, summary_card, before, after, scripts, visual_meta = prepare_visuals(visuals, candidates, title_indices)
    out = []
    for idx, (btype, raw, html_str) in enumerate(blocks):
        for frag in before.get(idx, []):
            out.append(frag)
        if idx not in title_indices:
            out.append(html_str)
        for frag in after.get(idx, []):
            out.append(frag)
    return title, title_markup, toc, deck, summary_card, "\n".join(out), scripts, visual_meta


def render_article(source, target, label="深度研究", as_of=None, back_link=None, markdown_link=None, visuals=None):
    # 1、读取报告并选择已安装的解析器；缺少可选库时使用标准库回退。
    source, target = Path(source), Path(target)
    as_of = as_of or date.today().isoformat()
    text = source.read_text(encoding="utf-8")
    try:
        from markdown_it import MarkdownIt
        from markdown_it.token import Token
        has_mdit = True
    except ImportError:
        has_mdit = False

    if has_mdit:
        md = MarkdownIt("commonmark", {"html": False}).enable("table")
        env = {}
        tokens = md.parse(text, env)
        for token in tokens:
            if token.type == "inline":
                prepared = normalize_inline_strong(token.content)
                if prepared != token.content:
                    token.children = md.inline.parse(prepared, md, env, [])
        title, title_markup, toc = source.stem, e(source.stem), []
        title_indices = set()
        candidates = []
        for index, token in enumerate(tokens):
            if token.type in {"paragraph_open", "heading_open"} and token.level == 0:
                if index + 2 < len(tokens) and tokens[index + 1].type == "inline":
                    candidates.append((index, index + 2, tokens[index + 1].content))
            if token.type != "heading_open":
                continue
            inline = tokens[index + 1]
            if token.tag == "h1" and not title_indices:
                title = inline.content
                title_markup = md.renderer.renderInline(inline.children or [], md.options, env)
                title_indices = {index, index + 1, index + 2}
            elif token.tag == "h2":
                anchor = "section-" + str(len(toc) + 1)
                token.attrSet("id", anchor)
                token.attrSet("tabindex", "-1")
                toc.append((anchor, inline.content))
        deck, summary_card, before, after, scripts, visual_meta = prepare_visuals(visuals, candidates, title_indices)
        body_tokens = []
        for index, token in enumerate(tokens):
            for fragment in before.get(index, []):
                injected = Token("html_block", "", 0)
                injected.content = fragment
                body_tokens.append(injected)
            if index not in title_indices:
                body_tokens.append(token)
            for fragment in after.get(index, []):
                injected = Token("html_block", "", 0)
                injected.content = fragment
                body_tokens.append(injected)
        body = md.renderer.render(body_tokens, md.options, env)
    else:
        title, title_markup, toc, deck, summary_card, body, scripts, visual_meta = _parse_stdlib_markdown(text, visuals)

    # 2、内嵌样式、导航和已校验图解，输出可离线阅读的HTML。
    body = body.replace("<table>", '<div class="table-scroll" tabindex="0" role="region" aria-label="对照表，可左右滚动"><table>').replace("</table>", "</table></div>")
    css = (ASSETS / "zhihu-research.css").read_text(encoding="utf-8")
    js = (ASSETS / "zhihu-research.js").read_text(encoding="utf-8")
    navigation = "".join('<a href="#' + anchor + '"><span class="article-rail-mark" aria-hidden="true"></span><span class="article-nav-label">' + e(name) + "</span></a>" for anchor, name in toc)
    rail_markup = ('<nav class="article-rail" aria-label="文章章节" data-article-nav><span class="article-rail-heading">文章目录</span>' + navigation + "</nav>") if toc else ""
    contents_markup = (
        '<details class="article-contents"><summary><span class="article-menu-icon" aria-hidden="true">☰</span>'
        '<span>目录</span><span class="article-nav-position">1 / '
        + str(len(toc))
        + '</span></summary><nav aria-label="文章章节" data-article-nav>'
        + navigation
        + "</nav></details>"
    ) if toc else ""
    footer_links = []
    if markdown_link:
        footer_links.append('<a href="' + e(markdown_link) + '">阅读 Markdown</a>')
    if back_link:
        footer_links.append('<a href="' + e(back_link) + '">返回样例展厅</a>')
    summary_html = render_summary_card(summary_card, "深度研究")
    doc = f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{e(title)}</title><style>{css}
</style></head><body class="research-article"><a class="skip-link" href="#content">跳到正文</a>{rail_markup}{contents_markup}<div class="article-shell">
<div class="article-publication"><span class="brand-name">知乎研究</span><span>深度研究</span><span class="article-edition">{e(label)}</span></div>
<header class="article-header"><h1>{title_markup}</h1>{'<p class="article-deck">' + e(deck) + '</p>' if deck else ''}<p class="article-dateline">研究截至 <time>{e(as_of)}</time></p>{summary_html}</header>
<main id="content"><article class="prose article-prose">{body}</article></main>
<footer class="article-footer"><button class="print-button" type="button">打印或保存 PDF</button><div class="article-actions">{''.join(footer_links)}</div></footer>
</div><script>
{js}
</script><script>
{chr(10).join(scripts)}
</script></body></html>"""
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(doc, encoding="utf-8")
    return {
        "valid": True,
        "type": "deep-research",
        "source": str(source),
        "output": str(target),
        "title": title,
        "section_count": len(toc),
        "visuals": visual_meta,
    }


def main():
    # 1、解析本地输入与输出，校验模式不得覆盖来源文件。
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("positional", nargs="*", type=Path, help="Optional [input_file output_html]")
    parser.add_argument("--page", type=Path, help="Page JSON for observer or recent-brief")
    parser.add_argument("--sources", type=Path, help="Optional separate sources JSON for observer/recent-brief")
    parser.add_argument("--output", "-o", type=Path, help="Output HTML path")
    parser.add_argument("--as-of", default=date.today().isoformat(), help="Research cutoff date (YYYY-MM-DD) for article mode")
    parser.add_argument("--label", default="深度研究", help="Edition label for article mode")
    parser.add_argument("--visuals", type=Path, help="Optional visuals.json manifest for article mode")
    parser.add_argument("--markdown-link", help="Optional Markdown source link for article footer")
    parser.add_argument("--back-link", help="Optional gallery link for article footer")
    parser.add_argument("--validate-only", action="store_true", help="Validate page.json without writing HTML")
    args = parser.parse_args()

    input_path = args.page or (args.positional[0] if len(args.positional) >= 1 else None)
    output_path = args.output or (args.positional[1] if len(args.positional) >= 2 else None)

    if not input_path:
        parser.error("Provide an input file (report.md or --page page.json)")
    if not output_path and not args.validate_only:
        parser.error("Provide an output HTML file (--output index.html or second positional argument)")
    if args.validate_only and input_path.suffix.lower() != ".json" and args.page is None:
        parser.error("--validate-only supports page.json; article mode requires an output file")
    if output_path and output_path.resolve() == input_path.resolve():
        parser.error("Output must differ from the input file")

    # 2、按输入类型校验并渲染，错误以非零退出码返回，不发起网络请求。
    try:
        if input_path.suffix.lower() == ".json" or args.page is not None:
            page = object_(json.loads(input_path.read_text(encoding="utf-8")), "page")
            sources = load_sources(page, args.sources)
            validate_page(page, sources)
            if not args.validate_only:
                output = PageRenderer(page, sources).render()
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_text(output, encoding="utf-8")
            print(json.dumps({"valid": True, "type": page["type"], "sources": len(sources), "output": None if args.validate_only else str(output_path)}, ensure_ascii=False))
        else:
            res = render_article(input_path, output_path, args.label, args.as_of, args.back_link, args.markdown_link, args.visuals)
            print(json.dumps(res, ensure_ascii=False))
    except (Invalid, ValueError, OSError, json.JSONDecodeError) as error:
        print(f"Validation/Render error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
