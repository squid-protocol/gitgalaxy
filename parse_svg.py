import re

with open("docs/self_scan/tri_comparison_chart.svg") as f:
    svg_content = f.read()

# We need to map y coordinates to languages
lang_map = {}
for m in re.finditer(r'<text class="lang-label"[^>]*y="([\d\.]+)">(.*?)</text>', svg_content):
    y = float(m.group(1))
    lang_map[round(y, -1)] = m.group(2)

# Also check for "awaiting" languages so we don't count them as tied
awaiting = set()
for m in re.finditer(r'<text class="awaiting"[^>]*y="([\d\.]+)">(.*?)</text>', svg_content):
    y = float(m.group(1))
    awaiting.add(round(y, -1))

winners = {"G": set(), "T": set(), "C": set()}
won_langs = set()

for m in re.finditer(r'<text class="badge-label"[^>]*y="([\d\.]+)">(.*?)</text>', svg_content):
    y = float(m.group(1))
    badge = m.group(2)
    # find the matching language
    lang_y = round(y, -1)
    if lang_y in lang_map:
        lang = lang_map[lang_y]
        winners[badge].add(lang)
        won_langs.add(lang)

ties = []
for y, lang in lang_map.items():
    if y not in awaiting and lang not in won_langs:
        ties.append(lang)

print("GitGalaxy wins in:", sorted(list(winners["G"])))
print("Tree-sitter wins in:", sorted(list(winners["T"])))
print("Ties in:", sorted(ties))

