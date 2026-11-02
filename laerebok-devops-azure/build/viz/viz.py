"""Gjør ```vis- og ```mermaid-blokker i Markdown om til PNG-illustrasjoner.

Bruk: python3 viz.py <kildemappe> <utmappe-md> <figurmappe>

Hver blokk erstattes med en bildelenke. Bildene navngis etter en hash av
innholdet, så bare nye/endrede figurer rendres på nytt.
"""
import hashlib
import html
import json
import os
import re
import subprocess
import sys

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))

COLORS = {
    "blue":   ("#0b5cad", "#e7f0fb"),
    "teal":   ("#0f7b6c", "#e3f4f1"),
    "purple": ("#6d3fd1", "#efe9fc"),
    "orange": ("#d9480f", "#fff0e6"),
    "green":  ("#2b8a3e", "#e8f6eb"),
    "red":    ("#c92a2a", "#fdecec"),
    "gray":   ("#495057", "#f1f3f5"),
    "yellow": ("#b07d00", "#fff8db"),
    "pink":   ("#c2255c", "#fdeef4"),
    "navy":   ("#1c3d6e", "#e6ecf5"),
}
ORDER = ["blue", "teal", "purple", "orange", "green", "pink", "navy", "red", "yellow", "gray"]

CSS = """
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:Inter,'Noto Color Emoji',sans-serif;color:#1b2430;background:#fff}
#fig{width:1000px;padding:28px 30px 30px;background:#fff}
.ftitle{font-family:'Inter Display',Inter,sans-serif;font-weight:800;font-size:27px;color:#0e1a2b;margin-bottom:6px}
.fsub{font-size:17px;color:#5b6675;margin-bottom:18px}
.grid{display:grid;gap:16px}
.card{border-radius:16px;padding:18px 18px 16px;border:2px solid;position:relative}
.card .ic{font-size:40px;line-height:1;margin-bottom:10px}
.card .t{font-weight:800;font-size:20px;margin-bottom:6px}
.card .x{font-size:15.5px;line-height:1.38;color:#2b3440}
.card .tag{position:absolute;top:12px;right:14px;font-size:12px;font-weight:700;padding:3px 9px;border-radius:99px;color:#fff}
.flow{display:flex;align-items:stretch;gap:0}
.step{flex:1;border-radius:16px;padding:16px 12px;text-align:center;border:2px solid;display:flex;flex-direction:column;align-items:center}
.step .n{width:30px;height:30px;border-radius:50%;color:#fff;font-weight:800;font-size:15px;display:flex;align-items:center;justify-content:center;margin-bottom:8px}
.step .ic{font-size:38px;margin-bottom:8px;line-height:1}
.step .t{font-weight:800;font-size:17px;margin-bottom:5px}
.step .x{font-size:13.5px;line-height:1.35;color:#2b3440}
.arrow{width:34px;display:flex;align-items:center;justify-content:center;font-size:28px;color:#8a94a3;flex:0 0 34px}
.loop{margin-top:12px;border:2px dashed #8a94a3;border-top:none;height:26px;border-radius:0 0 18px 18px;position:relative;margin-left:8%;margin-right:8%}
.loop span{position:absolute;bottom:-13px;left:50%;transform:translateX(-50%);background:#fff;padding:0 12px;font-size:15px;color:#5b6675;font-weight:600}
.vflow .vstep{display:flex;align-items:center;gap:16px;border-radius:14px;border:2px solid;padding:12px 16px}
.vflow .vstep .n{width:34px;height:34px;border-radius:50%;color:#fff;font-weight:800;display:flex;align-items:center;justify-content:center;flex:0 0 34px}
.vflow .vstep .ic{font-size:30px;flex:0 0 40px;text-align:center}
.vflow .vstep .t{font-weight:800;font-size:17px}
.vflow .vstep .x{font-size:14.5px;color:#2b3440}
.vflow .down{text-align:center;color:#8a94a3;font-size:22px;line-height:24px}
.layer{border-radius:12px;padding:12px 18px;display:flex;align-items:center;gap:14px;border:2px solid;margin:0 auto 8px}
.layer .ic{font-size:30px}
.layer .t{font-weight:800;font-size:18px;min-width:220px}
.layer .x{font-size:15px;color:#2b3440}
.cmp{display:grid;gap:18px}
.col{border-radius:18px;overflow:hidden;border:2px solid}
.col .head{padding:16px 18px;color:#fff;display:flex;align-items:center;gap:12px}
.col .head .ic{font-size:38px}
.col .head .t{font-weight:800;font-size:22px}
.col .head .s{font-size:14px;opacity:.9}
.col ul{list-style:none;padding:14px 18px 16px}
.col li{font-size:15.5px;line-height:1.4;padding:6px 0 6px 30px;position:relative;border-bottom:1px dashed #d9dee5}
.col li:last-child{border-bottom:none}
.col li::before{content:attr(data-m);position:absolute;left:0;top:5px;font-size:17px}
.vs{display:flex;align-items:center;justify-content:center;font-weight:900;font-size:22px;color:#8a94a3}
.ana{display:flex;align-items:stretch;gap:0}
.ana .side{flex:1;border-radius:18px;padding:22px;text-align:center;border:2px solid}
.ana .side .ic{font-size:64px;line-height:1;margin-bottom:10px}
.ana .side .t{font-weight:800;font-size:21px;margin-bottom:6px}
.ana .side .x{font-size:15.5px;line-height:1.4;color:#2b3440}
.ana .eq{flex:0 0 70px;display:flex;align-items:center;justify-content:center;font-size:40px;color:#8a94a3;font-weight:900}
.ana .map{margin-top:14px;display:grid;gap:8px}
.ana .map div{display:flex;gap:10px;align-items:center;font-size:15px;background:#f6f8fa;border-radius:10px;padding:8px 12px}
.pyr{display:flex;flex-direction:column;align-items:center;gap:6px}
.pyr .lv{color:#fff;text-align:center;padding:12px 10px;border-radius:8px}
.pyr .lv .t{font-weight:800;font-size:18px}
.pyr .lv .x{font-size:14px;opacity:.95}
.hub{position:relative;height:520px}
.hub .c{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);width:250px;height:150px;border-radius:24px;color:#fff;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;padding:12px}
.hub .c .ic{font-size:46px}
.hub .c .t{font-weight:800;font-size:22px}
.hub .s{position:absolute;width:230px;border-radius:14px;padding:10px 12px;border:2px solid;text-align:center;transform:translate(-50%,-50%)}
.hub .s .ic{font-size:28px}
.hub .s .t{font-weight:800;font-size:16px}
.hub .s .x{font-size:13px;color:#2b3440;line-height:1.3}
.hub svg{position:absolute;inset:0}
.timeline{display:flex;flex-direction:column;gap:0}
.tl{display:flex;gap:16px;align-items:stretch}
.tl .when{flex:0 0 110px;text-align:right;font-weight:800;font-size:16px;padding-top:12px}
.tl .dot{flex:0 0 22px;display:flex;flex-direction:column;align-items:center}
.tl .dot b{width:18px;height:18px;border-radius:50%;margin-top:14px;border:3px solid #fff;box-shadow:0 0 0 2px currentColor}
.tl .dot i{flex:1;width:3px;background:#d9dee5}
.tl .what{flex:1;border-radius:12px;padding:10px 14px;margin:5px 0;border:2px solid}
.tl .what .t{font-weight:800;font-size:16px}
.tl .what .x{font-size:14px;color:#2b3440}
.stat{display:grid;gap:14px}
.stat .k{border-radius:16px;padding:18px;text-align:center;color:#fff}
.stat .k .v{font-size:38px;font-weight:900;line-height:1.1}
.stat .k .l{font-size:15px;margin-top:6px;opacity:.95}
.note{margin-top:16px;font-size:15px;color:#5b6675;text-align:center}
.mm{display:flex;justify-content:center}
"""


