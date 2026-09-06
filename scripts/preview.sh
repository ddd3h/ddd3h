#!/usr/bin/env bash
# Render README.md the way github.com does (GitHub Markdown API, mode=markdown)
# into preview/dark.html and preview/light.html. Requires an authenticated `gh`.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p preview
gh api -X POST /markdown -f mode=markdown -f context=ddd3h/ddd3h -F text=@README.md > preview/body.html
for t in dark light; do
  bg=$([ "$t" = dark ] && echo "#0d1117" || echo "#ffffff")
  {
    printf '<!DOCTYPE html><html><head><meta charset="utf-8"><title>README preview (%s)</title><base href="../">' "$t"
    printf '<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/github-markdown-css/5.8.1/github-markdown-%s.min.css">' "$t"
    printf '<style>body{background:%s;margin:0}.markdown-body{max-width:1012px;margin:0 auto;padding:32px}</style></head><body><article class="markdown-body">' "$bg"
    cat preview/body.html
    printf '</article></body></html>'
  } > "preview/$t.html"
done
rm preview/body.html
echo "written: preview/dark.html preview/light.html (open in a browser)"
