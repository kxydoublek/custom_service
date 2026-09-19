#!/usr/bin/env python3
"""从 docs/project-map.json 生成 docs/project-console.html，并按源码指纹做隔离检查。

不 import 业务模块，不读取 backend/.env、日志、数据库或用户上传。
人工归纳的算法内容不会在刷新时改写；源码指纹变化时把「源码已核对」降为「来源已变化待复核」。
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import sys
from pathlib import Path
from typing import Any

STATUS_CHECKED = "源码已核对"
STATUS_STALE = "来源已变化待复核"
STATUS_MISSING = "未找到实现"
STATUS_DESIGN = "仅设计"
VALID_STATUSES = {STATUS_CHECKED, STATUS_STALE, STATUS_MISSING, STATUS_DESIGN}

CHECKED_AT_KEY = "checked_at"


def project_root_from_script() -> Path:
    return Path(__file__).resolve().parents[1]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_map(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    if not path.is_file():
        return None, f"说明数据不存在：{path}"
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return None, f"无法读取说明数据：{path}（{exc}）"
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        return None, f"说明数据不是合法 JSON：{path}（第 {exc.lineno} 行：{exc.msg}）"
    if not isinstance(data, dict):
        return None, f"说明数据根节点必须是对象：{path}"
    return data, None


def iter_source_owners(data: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    owners: list[tuple[str, dict[str, Any]]] = []
    for key in ("pages", "features", "apis", "algorithms", "modules"):
        items = data.get(key) or []
        if not isinstance(items, list):
            continue
        for item in items:
            if isinstance(item, dict):
                owners.append((key, item))
                nested = item.get("algorithm")
                if isinstance(nested, dict):
                    owners.append((f"{key}.algorithm", nested))
    return owners


def apply_fingerprints(
    data: dict[str, Any],
    root: Path,
    *,
    record_empty: bool,
) -> list[str]:
    issues: list[str] = []
    for owner_kind, owner in iter_source_owners(data):
        sources = owner.get("sources")
        if not isinstance(sources, list):
            continue
        owner_id = str(owner.get("id") or owner.get("name") or owner_kind)
        stale = False
        missing = False
        parse_hints: list[str] = []
        for source in sources:
            if not isinstance(source, dict):
                continue
            rel = str(source.get("path") or "").strip()
            if not rel:
                continue
            path = (root / rel).resolve()
            try:
                path.relative_to(root.resolve())
            except ValueError:
                missing = True
                source["check"] = "outside-root"
                parse_hints.append(f"{owner_id} 来源路径越界：{rel}")
                continue
            if not path.is_file():
                missing = True
                source["check"] = "missing"
                parse_hints.append(f"{owner_id} 来源缺失：{rel}")
                continue
            current = sha256_file(path)
            stored = str(source.get("fingerprint") or "").strip()
            if not stored:
                source["check"] = "unrecorded"
                if record_empty:
                    source["fingerprint"] = current
                    source["check"] = "ok"
                else:
                    parse_hints.append(f"{owner_id} 尚未记录指纹：{rel}")
                continue
            if stored != current:
                stale = True
                source["check"] = "stale"
                parse_hints.append(f"{owner_id} 源码已变化：{rel}")
            else:
                source["check"] = "ok"
        status = str(owner.get("implementation_status") or "")
        if missing:
            owner["implementation_status"] = STATUS_MISSING
            owner["status_hint"] = "；".join(parse_hints) or "来源文件不存在，无法继续标已核对"
            issues.extend(parse_hints)
        elif stale:
            if status == STATUS_CHECKED or status not in VALID_STATUSES:
                owner["implementation_status"] = STATUS_STALE
            owner["status_hint"] = "；".join(parse_hints)
            issues.extend(parse_hints)
        elif parse_hints and not record_empty:
            owner["status_hint"] = "；".join(parse_hints)
            issues.extend(parse_hints)
        else:
            owner.pop("status_hint", None)
    return issues


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def join_lines(items: list[Any] | None) -> str:
    if not items:
        return ""
    return "".join(f"<li>{esc(item)}</li>" for item in items)


def render_flow(steps: list[Any] | None) -> str:
    if not steps:
        return "<p class='muted'>未记录流程。</p>"
    rows = []
    for index, step in enumerate(steps, start=1):
        if not isinstance(step, dict):
            rows.append(f"<li>{esc(step)}</li>")
            continue
        branch = step.get("branch")
        branch_html = f"<div class='meta'>分支：{esc(branch)}</div>" if branch else ""
        rows.append(
            "<li>"
            f"<strong>{index}. {esc(step.get('actor'))}</strong>"
            f"<div>{esc(step.get('action'))}</div>"
            f"<div class='meta'>数据：{esc(step.get('data'))}</div>"
            f"{branch_html}"
            "</li>"
        )
    return f"<ol class='flow'>{''.join(rows)}</ol>"


def render_fields(fields: list[Any] | None, caption: str) -> str:
    if not fields:
        return f"<p class='muted'>{esc(caption)}未记录。</p>"
    rows = []
    for field in fields:
        if not isinstance(field, dict):
            rows.append(f"<li>{esc(field)}</li>")
            continue
        rows.append(
            "<li>"
            f"<code>{esc(field.get('name'))}</code>"
            f" · {esc(field.get('location') or 'body')} · {esc(field.get('type'))}"
            f"<div class='meta'>{esc(field.get('note'))}</div>"
            "</li>"
        )
    return f"<ul class='fields'>{''.join(rows)}</ul>"


def render_sources(sources: list[Any] | None) -> str:
    if not sources:
        return "<p class='muted'>未记录来源。</p>"
    items = []
    for source in sources:
        if not isinstance(source, dict):
            continue
        path = str(source.get("path") or "")
        symbol = source.get("symbol") or source.get("section") or ""
        check = source.get("check") or ""
        check_label = {
            "ok": "指纹相符",
            "stale": "指纹已过期",
            "missing": "文件缺失",
            "unrecorded": "未记指纹",
            "outside-root": "路径越界",
        }.get(check, check)
        items.append(
            "<li>"
            f"<code class='path' data-path='{esc(path)}'>{esc(path)}</code>"
            f"{' · ' + esc(symbol) if symbol else ''}"
            f"{' · ' + esc(check_label) if check_label else ''}"
            "<button type='button' class='copy' data-copy='"
            f"{esc(path)}'>复制路径</button>"
            "</li>"
        )
    return f"<ul class='sources'>{''.join(items)}</ul>"


def render_parameters(params: list[Any] | None) -> str:
    if not params:
        return "<p class='muted'>未挂参数。</p>"
    items = []
    for param in params:
        if not isinstance(param, dict):
            continue
        items.append(
            "<li>"
            f"<code>{esc(param.get('key'))}</code>"
            f" = {esc(param.get('value'))}"
            f" · {esc(param.get('value_kind'))}"
            f"<div class='meta'>{esc(param.get('location'))}。影响：{esc(param.get('impact'))}</div>"
            "</li>"
        )
    return f"<ul class='fields'>{''.join(items)}</ul>"


def status_class(status: str) -> str:
    mapping = {
        STATUS_CHECKED: "ok",
        STATUS_STALE: "stale",
        STATUS_MISSING: "missing",
        STATUS_DESIGN: "design",
    }
    return mapping.get(status, "unknown")


def collect_by_page(features: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for feature in features:
        page_id = str(feature.get("page_id") or "")
        grouped.setdefault(page_id, []).append(feature)
    return grouped


def render_error_html(message: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>页面功能导航 · 无法生成</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 1rem; color: #222; }}
    .error {{ border: 1px solid #b42318; background: #fff4f0; padding: 1rem; border-radius: 8px; }}
  </style>
</head>
<body>
  <h1>页面功能与实现导航</h1>
  <p class="error" role="alert">{esc(message)}</p>
  <p>请检查 <code>docs/project-map.json</code> 后重新运行刷新脚本。此页不读取密钥或业务数据。</p>
</body>
</html>
"""


