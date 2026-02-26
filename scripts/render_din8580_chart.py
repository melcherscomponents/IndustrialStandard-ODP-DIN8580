#!/usr/bin/env python3
"""Render DIN8580 taxonomy JSON as an interactive HTML chart."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

DEFAULT_IN_JSON = "artifacts/din8580_full_taxonomy.json"
DEFAULT_OUT_HTML = "artifacts/din8580_full_taxonomy.html"

HTML_TEMPLATE = """<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>DIN8580 Full Taxonomy</title>
  <style>
    :root {
      --bg: #f4f1eb;
      --panel: #fffdf8;
      --ink: #1f2a33;
      --line: #9ca8b2;
      --accent: #005f73;
      --accent-2: #9b2226;
      --muted: #65727d;
      --node: #0b4f6c;
      --node-highlight: #bb3e03;
    }
    html, body {
      margin: 0;
      height: 100%;
      font-family: 'Avenir Next', 'Segoe UI', sans-serif;
      background: radial-gradient(circle at top right, #fffdf8, var(--bg));
      color: var(--ink);
    }
    .layout {
      display: grid;
      grid-template-rows: auto auto 1fr;
      height: 100vh;
    }
    .header {
      padding: 14px 18px 8px;
      background: var(--panel);
      border-bottom: 1px solid #e5ddd1;
    }
    .title {
      margin: 0;
      font-size: 1.15rem;
      letter-spacing: 0.02em;
    }
    .meta {
      margin-top: 4px;
      font-size: 0.85rem;
      color: var(--muted);
    }
    .controls {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 8px;
      padding: 10px 18px;
      background: var(--panel);
      border-bottom: 1px solid #e5ddd1;
    }
    input[type=\"search\"] {
      min-width: 280px;
      flex: 1;
      border: 1px solid #c7c0b6;
      border-radius: 6px;
      padding: 8px 10px;
      font-size: 0.95rem;
      background: #ffffff;
      color: var(--ink);
    }
    button {
      border: 1px solid #0f5969;
      background: var(--accent);
      color: #ffffff;
      border-radius: 6px;
      padding: 8px 10px;
      font-size: 0.9rem;
      cursor: pointer;
    }
    button.secondary {
      background: #ffffff;
      color: var(--accent);
      border-color: #7d8d99;
    }
    button:hover {
      filter: brightness(0.95);
    }
    #status {
      font-size: 0.85rem;
      color: var(--muted);
      margin-left: auto;
    }
    #chart {
      position: relative;
      overflow: hidden;
    }
    #tooltip {
      position: absolute;
      pointer-events: none;
      padding: 6px 8px;
      background: rgba(31, 42, 51, 0.95);
      color: #fff;
      border-radius: 4px;
      font-size: 0.75rem;
      transform: translate(10px, 10px);
      opacity: 0;
      transition: opacity 120ms ease;
      max-width: min(60ch, 80vw);
      z-index: 10;
    }
    .node circle {
      fill: var(--node);
      stroke: #ffffff;
      stroke-width: 1.2px;
    }
    .node text {
      font-size: 12px;
      fill: var(--ink);
      dominant-baseline: central;
    }
    .node .label-bg {
      fill: rgba(255, 255, 255, 0.94);
      stroke: #d9d2c7;
      stroke-width: 0.8px;
      rx: 3;
      ry: 3;
    }
    .node.match circle {
      fill: var(--node-highlight);
      r: 6;
    }
    .node.match text {
      fill: var(--accent-2);
      font-weight: 700;
    }
    .link {
      fill: none;
      stroke: var(--line);
      stroke-opacity: 0.8;
      stroke-width: 1.2px;
    }
    .link.match-path {
      stroke: var(--accent-2);
      stroke-width: 1.8px;
    }
  </style>
