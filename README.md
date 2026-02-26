# DIN8580 Interactive Chart Pipeline

This workspace provides a reproducible pipeline to convert the DIN8580 OWL taxonomy into:

- `artifacts/din8580_full_taxonomy.json`
- `artifacts/din8580_full_taxonomy.html`

The chart covers the full taxonomy and uses humanized German labels (URI fragments with underscores converted to spaces).

## Prerequisites

- Python 3.9+
- Internet access for default OWL source download
- Internet access in browser for D3.js CDN (`https://d3js.org/d3.v7.min.js`)

No third-party Python packages are required.

## Build

Run from workspace root:

```bash
python3 scripts/build_din8580_chart.py \
  --source https://raw.githubusercontent.com/hsu-aut/IndustrialStandard-ODP-DIN8580/master/DIN8580.owl \
  --out-json artifacts/din8580_full_taxonomy.json

python3 scripts/render_din8580_chart.py \
  --in-json artifacts/din8580_full_taxonomy.json \
  --out-html artifacts/din8580_full_taxonomy.html
```

You can also pass a local OWL file path to `--source`.

## Result

Open `artifacts/din8580_full_taxonomy.html` in a browser.

Available interactions:
- Expand/collapse by clicking nodes
- Expand all / collapse all
- Pan/zoom
- Search by label or raw fragment
- Hover tooltip with full class IRI

## Notes

The full taxonomy is intentionally dense. Use search and collapse controls to focus on relevant branches.