def render_html(data: dict[str, Any], issues: list[str]) -> str:
    meta = data.get("meta") if isinstance(data.get("meta"), dict) else {}
    pages = [item for item in (data.get("pages") or []) if isinstance(item, dict)]
    features = [item for item in (data.get("features") or []) if isinstance(item, dict)]
    apis = [item for item in (data.get("apis") or []) if isinstance(item, dict)]
    algorithms = [item for item in (data.get("algorithms") or []) if isinstance(item, dict)]
    modules = [item for item in (data.get("modules") or []) if isinstance(item, dict)]
    parameters = [item for item in (data.get("parameters") or []) if isinstance(item, dict)]
    by_page = collect_by_page(features)

    issue_banner = ""
    if issues:
        issue_banner = (
            "<div class='banner warn' role='status'><strong>刷新检查</strong><ul>"
            + "".join(f"<li>{esc(item)}</li>" for item in issues)
            + "</ul></div>"
        )

    nav_items = []
    page_blocks = []
    for page in pages:
        page_id = str(page.get("id") or "")
        nav_items.append(
            f"<a class='nav-link' href='#page-{esc(page_id)}'>"
            f"<span class='route'>{esc(page.get('route'))}</span>"
            f"{esc(page.get('name'))}</a>"
        )
        cards = []
        for feature in by_page.get(page_id, []):
            feature_id = str(feature.get("id") or "")
            api_links = []
            for api_id in feature.get("api_ids") or []:
                api_links.append(f"<a href='#api-{esc(api_id)}'>{esc(api_id)}</a>")
            algo_links = []
            for algo_id in feature.get("algorithm_ids") or []:
                algo_links.append(f"<a href='#algo-{esc(algo_id)}'>{esc(algo_id)}</a>")
            status = str(feature.get("implementation_status") or "")
            hint = feature.get("status_hint")
            cards.append(
                "<article class='card' id='feature-"
                f"{esc(feature_id)}'>"
                f"<h3>{esc(feature.get('name'))}</h3>"
                f"<p class='status {status_class(status)}'>{esc(status)}</p>"
                + (f"<p class='hint'>{esc(hint)}</p>" if hint else "")
                + "<p><strong>触发：</strong>"
                f"{esc(feature.get('trigger'))}</p>"
                f"<p><strong>输入：</strong>{esc(feature.get('input'))}</p>"
                f"<p><strong>输出：</strong>{esc(feature.get('output'))}</p>"
                "<h4>主流程</h4>"
                + render_flow(feature.get("flow") if isinstance(feature.get("flow"), list) else None)
                + "<p class='refs'>接口："
                + ("、".join(api_links) if api_links else "无")
                + "</p>"
                + (
                    "<p class='refs'>算法：" + "、".join(algo_links) + "</p>"
                    if algo_links
                    else ""
                )
                + "<details><summary>来源</summary>"
                + render_sources(feature.get("sources") if isinstance(feature.get("sources"), list) else None)
                + "</details></article>"
            )
        page_blocks.append(
            f"<section class='page' id='page-{esc(page_id)}'>"
            f"<header class='page-head'><h2>{esc(page.get('name'))}</h2>"
            f"<p class='route'>{esc(page.get('route'))}</p>"
            f"<p>{esc(page.get('purpose'))}</p></header>"
            + "".join(cards)
            + "</section>"
        )

    api_blocks = []
    for api in apis:
        api_id = str(api.get("id") or "")
        status = str(api.get("implementation_status") or "")
        algo_id = api.get("algorithm_id")
        algo_link = (
            f"<p class='refs'>算法：<a href='#algo-{esc(algo_id)}'>{esc(algo_id)}</a></p>"
            if algo_id
            else ""
        )
        module_links = []
        for module_id in api.get("module_ids") or []:
            module_links.append(f"<a href='#mod-{esc(module_id)}'>{esc(module_id)}</a>")
        api_blocks.append(
            f"<article class='card' id='api-{esc(api_id)}'>"
            f"<h3>{esc(api_id)} {esc(api.get('name'))}</h3>"
            f"<p><code>{esc(api.get('method'))} {esc(api.get('url'))}</code></p>"
            f"<p class='status {status_class(status)}'>{esc(status)}</p>"
            + (f"<p class='hint'>{esc(api.get('status_hint'))}</p>" if api.get("status_hint") else "")
            + "<details><summary>请求字段</summary>"
            + render_fields(api.get("request") if isinstance(api.get("request"), list) else None, "请求")
            + "</details><details><summary>响应字段</summary>"
            + render_fields(api.get("response") if isinstance(api.get("response"), list) else None, "响应")
            + "</details>"
            + algo_link
            + (
                "<p class='refs'>模块：" + "、".join(module_links) + "</p>"
                if module_links
                else ""
            )
            + "<details><summary>来源</summary>"
            + render_sources(api.get("sources") if isinstance(api.get("sources"), list) else None)
            + "</details></article>"
        )

    algo_blocks = []
    for algo in algorithms:
        algo_id = str(algo.get("id") or "")
        status = str(algo.get("implementation_status") or "")
        algo_blocks.append(
            f"<article class='card' id='algo-{esc(algo_id)}'>"
            f"<h3>{esc(algo_id)} {esc(algo.get('name') or algo.get('subject'))}</h3>"
            f"<p>{esc(algo.get('subject'))}</p>"
            f"<p class='status {status_class(status)}'>{esc(status)}</p>"
            + (f"<p class='hint'>{esc(algo.get('status_hint'))}</p>" if algo.get("status_hint") else "")
            + "<details open><summary>步骤</summary><ol>"
            + join_lines(algo.get("steps") if isinstance(algo.get("steps"), list) else None)
            + "</ol></details>"
            + "<details><summary>分支与筛选</summary><ul>"
            + join_lines(algo.get("branches") if isinstance(algo.get("branches"), list) else None)
            + "</ul><h4>结果选择</h4><p>"
            + esc(algo.get("selection"))
            + "</p></details>"
            + "<details><summary>失败边界</summary><ul>"
            + join_lines(algo.get("failures") if isinstance(algo.get("failures"), list) else None)
            + "</ul></details>"
            + "<details><summary>参数</summary>"
            + render_parameters(algo.get("parameters") if isinstance(algo.get("parameters"), list) else None)
            + "</details><details><summary>来源</summary>"
            + render_sources(algo.get("sources") if isinstance(algo.get("sources"), list) else None)
            + "</details></article>"
        )

    module_blocks = []
    for module in modules:
        module_id = str(module.get("id") or "")
        status = str(module.get("implementation_status") or "")
        kind = str(module.get("kind") or "")
        if kind.lower() == "agent" or "agent工具" in kind.lower():
            continue
        module_blocks.append(
            f"<article class='card' id='mod-{esc(module_id)}'>"
            f"<h3>{esc(module_id)} {esc(module.get('name'))}</h3>"
            f"<p>类型：{esc(kind)}</p>"
            f"<p class='status {status_class(status)}'>{esc(status)}</p>"
            + (f"<p class='hint'>{esc(module.get('status_hint'))}</p>" if module.get("status_hint") else "")
            + f"<p>{esc(module.get('responsibility'))}</p>"
            f"<p><strong>输入：</strong>{esc(module.get('input'))}</p>"
            f"<p><strong>输出：</strong>{esc(module.get('output'))}</p>"
            + (
                f"<p class='refs'>算法：<a href='#algo-{esc(module.get('algorithm_id'))}'>"
                f"{esc(module.get('algorithm_id'))}</a></p>"
                if module.get("algorithm_id")
                else ""
            )
            + "<details><summary>来源</summary>"
            + render_sources(module.get("sources") if isinstance(module.get("sources"), list) else None)
            + "</details></article>"
        )

    param_rows = []
    for param in parameters:
        param_rows.append(
            "<tr>"
            f"<td><code>{esc(param.get('key'))}</code></td>"
            f"<td>{esc(param.get('value'))}</td>"
            f"<td>{esc(param.get('value_kind'))}</td>"
            f"<td>{esc(param.get('location'))}</td>"
            f"<td>{esc(param.get('impact'))}</td>"
            "</tr>"
        )

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{esc(meta.get('title') or '页面功能与实现导航')}</title>
  <style>
    :root {{
      --bg: #f7f5f1;
      --card: #fff;
      --ink: #1f1c17;
      --muted: #5c574e;
      --line: #d9d3c7;
      --accent: #215a6b;
      --ok: #216e4e;
      --stale: #8a5a12;
      --missing: #b42318;
      --design: #4747a3;
    }}
    * {{ box-sizing: border-box; }}
    html, body {{ margin: 0; padding: 0; background: var(--bg); color: var(--ink);
      font-family: "PingFang SC", "Noto Sans SC", "Source Han Sans SC", sans-serif;
      line-height: 1.55; overflow-x: hidden; }}
    a {{ color: var(--accent); }}
    .wrap {{ display: grid; grid-template-columns: minmax(10rem, 14rem) minmax(0, 1fr); min-height: 100vh; max-width: 100%; }}
    .nav {{ border-right: 1px solid var(--line); padding: 1rem; position: sticky; top: 0;
      align-self: start; max-height: 100vh; overflow: auto; background: var(--bg); }}
    .nav h1 {{ font-size: 1.05rem; margin: 0 0 .75rem; }}
    .nav-link {{ display: block; padding: .45rem .5rem; border-radius: 8px; text-decoration: none;
      color: inherit; margin-bottom: .25rem; }}
    .nav-link:hover, .nav-link:focus {{ background: #ece7dc; }}
    .nav .route {{ display: block; color: var(--muted); font-size: .8rem; }}
    main {{ padding: 1rem; min-width: 0; overflow-x: hidden; }}
    .banner {{ padding: .75rem 1rem; border-radius: 8px; margin-bottom: 1rem; }}
    .banner.warn {{ background: #fff4e5; border: 1px solid #efc16b; }}
    .page {{ margin-bottom: 2rem; }}
    .page-head h2 {{ margin: 0 0 .25rem; }}
    .card {{ background: var(--card); border: 1px solid var(--line); border-radius: 12px;
      padding: .9rem 1rem; margin: .75rem 0; overflow-wrap: anywhere; }}
    .status {{ display: inline-block; font-size: .85rem; padding: .1rem .45rem; border-radius: 999px; }}
    .status.ok {{ background: #e8f5ee; color: var(--ok); }}
    .status.stale {{ background: #fff4e5; color: var(--stale); }}
    .status.missing {{ background: #fdecec; color: var(--missing); }}
    .status.design {{ background: #ececff; color: var(--design); }}
    .muted, .meta, .hint {{ color: var(--muted); font-size: .92rem; }}
    details {{ margin: .4rem 0; }}
    summary {{ cursor: pointer; font-weight: 600; }}
    .flow, .fields, .sources {{ padding-left: 1.1rem; }}
    code, .route {{ overflow-wrap: anywhere; }}
    code.path {{ background: #eeeae2; padding: .05rem .3rem; border-radius: 4px; }}
    button.copy {{ margin-left: .35rem; font-size: .8rem; }}
    #parameters {{ min-width: 0; }}
    .table-wrap {{ overflow-x: auto; max-width: 100%; }}
    table {{ width: 100%; min-width: 28rem; border-collapse: collapse; font-size: .92rem; table-layout: fixed; }}
    th, td {{ border-bottom: 1px solid var(--line); text-align: left; padding: .4rem; vertical-align: top; overflow-wrap: anywhere; }}
    .copy-fallback {{ display: none; width: 100%; margin-top: .35rem; }}
    .toast {{ position: fixed; bottom: 1rem; right: 1rem; background: #1f1c17; color: #fff;
      padding: .4rem .7rem; border-radius: 8px; display: none; }}
    @media (max-width: 800px) {{
      .wrap {{ display: block; }}
      .nav {{ position: static; max-height: none; display: flex; flex-wrap: wrap; gap: .35rem;
        border-right: 0; border-bottom: 1px solid var(--line); }}
      .nav h1 {{ width: 100%; }}
      .nav-link {{ margin: 0; }}
      main {{ padding: .75rem; }}
      table {{ min-width: 0; }}
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <nav class="nav" aria-label="页面">
      <h1>{esc(meta.get("title") or "页面功能与实现导航")}</h1>
      <p class="muted">{esc(meta.get("project_name"))} · 核对日 {esc(meta.get(CHECKED_AT_KEY))}</p>
      {''.join(nav_items)}
      <a class="nav-link" href="#apis">全部接口</a>
      <a class="nav-link" href="#algorithms">算法</a>
      <a class="nav-link" href="#modules">模块</a>
      <a class="nav-link" href="#parameters">参数</a>
    </nav>
    <main>
      {issue_banner}
      <p>{esc(meta.get("notes"))}</p>
      {''.join(page_blocks)}
      <section id="apis"><h2>接口</h2>{''.join(api_blocks)}</section>
      <section id="algorithms"><h2>算法</h2>{''.join(algo_blocks)}</section>
      <section id="modules"><h2>模块与外部调用</h2>
        <p class="muted">本仓库没有 Plugin / Agent 工具循环。百炼调用是 httpx Chat/Embedding，不展示 Agent 观察环。</p>
        {''.join(module_blocks)}
      </section>
      <section id="parameters"><h2>参数</h2>
        <p class="muted">源码默认值来自 settings 与空值模板；未读取真实 .env，运行值标为未知。</p>
        <div class="table-wrap">
        <table>
          <thead><tr><th>键</th><th>值</th><th>种类</th><th>位置</th><th>影响</th></tr></thead>
          <tbody>{''.join(param_rows)}</tbody>
        </table>
        </div>
      </section>
    </main>
  </div>
  <div class="toast" id="toast" role="status"></div>
  <script>
    const toast = document.getElementById('toast');
    function showToast(text) {{
      toast.textContent = text;
      toast.style.display = 'block';
      setTimeout(() => {{ toast.style.display = 'none'; }}, 1600);
    }}
    function manualSelect(button, text) {{
      let input = button.parentElement.querySelector('.copy-fallback');
      if (!input) {{
        input = document.createElement('input');
        input.className = 'copy-fallback';
        input.setAttribute('readonly', 'readonly');
        button.parentElement.appendChild(input);
      }}
      input.value = text;
      input.style.display = 'block';
      input.focus();
      input.select();
      showToast('复制失败，请手选路径');
    }}
    document.querySelectorAll('button.copy').forEach((button) => {{
      button.addEventListener('click', async () => {{
        const text = button.getAttribute('data-copy') || '';
        try {{
          if (!navigator.clipboard || !navigator.clipboard.writeText) throw new Error('no clipboard');
          await navigator.clipboard.writeText(text);
          showToast('已复制路径');
        }} catch (err) {{
          manualSelect(button, text);
        }}
      }});
    }});
  </script>
</body>
</html>
"""


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def persistable_map(data: dict[str, Any]) -> dict[str, Any]:
    cleaned = json.loads(json.dumps(data))
    for _, owner in iter_source_owners(cleaned):
        owner.pop("status_hint", None)
        sources = owner.get("sources")
        if not isinstance(sources, list):
            continue
        for source in sources:
            if isinstance(source, dict):
                source.pop("check", None)
    return cleaned


def generate(map_path: Path, html_path: Path, root: Path, record_empty: bool) -> int:
    data, error = load_map(map_path)
    if error or data is None:
        write_text(html_path, render_error_html(error or "无法读取说明数据"))
        print(error or "无法读取说明数据", file=sys.stderr)
        return 2
    issues = apply_fingerprints(data, root, record_empty=record_empty)
    if record_empty:
        map_path.write_text(
            json.dumps(persistable_map(data), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    write_text(html_path, render_html(data, issues))
    print(f"wrote {html_path}")
    if issues:
        print("fingerprint issues:", len(issues))
        for item in issues:
            print(" -", item)
    return 0


def card_html(page: str, card_id: str) -> str:
    prefix = card_id.split("-", 1)[0] + "-"
    for quote in ("'", '"'):
        needle = f"id={quote}{card_id}{quote}"
        start = page.find(needle)
        if start < 0:
            continue
        nxt = page.find(f"id={quote}{prefix}", start + len(needle))
        return page[start : nxt if nxt > 0 else None]
    return ""


def run_isolation_sample(root: Path, map_path: Path, out_dir: Path) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    data, error = load_map(map_path)
    if error or data is None:
        print(error, file=sys.stderr)
        return 2

    stale_map = json.loads(json.dumps(data))
    stale_hit = False
    for _, owner in iter_source_owners(stale_map):
        if str(owner.get("id")) != "ALG-QA":
            continue
        sources = owner.get("sources") or []
        if sources and isinstance(sources[0], dict):
            sources[0]["fingerprint"] = "0" * 64
            stale_hit = True
            break
    if not stale_hit:
        print("isolation stale: ALG-QA sources missing", file=sys.stderr)
        return 1
    stale_path = out_dir / "stale-map.json"
    stale_html = out_dir / "stale.html"
    stale_path.write_text(json.dumps(stale_map, ensure_ascii=False, indent=2), encoding="utf-8")
    generate(stale_path, stale_html, root, record_empty=False)
    stale_text = stale_html.read_text(encoding="utf-8")
    if STATUS_STALE not in stale_text:
        print("isolation stale: 未出现待复核", file=sys.stderr)
        return 1
    qa_html = card_html(stale_text, "algo-ALG-QA")
    if not qa_html:
        print("isolation stale: 未找到 ALG-QA 卡片", file=sys.stderr)
        return 1
    if STATUS_STALE not in qa_html or STATUS_CHECKED in qa_html:
        print("isolation stale: ALG-QA 在源变更后仍标已核对", file=sys.stderr)
        return 1

    missing_map = json.loads(json.dumps(data))
    missing_hit = False
    for _, owner in iter_source_owners(missing_map):
        if str(owner.get("id")) != "ALG-INGEST":
            continue
        sources = owner.get("sources") or []
        if sources and isinstance(sources[0], dict):
            sources[0]["path"] = "backend/src/services/does-not-exist.py"
            missing_hit = True
            break
    if not missing_hit:
        print("isolation missing: ALG-INGEST sources missing", file=sys.stderr)
        return 1
    missing_path = out_dir / "missing-map.json"
    missing_html = out_dir / "missing.html"
    missing_path.write_text(json.dumps(missing_map, ensure_ascii=False, indent=2), encoding="utf-8")
    generate(missing_path, missing_html, root, record_empty=False)
    missing_text = missing_html.read_text(encoding="utf-8")
    if "来源缺失" not in missing_text and "does-not-exist.py" not in missing_text:
        print("isolation missing: 未出现缺失提示", file=sys.stderr)
        return 1

    bad_path = out_dir / "bad.json"
    bad_html = out_dir / "bad.html"
    bad_path.write_text("{not json", encoding="utf-8")
    generate(bad_path, bad_html, root, record_empty=False)
    if "不是合法 JSON" not in bad_html.read_text(encoding="utf-8"):
        print("isolation parse: 未出现 JSON 错误提示", file=sys.stderr)
        return 1

    print(f"isolation sample passed in {out_dir}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="刷新页面功能导航 HTML")
    parser.add_argument("--project-root", type=Path, default=project_root_from_script())
    parser.add_argument("--map", type=Path, default=Path("docs/project-map.json"))
    parser.add_argument("--html", type=Path, default=Path("docs/project-console.html"))
    parser.add_argument(
        "--record-fingerprints",
        action="store_true",
        help="只为尚未记录的来源写入指纹，不把过期指纹改成已核对",
    )
    parser.add_argument(
        "--isolation-sample",
        type=Path,
        help="在指定目录写入过期指纹/缺失来源/坏 JSON 样例，不覆盖正式 HTML",
    )
    args = parser.parse_args()
    root = args.project_root.resolve()
    map_path = args.map if args.map.is_absolute() else root / args.map
    html_path = args.html if args.html.is_absolute() else root / args.html
    if args.isolation_sample:
        sample_dir = args.isolation_sample
        if not sample_dir.is_absolute():
            sample_dir = root / sample_dir
        return run_isolation_sample(root, map_path, sample_dir)
    return generate(map_path, html_path, root, record_empty=args.record_fingerprints)


if __name__ == "__main__":
    sys.exit(main())