</head>
<body>
  <div class=\"layout\">
    <div class=\"header\">
      <h1 class=\"title\">DIN8580 Interactive Full Taxonomy</h1>
      <div class=\"meta\" id=\"meta\"></div>
    </div>
    <div class=\"controls\">
      <input id=\"search\" type=\"search\" placeholder=\"Search by label or raw fragment...\" />
      <button id=\"expandAll\">Expand all</button>
      <button id=\"collapseAll\" class=\"secondary\">Collapse all</button>
      <button id=\"resetView\" class=\"secondary\">Reset view</button>
      <span id=\"status\"></span>
    </div>
    <div id=\"chart\">
      <div id=\"tooltip\"></div>
    </div>
  </div>

  <script src=\"https://d3js.org/d3.v7.min.js\"></script>
  <script>
    const graphData = __GRAPH_JSON__;

    const chart = document.getElementById('chart');
    const tooltip = document.getElementById('tooltip');
    const statusEl = document.getElementById('status');
    const metaEl = document.getElementById('meta');
    const searchEl = document.getElementById('search');
    const expandAllBtn = document.getElementById('expandAll');
    const collapseAllBtn = document.getElementById('collapseAll');
    const resetViewBtn = document.getElementById('resetView');

    metaEl.textContent = `source: ${graphData.source} | nodes: ${graphData.node_count} | edges: ${graphData.edge_count} | roots: ${graphData.roots.length}`;

    const rootPayload = {
      id: 'urn:local:din8580:root',
      raw_fragment: 'DIN8580',
      label: 'DIN8580',
      children: graphData.roots,
    };

    const margin = { top: 20, right: 260, bottom: 20, left: 220 };
    const width = Math.max(chart.clientWidth, 1000);
    const height = Math.max(chart.clientHeight, 800);

    const svg = d3
      .select('#chart')
      .append('svg')
      .attr('width', width)
      .attr('height', height)
      .attr('viewBox', [0, 0, width, height]);

    const g = svg.append('g');

    const zoom = d3.zoom().scaleExtent([0.25, 2.5]).on('zoom', ({ transform }) => {
      g.attr('transform', transform);
    });
    svg.call(zoom);

    const root = d3.hierarchy(rootPayload);
    root.x0 = height / 2;
    root.y0 = 0;

    const LINE_WRAP_AT = 36;
    const LINE_HEIGHT_PX = 14;
    const DEPTH_GAP_X = 80;
    const ROW_GAP_Y = 34;
    const COLLISION_PADDING = 10;
    const DEPTH_PADDING = 58;
    const NODE_TEXT_FONT = "12px 'Avenir Next', 'Segoe UI', sans-serif";
    const textMeasureCanvas = document.createElement('canvas');
    const textMeasureCtx = textMeasureCanvas.getContext('2d');
    textMeasureCtx.font = NODE_TEXT_FONT;

    const treeLayout = d3
      .tree()
      .nodeSize([ROW_GAP_Y, DEPTH_GAP_X])
      .separation((a, b) => {
        if (a.parent === b.parent) return 1.35;
        return 1.8;
      });
    let nodeId = 0;

    root.descendants().forEach((d) => {
      d.id = ++nodeId;
      d._children = d.children;
      if (d.depth > 1) {
        d.children = null;
      }
    });

    function diagonal(link) {
      const sourceAnchorY = link.source.y + (link.source._labelRight || 0);
      const targetAnchorY = link.target.y;
      const midY = (sourceAnchorY + targetAnchorY) / 2;
      return `M${sourceAnchorY},${link.source.x}
              C${midY},${link.source.x}
               ${midY},${link.target.x}
               ${targetAnchorY},${link.target.x}`;
    }

    function wrapLabel(text, maxChars = LINE_WRAP_AT) {
      const value = (text || '').trim();
      if (!value) return [''];

      const words = value.split(/\\s+/);
      const lines = [];
      let current = '';

      for (const word of words) {
        const next = current ? `${current} ${word}` : word;
        if (next.length <= maxChars) {
          current = next;
          continue;
        }
        if (current) lines.push(current);
        current = word;
      }
      if (current) lines.push(current);
      return lines.length ? lines : [value];
    }

    function nodeLabelText(node) {
      const label = (node.data.label || '').trim();
      const number = (node.data.level_number || '').trim();
      if (!number) return label;
      return `[${number}] ${label}`.trim();
    }

    function labelHeightPx(node) {
      const lineCount = (node._labelLines && node._labelLines.length) || 1;
      return lineCount * LINE_HEIGHT_PX + 6;
    }

    function labelWidthPx(node) {
      const lines = node._labelLines || [''];
      let maxWidth = 0;
      for (const line of lines) {
        const w = textMeasureCtx.measureText(line).width;
        if (w > maxWidth) maxWidth = w;
      }
      return Math.ceil(maxWidth) + 24; // text padding + visual breathing room
    }

    function allNodes(node) {
      const out = [];
      (function visit(current) {
        out.push(current);
        const kids = current._children || [];
        kids.forEach((child) => visit(child));
      })(node);
      return out;
    }

    function resolveVerticalCollisions(nodes) {
      const byDepth = d3.group(nodes, (d) => d.depth);
      for (const depthNodes of byDepth.values()) {
        const sorted = depthNodes.slice().sort((a, b) => a.x - b.x);
        for (let i = 1; i < sorted.length; i += 1) {
          const prev = sorted[i - 1];
          const curr = sorted[i];
          const requiredGap = (labelHeightPx(prev) + labelHeightPx(curr)) / 2 + COLLISION_PADDING;
          if (curr.x - prev.x < requiredGap) {
            curr.x = prev.x + requiredGap;
          }
        }
      }
    }

    function resolveHorizontalDepthSpacing(nodes) {
      const byDepth = d3.group(nodes, (d) => d.depth);
      const depths = Array.from(byDepth.keys()).sort((a, b) => a - b);
      const yByDepth = new Map();
      let cursorY = 0;

      depths.forEach((depth) => {
        if (depth === 0) {
          yByDepth.set(depth, 0);
          return;
        }
        const prevDepth = depth - 1;
        const prevNodes = byDepth.get(prevDepth) || [];
        let prevMaxWidth = 0;
        prevNodes.forEach((n) => {
          prevMaxWidth = Math.max(prevMaxWidth, labelWidthPx(n));
        });
        cursorY = cursorY + prevMaxWidth + DEPTH_PADDING;
        yByDepth.set(depth, cursorY);
      });

      nodes.forEach((n) => {
        const resolved = yByDepth.get(n.depth);
        if (typeof resolved === 'number') {
          n.y = resolved;
        }
      });
    }

    function update(source, highlightedNodeIds = new Set(), highlightedLinkIds = new Set()) {
      treeLayout(root);

      const nodes = root.descendants();
      nodes.forEach((d) => {
        d._labelLines = wrapLabel(nodeLabelText(d));
      });
      resolveVerticalCollisions(nodes);
      resolveHorizontalDepthSpacing(nodes);
      const links = root.links();

      const minX = d3.min(nodes, (d) => d.x) - margin.top;
      const maxX = d3.max(nodes, (d) => d.x) + margin.bottom;
      const maxY = d3.max(nodes, (d) => d.y) + margin.right;

      svg.attr('viewBox', [0, minX, Math.max(width, maxY + margin.left), maxX - minX + margin.top + margin.bottom]);

      const node = g.selectAll('g.node').data(nodes, (d) => d.id);

      const nodeEnter = node
        .enter()
        .append('g')
        .attr('class', 'node')
        .attr('transform', () => `translate(${source.y0},${source.x0})`)
        .on('click', (event, d) => {
          d.children = d.children ? null : d._children;
          update(d, highlightedNodeIds, highlightedLinkIds);
        })
        .on('mousemove', (event, d) => {
          tooltip.style.opacity = 1;
          tooltip.textContent = d.data.id;
          tooltip.style.left = `${event.offsetX}px`;
          tooltip.style.top = `${event.offsetY}px`;
        })
        .on('mouseleave', () => {
          tooltip.style.opacity = 0;
        });

      nodeEnter.append('circle').attr('r', 4.5);

      nodeEnter.append('rect').attr('class', 'label-bg');

      nodeEnter
        .append('text')
        .attr('x', 12)
        .attr('text-anchor', 'start');

      const nodeMerged = node
        .merge(nodeEnter)
        .attr('class', (d) => {
          const cls = ['node'];
          if (highlightedNodeIds.has(d.id)) cls.push('match');
          return cls.join(' ');
        });

      nodeMerged
        .select('text')
        .each(function(d) {
          const textSel = d3.select(this);
          const lines = d._labelLines || [d.data.label || ''];
          textSel.text(null);
          textSel.selectAll('tspan').remove();
          const startDy = -((lines.length - 1) * 0.55);
          lines.forEach((line, idx) => {
            textSel
              .append('tspan')
              .attr('x', 12)
              .attr('dy', idx === 0 ? `${startDy}em` : '1.1em')
              .text(line);
          });
        });

      nodeMerged
        .transition()
        .duration(220)
        .attr('transform', (d) => `translate(${d.y},${d.x})`);

      // Keep labels readable by placing a background box behind each text.
      g.selectAll('g.node').each(function() {
        const nodeSel = d3.select(this);
        const text = nodeSel.select('text');
        const textEl = text.node();
        if (!textEl) return;
        const datum = nodeSel.datum();
        const bbox = textEl.getBBox();
        const boxX = bbox.x - 4;
        const boxWidth = bbox.width + 8;
        nodeSel
          .select('rect.label-bg')
          .attr('x', boxX)
          .attr('y', bbox.y - 2)
          .attr('width', boxWidth)
          .attr('height', bbox.height + 4);
        datum._labelRight = Math.max(0, boxX + boxWidth);
      });

      node.exit().transition().duration(220).attr('transform', () => `translate(${source.y},${source.x})`).remove();

      const link = g.selectAll('path.link').data(links, (d) => d.target.id);

      const linkEnter = link
        .enter()
        .insert('path', 'g')
        .attr('class', 'link')
        .attr('d', () => {
          const p = { x: source.x0, y: source.y0 };
          return diagonal({ source: p, target: p });
        });

      link
        .merge(linkEnter)
        .transition()
        .duration(220)
        .attr('d', diagonal)
        .attr('class', (d) => {
          const cls = ['link'];
          if (highlightedLinkIds.has(d.target.id)) cls.push('match-path');
          return cls.join(' ');
        });

      link
        .exit()
        .transition()
        .duration(220)
        .attr('d', () => {
          const p = { x: source.x, y: source.y };
          return diagonal({ source: p, target: p });
        })
        .remove();

      root.eachBefore((d) => {
        d.x0 = d.x;
        d.y0 = d.y;
      });
    }

    function setAllExpanded(node, expanded) {
      if (!node._children) node._children = node.children;
      node.children = expanded ? node._children : null;
      const kids = node._children || [];
      kids.forEach((child) => setAllExpanded(child, expanded));
    }

    function captureExpansionState(node) {
      const state = new Map();
      allNodes(node).forEach((n) => {
        state.set(n.id, Boolean(n.children));
      });
      return state;
    }

    function restoreExpansionState(node, state) {
      allNodes(node).forEach((n) => {
        const shouldExpand = state.get(n.id);
        n.children = shouldExpand ? n._children : null;
      });
      node.children = node._children;
    }

    function expandPath(node) {
      let current = node;
      while (current) {
        if (current._children) current.children = current._children;
        current = current.parent;
      }
    }

    let searchActive = false;
    let preSearchState = null;

    function applySearchLayoutReset() {
      setAllExpanded(root, false);
      root.children = root._children;
    }

    function runSearch(term) {
      const query = term.trim().toLowerCase();
      const nodeMatches = new Set();
      const linkMatches = new Set();

      if (!query) {
        if (searchActive && preSearchState) {
          restoreExpansionState(root, preSearchState);
        }
        searchActive = false;
        preSearchState = null;
        statusEl.textContent = `${root.descendants().length} visible nodes`;
        update(root, nodeMatches, linkMatches);
        return;
      }

      if (!searchActive) {
        preSearchState = captureExpansionState(root);
        searchActive = true;
      }

      applySearchLayoutReset();

      const matched = allNodes(root).filter((d) => {
        const label = (d.data.label || '').toLowerCase();
        const raw = (d.data.raw_fragment || '').toLowerCase();
        const level = (d.data.level_number || '').toLowerCase();
        return label.includes(query) || raw.includes(query) || level.includes(query);
      });

      matched.forEach((d) => {
        nodeMatches.add(d.id);
        expandPath(d);
        let current = d;
        while (current && current.parent) {
          linkMatches.add(current.id);
          current = current.parent;
        }
      });

      statusEl.textContent = `${matched.length} matches`;
      update(root, nodeMatches, linkMatches);
    }

    expandAllBtn.addEventListener('click', () => {
      setAllExpanded(root, true);
      update(root);
      statusEl.textContent = `${root.descendants().length} visible nodes`;
    });

    collapseAllBtn.addEventListener('click', () => {
      setAllExpanded(root, false);
      root.children = root._children;
      update(root);
      statusEl.textContent = `${root.descendants().length} visible nodes`;
    });

    resetViewBtn.addEventListener('click', () => {
      svg.transition().duration(250).call(zoom.transform, d3.zoomIdentity);
    });

    let searchTimer = null;
    searchEl.addEventListener('input', (event) => {
      const term = event.target.value;
      clearTimeout(searchTimer);
      searchTimer = setTimeout(() => runSearch(term), 120);
    });

    update(root);
    statusEl.textContent = `${root.descendants().length} visible nodes`;
  </script>
</body>
</html>
"""


def render(in_json: str, out_html: str) -> None:
    in_path = Path(in_json)
    if not in_path.exists():
        raise RuntimeError(f"Input JSON not found: {in_path}")

    try:
        payload = json.loads(in_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Failed to parse JSON from '{in_path}': {exc}") from exc

    required_fields = {"source", "node_count", "edge_count", "roots"}
    missing = required_fields - set(payload.keys())
    if missing:
        raise RuntimeError(f"Input JSON missing required fields: {', '.join(sorted(missing))}")

    rendered = HTML_TEMPLATE.replace("__GRAPH_JSON__", json.dumps(payload, ensure_ascii=False))

    out_path = Path(out_html)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(rendered, encoding="utf-8")

    print(f"Wrote HTML: {out_path}")
    print(f"source_json={in_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render DIN8580 taxonomy HTML from JSON")
    parser.add_argument("--in-json", default=DEFAULT_IN_JSON, help="Input JSON path")
    parser.add_argument("--out-html", default=DEFAULT_OUT_HTML, help="Output HTML path")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        render(in_json=args.in_json, out_html=args.out_html)
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
