"""Markdown and HTML report generation from experiment runs.

Reads run data, metrics, and artifacts from a :class:`RunDatabase` and
renders structured reports.  Markdown is the canonical format; HTML is
produced by wrapping the markdown body in a minimal styled document with
inline-base64-encoded images.
"""
from __future__ import annotations

import base64
import html as html_mod
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .run_db import RunDatabase


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _safe(text: str) -> str:
    """Escape text for safe HTML embedding."""
    return html_mod.escape(str(text))


class ReportGenerator:
    """Generate Markdown and HTML reports from one or more experiment runs.

    Parameters
    ----------
    db : RunDatabase
        The database that holds run data, metrics, and artifact records.
    """

    def __init__(self, db: RunDatabase) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Markdown
    # ------------------------------------------------------------------

    def generate_markdown(
        self,
        run_ids: list[str],
        output_path: str,
        config: dict | None = None,
    ) -> str:
        """Generate a Markdown report and write it to *output_path*.

        Parameters
        ----------
        run_ids : list[str]
            One or more run identifiers to include.
        output_path : str
            Destination file path (``.md``).
        config : dict, optional
            Report configuration.  Recognised keys:

            - ``title`` (str) — report title, default auto-generated.
            - ``include_config`` (bool) — include run configs, default True.
            - ``include_metrics`` (bool) — include metrics table, default True.
            - ``include_plots`` (bool) — include artifact plot images, default True.

        Returns
        -------
        str
            The generated Markdown text.
        """
        config = config or {}
        title = config.get("title", f"Experiment Report — {_utcnow_iso()}")
        include_config = config.get("include_config", True)
        include_metrics = config.get("include_metrics", True)
        include_plots = config.get("include_plots", True)

        runs: list[dict] = []
        all_metrics: dict[str, list[dict]] = {}
        all_artifacts: dict[str, list[dict]] = {}
        all_configs: list[dict] = []

        for rid in run_ids:
            run = self.db.get_run(rid)
            if run is None:
                continue
            runs.append(run)
            all_metrics[rid] = self.db.get_metrics(rid)
            all_artifacts[rid] = self.db.get_artifacts(rid)
            run_cfg = run.get("config", {})
            if isinstance(run_cfg, str):
                try:
                    run_cfg = json.loads(run_cfg)
                except (json.JSONDecodeError, TypeError):
                    run_cfg = {}
            all_configs.append({"run_id": rid, **run_cfg})

        sections: list[str] = []

        # Title
        sections.append(f"# {title}\n")
        sections.append(f"*Generated at {_utcnow_iso()}*\n")

        # Summary
        sections.append("## Summary\n")
        sections.append(f"- **Runs included**: {len(runs)}")
        for run in runs:
            rid = run["run_id"]
            status = run.get("status", "unknown")
            run_type = run.get("run_type", "")
            tags = self.db.get_tags(rid)
            tag_str = ", ".join(tags) if tags else "none"
            sections.append(
                f"- `{rid[:12]}` | type={run_type} | status={status} | tags={tag_str}"
            )
        sections.append("")

        # Config section
        if include_config and all_configs:
            sections.append("## Configuration\n")
            if len(all_configs) > 1:
                sections.append(self._render_config_diff(all_configs))
            else:
                sections.append("```json")
                sections.append(json.dumps(all_configs[0], indent=2, default=str))
                sections.append("```\n")

        # Metrics section
        if include_metrics:
            sections.append("## Metrics\n")
            for run in runs:
                rid = run["run_id"]
                metrics = all_metrics.get(rid, [])
                if not metrics:
                    sections.append(f"### Run `{rid[:12]}` — no metrics recorded.\n")
                    continue
                sections.append(f"### Run `{rid[:12]}`\n")
                sections.append(self._render_metrics_table(metrics))
                sections.append("")

        # Plots section
        if include_plots:
            for run in runs:
                rid = run["run_id"]
                artifacts = all_artifacts.get(rid, [])
                plot_artifacts = [
                    a for a in artifacts if a.get("artifact_type") in ("plot", "image")
                ]
                if plot_artifacts:
                    sections.append(f"## Plots — Run `{rid[:12]}`\n")
                    sections.append(self._render_plots_section(plot_artifacts))
                    sections.append("")

        md_text = "\n".join(sections)

        # Write to disk
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as fh:
            fh.write(md_text)

        # Persist report record in the database
        self.db.insert_report({
            "title": title,
            "format": "markdown",
            "content": md_text,
            "output_path": output_path,
            "run_ids": run_ids,
            "config": config,
        })

        return md_text

    # ------------------------------------------------------------------
    # HTML
    # ------------------------------------------------------------------

    def generate_html(
        self,
        run_ids: list[str],
        output_path: str,
        config: dict | None = None,
    ) -> str:
        """Generate an HTML report with embedded images.

        First renders Markdown via :meth:`generate_markdown`, then wraps
        it in a self-contained HTML document.  Image references are
        converted to inline ``data:`` URIs so the HTML file is portable.

        Parameters and return value follow the same contract as
        :meth:`generate_markdown`.
        """
        config = config or {}
        title = config.get("title", f"Experiment Report — {_utcnow_iso()}")

        # Generate the markdown body (to a temp path, we'll embed it)
        md_path = str(Path(output_path).with_suffix(".md"))
        md_text = self.generate_markdown(run_ids, md_path, config)

        # Convert markdown to basic HTML
        body_html = self._md_to_html(md_text, base_dir=str(Path(output_path).parent))

        html_doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_safe(title)}</title>