def col(name, i=0):
    name = name or ORDER[i % len(ORDER)]
    return COLORS.get(name, COLORS["blue"])


def e(s):
    return html.escape(str(s or "")).replace("\n", "<br>")


def head(spec):
    out = ""
    if spec.get("title"):
        out += f'<div class="ftitle">{e(spec["title"])}</div>'
    if spec.get("subtitle"):
        out += f'<div class="fsub">{e(spec["subtitle"])}</div>'
    return out


def foot(spec):
    return f'<div class="note">{e(spec["note"])}</div>' if spec.get("note") else ""


def r_cards(spec):
    items = spec["items"]
    cols = spec.get("cols", min(4, len(items)))
    h = f'<div class="grid" style="grid-template-columns:repeat({cols},1fr)">'
    for i, it in enumerate(items):
        fg, bg = col(it.get("color"), i)
        tag = f'<div class="tag" style="background:{fg}">{e(it["tag"])}</div>' if it.get("tag") else ""
        h += (f'<div class="card" style="border-color:{fg};background:{bg}">{tag}'
              f'<div class="ic">{e(it.get("icon",""))}</div>'
              f'<div class="t" style="color:{fg}">{e(it["title"])}</div>'
              f'<div class="x">{e(it.get("text",""))}</div></div>')
    return h + "</div>"


def r_flow(spec):
    steps = spec["steps"]
    h = '<div class="flow">'
    for i, s in enumerate(steps):
        fg, bg = col(s.get("color"), i)
        if i:
            h += f'<div class="arrow">{e(spec.get("arrow","➜"))}</div>'
        h += (f'<div class="step" style="border-color:{fg};background:{bg}">'
              f'<div class="n" style="background:{fg}">{i+1}</div>'
              f'<div class="ic">{e(s.get("icon",""))}</div>'
              f'<div class="t" style="color:{fg}">{e(s["title"])}</div>'
              f'<div class="x">{e(s.get("text",""))}</div></div>')
    h += "</div>"
    if spec.get("loop"):
        h += f'<div class="loop"><span>↺ {e(spec["loop"])}</span></div>'
    return h


def r_vflow(spec):
    h = '<div class="vflow">'
    for i, s in enumerate(spec["steps"]):
        fg, bg = col(s.get("color"), i)
        if i:
            h += '<div class="down">▼</div>'
        h += (f'<div class="vstep" style="border-color:{fg};background:{bg}">'
              f'<div class="n" style="background:{fg}">{i+1}</div>'
              f'<div class="ic">{e(s.get("icon",""))}</div>'
              f'<div><div class="t" style="color:{fg}">{e(s["title"])}</div>'
              f'<div class="x">{e(s.get("text",""))}</div></div></div>')
    return h + "</div>"


def r_layers(spec):
    items = spec["items"]
    n = len(items)
    h = ""
    for i, it in enumerate(items):
        fg, bg = col(it.get("color"), i)
        w = 100 if not spec.get("widen") else 60 + 40 * i / max(1, n - 1)
        h += (f'<div class="layer" style="border-color:{fg};background:{bg};width:{w}%">'
              f'<div class="ic">{e(it.get("icon",""))}</div>'
              f'<div class="t" style="color:{fg}">{e(it["title"])}</div>'
              f'<div class="x">{e(it.get("text",""))}</div></div>')
    return h


def r_compare(spec):
    cols_ = spec["columns"]
    tmpl = []
    for i in range(len(cols_)):
        if i and spec.get("vs"):
            tmpl.append("50px")
        tmpl.append("1fr")
    h = f'<div class="cmp" style="grid-template-columns:{" ".join(tmpl)}">'
    for i, c in enumerate(cols_):
        if i and spec.get("vs"):
            h += '<div class="vs">VS</div>'
        fg, bg = col(c.get("color"), i)
        h += (f'<div class="col" style="border-color:{fg};background:{bg}">'
              f'<div class="head" style="background:{fg}"><div class="ic">{e(c.get("icon",""))}</div>'
              f'<div><div class="t">{e(c["title"])}</div><div class="s">{e(c.get("sub",""))}</div></div></div><ul>')
        for p in c.get("points", []):
            m = c.get("mark", "✔️")
            if isinstance(p, dict):
                m, p = p.get("m", m), p.get("p", "")
            elif str(p).startswith(("+ ", "- ", "~ ")):
                m = {"+": "✅", "-": "⚠️", "~": "➖"}[p[0]]
                p = p[2:]
            h += f'<li data-m="{e(m)}">{e(p)}</li>'
        h += "</ul></div>"
    return h + "</div>"