<style>
  :root {{
    --bg: #fafafa;
    --fg: #1d1d1f;
    --accent: #0071e3;
    --border: #d2d2d7;
    --card-bg: #ffffff;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    background: var(--bg);
    color: var(--fg);
    line-height: 1.6;
    padding: 2rem;
    max-width: 960px;
    margin: 0 auto;
  }}
  h1 {{ font-size: 1.8rem; margin-bottom: 0.5rem; }}
  h2 {{ font-size: 1.4rem; margin-top: 2rem; margin-bottom: 0.5rem; border-bottom: 1px solid var(--border); padding-bottom: 0.3rem; }}
  h3 {{ font-size: 1.15rem; margin-top: 1.2rem; margin-bottom: 0.4rem; }}
  table {{
    width: 100%;
    border-collapse: collapse;
    margin: 1rem 0;
    background: var(--card-bg);
    border-radius: 8px;
    overflow: hidden;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06);
  }}
  th, td {{
    text-align: left;
    padding: 0.5rem 0.75rem;
    border-bottom: 1px solid var(--border);
  }}
  th {{ background: #f5f5f7; font-weight: 600; }}
  code, pre {{
    font-family: "SF Mono", Menlo, monospace;
    font-size: 0.88rem;
    background: #f5f5f7;
    border-radius: 4px;
  }}
  pre {{ padding: 1rem; overflow-x: auto; margin: 0.8rem 0; }}
  code {{ padding: 0.15em 0.3em; }}
  img {{ max-width: 100%; height: auto; border-radius: 6px; margin: 0.5rem 0; }}
  ul {{ padding-left: 1.5rem; margin: 0.5rem 0; }}
  em {{ color: #86868b; }}
  .diff-add {{ background: #e6ffec; }}
  .diff-del {{ background: #ffebe9; }}
</style>
</head>
<body>
{body_html}
</body>
</html>"""

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as fh:
            fh.write(html_doc)

        self.db.insert_report({
            "title": title,
            "format": "html",
            "content": "",
            "output_path": output_path,
            "run_ids": run_ids,
            "config": config,
        })

        return html_doc

    # ------------------------------------------------------------------
    # private renderers
    # ------------------------------------------------------------------

    def _render_metrics_table(self, metrics: list[dict]) -> str:
        """Render a list of metric dicts as a Markdown table."""
        if not metrics:
            return "_No metrics._\n"
        header = "| Name | Value | Step | Recorded |"
        sep = "|------|------:|-----:|---------:|"
        rows: list[str] = [header, sep]
        for m in metrics:
            name = m.get("name", "")
            value = m.get("value", "")
            step = m.get("step", "")
            recorded = m.get("recorded_at", "")
            if isinstance(value, float):
                value = f"{value:.6g}"
            rows.append(f"| {name} | {value} | {step} | {recorded} |")
        return "\n".join(rows)

    def _render_config_diff(self, configs: list[dict]) -> str:
        """Render a simple key-level diff table for multiple run configs."""
        if len(configs) <= 1:
            return ""

        # Collect all keys across configs
        all_keys: set[str] = set()
        for cfg in configs:
            all_keys.update(cfg.keys())
        all_keys.discard("run_id")
        sorted_keys = sorted(all_keys)

        run_labels = [c.get("run_id", "?")[:12] for c in configs]
        header = "| Parameter | " + " | ".join(f"`{lbl}`" for lbl in run_labels) + " |"
        sep = "|-----------|" + "|".join("---" for _ in run_labels) + "|"
        rows: list[str] = [header, sep]

        for key in sorted_keys:
            values = []
            for cfg in configs:
                v = cfg.get(key, "—")
                if isinstance(v, (dict, list)):
                    v = json.dumps(v, default=str)
                values.append(str(v))
            # Highlight rows where values differ
            unique_vals = set(values)
            marker = " **" if len(unique_vals) > 1 else ""
            row = f"| {key}{marker} | " + " | ".join(values) + " |"
            rows.append(row)

        return "\n".join(rows) + "\n"

    def _render_plots_section(self, artifacts: list[dict]) -> str:
        """Render image artifact references as Markdown image tags."""
        lines: list[str] = []
        for art in artifacts:
            name = art.get("name", "plot")
            path = art.get("path", "")
            lines.append(f"### {name}\n")
            if path and os.path.isfile(path):
                lines.append(f"![{name}]({path})\n")
            else:
                lines.append(f"_Image not found: `{path}`_\n")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Markdown -> HTML converter (basic, no external deps)
    # ------------------------------------------------------------------

    def _md_to_html(self, md: str, base_dir: str = ".") -> str:
        """Convert a subset of Markdown to HTML.

        Handles headings, bold/italic/code spans, code blocks, tables,
        unordered lists, image tags, and paragraphs.  Image paths are
        resolved relative to *base_dir* and embedded as base64 data URIs.
        """
        lines = md.split("\n")
        html_parts: list[str] = []
        in_code_block = False
        in_table = False
        in_list = False
        i = 0

        while i < len(lines):
            line = lines[i]

            # Fenced code blocks
            if line.strip().startswith("```"):
                if in_code_block:
                    html_parts.append("</code></pre>")
                    in_code_block = False
                else:
                    lang = line.strip().lstrip("`").strip()
                    cls = f' class="language-{_safe(lang)}"' if lang else ""
                    html_parts.append(f"<pre><code{cls}>")
                    in_code_block = True
                i += 1
                continue

            if in_code_block:
                html_parts.append(_safe(line))
                html_parts.append("\n")
                i += 1
                continue

            stripped = line.strip()

            # Empty line: close list / table if open
            if not stripped:
                if in_list:
                    html_parts.append("</ul>")
                    in_list = False
                if in_table:
                    html_parts.append("</table>")
                    in_table = False
                i += 1
                continue

            # Headings
            if stripped.startswith("#"):
                if in_list:
                    html_parts.append("</ul>")
                    in_list = False
                hashes = 0
                for ch in stripped:
                    if ch == "#":
                        hashes += 1
                    else:
                        break
                level = min(hashes, 6)
                text = self._inline(stripped[hashes:].strip(), base_dir)
                html_parts.append(f"<h{level}>{text}</h{level}>")
                i += 1
                continue

            # Table rows
            if "|" in stripped and stripped.startswith("|"):
                cells = [c.strip() for c in stripped.split("|")[1:-1]]
                # Check for separator row
                if all(set(c) <= set("-: ") for c in cells) and cells:
                    i += 1
                    continue
                if not in_table:
                    html_parts.append("<table>")
                    in_table = True
                    # First row is header
                    html_parts.append("<tr>")
                    for c in cells:
                        html_parts.append(f"<th>{self._inline(c, base_dir)}</th>")
                    html_parts.append("</tr>")
                else:
                    html_parts.append("<tr>")
                    for c in cells:
                        html_parts.append(f"<td>{self._inline(c, base_dir)}</td>")
                    html_parts.append("</tr>")
                i += 1
                continue

            # Unordered list
            if stripped.startswith("- ") or stripped.startswith("* "):
                if not in_list:
                    html_parts.append("<ul>")
                    in_list = True
                text = self._inline(stripped[2:], base_dir)
                html_parts.append(f"<li>{text}</li>")
                i += 1
                continue

            # Paragraph / inline
            if in_list:
                html_parts.append("</ul>")
                in_list = False
            text = self._inline(stripped, base_dir)
            html_parts.append(f"<p>{text}</p>")
            i += 1

        # Close any open blocks
        if in_list:
            html_parts.append("</ul>")
        if in_table:
            html_parts.append("</table>")
        if in_code_block:
            html_parts.append("</code></pre>")

        return "\n".join(html_parts)

    def _inline(self, text: str, base_dir: str = ".") -> str:
        """Process inline markdown: images, bold, italic, code."""
        result = _safe(text)

        # Images — ![alt](path)
        import re

        def _embed_image(m: re.Match) -> str:
            alt = m.group(1)
            src = m.group(2)
            abs_path = src if os.path.isabs(src) else os.path.join(base_dir, src)
            if os.path.isfile(abs_path):
                ext = Path(abs_path).suffix.lstrip(".").lower()
                mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
                        "gif": "image/gif", "svg": "image/svg+xml"}.get(ext, "image/png")
                try:
                    with open(abs_path, "rb") as fh:
                        b64 = base64.b64encode(fh.read()).decode("ascii")
                    return f'<img src="data:{mime};base64,{b64}" alt="{_safe(alt)}">'
                except OSError:
                    return f'<img src="{_safe(src)}" alt="{_safe(alt)}">'
            return f'<img src="{_safe(src)}" alt="{_safe(alt)}">'

        result = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", _embed_image, result)

        # Bold **text**
        result = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", result)
        # Italic *text*
        result = re.sub(r"\*(.+?)\*", r"<em>\1</em>", result)
        # Inline code `text`
        result = re.sub(r"`([^`]+)`", r"<code>\1</code>", result)

        return result