def r_analogy(spec):
    L, R = spec["left"], spec["right"]
    fl, bl = col(L.get("color", "orange"))
    fr, br = col(R.get("color", "blue"))
    h = (f'<div class="ana"><div class="side" style="border-color:{fl};background:{bl}">'
         f'<div class="ic">{e(L["icon"])}</div><div class="t" style="color:{fl}">{e(L["title"])}</div>'
         f'<div class="x">{e(L.get("text",""))}</div></div><div class="eq">=</div>'
         f'<div class="side" style="border-color:{fr};background:{br}">'
         f'<div class="ic">{e(R["icon"])}</div><div class="t" style="color:{fr}">{e(R["title"])}</div>'
         f'<div class="x">{e(R.get("text",""))}</div></div></div>')
    if spec.get("map"):
        h += f'<div class="ana"><div class="map" style="flex:1;grid-template-columns:repeat({spec.get("mapcols",2)},1fr)">'
        for a, b in spec["map"]:
            h += f'<div><b>{e(a)}</b> → {e(b)}</div>'
        h += "</div></div>"
    return h


def r_pyramid(spec):
    items = spec["items"]
    n = len(items)
    h = '<div class="pyr">'
    for i, it in enumerate(items):
        fg, _ = col(it.get("color"), i)
        w = 38 + 62 * i / max(1, n - 1)
        h += (f'<div class="lv" style="background:{fg};width:{w}%"><div class="t">{e(it.get("icon",""))} {e(it["title"])}</div>'
              f'<div class="x">{e(it.get("text",""))}</div></div>')
    return h + "</div>"


def r_hub(spec):
    import math
    c = spec["center"]
    fg, _ = col(c.get("color", "navy"))
    items = spec["items"]
    W, H = 940, spec.get("height", 520)
    cx, cy = W / 2, H / 2
    rx, ry = W / 2 - 135, H / 2 - 60
    svg = f'<svg width="{W}" height="{H}">'
    sats = ""
    for i, it in enumerate(items):
        a = -math.pi / 2 + 2 * math.pi * i / len(items)
        x, y = cx + rx * math.cos(a), cy + ry * math.sin(a)
        f2, b2 = col(it.get("color"), i)
        svg += f'<line x1="{cx}" y1="{cy}" x2="{x}" y2="{y}" stroke="{f2}" stroke-width="3" stroke-dasharray="6 5"/>'
        sats += (f'<div class="s" style="left:{x}px;top:{y}px;border-color:{f2};background:{b2}">'
                 f'<div class="ic">{e(it.get("icon",""))}</div><div class="t" style="color:{f2}">{e(it["title"])}</div>'
                 f'<div class="x">{e(it.get("text",""))}</div></div>')
    svg += "</svg>"
    return (f'<div class="hub" style="height:{H}px">{svg}'
            f'<div class="c" style="background:{fg}"><div class="ic">{e(c.get("icon",""))}</div>'
            f'<div class="t">{e(c["title"])}</div><div style="font-size:14px">{e(c.get("text",""))}</div></div>{sats}</div>')


def r_timeline(spec):
    h = '<div class="timeline">'
    for i, it in enumerate(spec["items"]):
        fg, bg = col(it.get("color"), i)
        h += (f'<div class="tl"><div class="when" style="color:{fg}">{e(it["when"])}</div>'
              f'<div class="dot" style="color:{fg}"><b style="background:{fg}"></b><i></i></div>'
              f'<div class="what" style="border-color:{fg};background:{bg}"><div class="t">{e(it.get("icon",""))} {e(it["title"])}</div>'
              f'<div class="x">{e(it.get("text",""))}</div></div></div>')
    return h + "</div>"


def r_stats(spec):
    items = spec["items"]
    h = f'<div class="stat" style="grid-template-columns:repeat({spec.get("cols", len(items))},1fr)">'
    for i, it in enumerate(items):
        fg, _ = col(it.get("color"), i)
        h += f'<div class="k" style="background:{fg}"><div class="v">{e(it["value"])}</div><div class="l">{e(it["label"])}</div></div>'
    return h + "</div>"


RENDER = {"cards": r_cards, "flow": r_flow, "vflow": r_vflow, "layers": r_layers, "compare": r_compare,
          "analogy": r_analogy, "pyramid": r_pyramid, "hub": r_hub, "timeline": r_timeline, "stats": r_stats}

MERMAID_INIT = {
    "startOnLoad": False, "theme": "base", "securityLevel": "loose",
    "flowchart": {"htmlLabels": True, "useMaxWidth": False, "curve": "basis", "padding": 14, "nodeSpacing": 40, "rankSpacing": 55},
    "sequence": {"useMaxWidth": False, "actorMargin": 60, "messageFontSize": 16},
    "themeVariables": {
        "fontFamily": "Inter, Noto Color Emoji, sans-serif", "fontSize": "17px",
        "primaryColor": "#e7f0fb", "primaryBorderColor": "#0b5cad", "primaryTextColor": "#0e1a2b",
        "lineColor": "#5b6675", "secondaryColor": "#e3f4f1", "tertiaryColor": "#f6f8fa",
        "clusterBkg": "#f6f8fa", "clusterBorder": "#adb5bd", "edgeLabelBackground": "#ffffff",
        "actorBkg": "#e7f0fb", "actorBorder": "#0b5cad", "signalColor": "#1b2430", "noteBkgColor": "#fff8db",
    },
}
MERMAID_CLASSES = "\n".join(
    f"classDef {n} fill:{bg},stroke:{fg},stroke-width:2px,color:#0e1a2b" for n, (fg, bg) in COLORS.items())


def fig_html(kind, body):
    if kind == "mermaid":
        src = body.strip()
        first = next(l for l in src.splitlines() if l.strip() and not l.strip().startswith("%%"))
        if first.split()[0] in ("flowchart", "graph"):
            src += "\n" + MERMAID_CLASSES
        return ("<!doctype html><html><head><meta charset='utf-8'><style>" + CSS + "</style>"
                "<script src='../node_modules/mermaid/dist/mermaid.min.js'></script></head><body>"
                "<div id='fig'><div class='mm'><pre class='mermaid'>" + html.escape(src) + "</pre></div></div>"
                "<script>mermaid.initialize(" + json.dumps(MERMAID_INIT) + ");"
                "mermaid.run().then(()=>{const g=document.querySelector('.mm svg');const vb=g.viewBox.baseVal;const w=Math.min(940,vb.width*1.5);g.style.maxWidth='none';g.setAttribute('width',w);g.setAttribute('height',vb.height*w/vb.width);document.body.dataset.done=1}).catch(e=>{document.body.dataset.err=String(e);document.body.dataset.done=1});</script>"
                "</body></html>")
    spec = yaml.safe_load(body)
    inner = head(spec) + RENDER[spec["type"]](spec) + foot(spec)
    return ("<!doctype html><html><head><meta charset='utf-8'><style>" + CSS +
            "</style></head><body data-done='1'><div id='fig'>" + inner + "</div></body></html>")


BLOCK = re.compile(r"^```(vis|mermaid)[^\n]*\n(.*?)^```[ \t]*$", re.S | re.M)


def main(src, dst, figdir):
    os.makedirs(dst, exist_ok=True)
    os.makedirs(figdir, exist_ok=True)
    htmldir = os.path.join(HERE, "html")
    os.makedirs(htmldir, exist_ok=True)
    jobs = []
    for name in sorted(os.listdir(src)):
        if not name.endswith(".md"):
            continue
        text = open(os.path.join(src, name), encoding="utf-8").read()

        def sub(m):
            kind, body = m.group(1), m.group(2)
            caption = ""
            if kind == "vis":
                caption = (yaml.safe_load(body) or {}).get("caption", "")
            else:
                cm = re.match(r"%%\s*caption:\s*(.*)", body)
                caption = cm.group(1).strip() if cm else ""
            hsh = hashlib.sha1((kind + body + CSS + MERMAID_CLASSES).encode()).hexdigest()[:12]
            png = os.path.join(figdir, f"fig-{hsh}.png")
            if not os.path.exists(png):
                hp = os.path.join(htmldir, f"fig-{hsh}.html")
                open(hp, "w", encoding="utf-8").write(fig_html(kind, body))
                jobs.append([hp, png])
            rel = os.path.relpath(png, dst)
            return f"![{caption}]({rel}){{width=100%}}\n"

        open(os.path.join(dst, name), "w", encoding="utf-8").write(BLOCK.sub(sub, text))
    if jobs:
        jf = os.path.join(htmldir, "jobs.json")
        json.dump(jobs, open(jf, "w"))
        env = dict(os.environ, NODE_PATH=subprocess.check_output(["npm", "root", "-g"], text=True).strip())
        subprocess.run(["node", os.path.join(HERE, "render.js"), jf], check=True, env=env)
    print(f"Figurer rendret: {len(jobs)}")


if __name__ == "__main__":
    main(*sys.argv[1:4])
