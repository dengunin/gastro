#!/usr/bin/env python3
"""Сборка всех тем с topics/<NN_slug>/meta.json для GitHub Pages.

Запуск: python tools/build_site.py из корня репозитория или любого каталога.
Результат: site/index.html, site/topics.html, site/topics/<NN_slug>/*.html.

Данные темы, кроме Markdown-файлов:
  sources.json    — реестр источников (ссылки, дата проверки, статус);
  verify.json     — разбор каждой пометки [ПРОВЕРИТЬ#id];
  structure.json  — порядок и заголовки полной версии, «основание» и «следующий шаг» методов;
  figures.json    — обрезка заголовка внутри схемы и пояснение «что нужно понять»;
  cases.json      — порядок и короткие названия клинических задач, плитки показателей.

Шпаргалка: плитки раскладываются по колонкам без пустот алгоритмом pack_tiles (см. docstring).
Тест: банк вопросов (4_tests.md) целиком уходит на страницу, в попытку берутся 20 случайных.
"""
import html
import hashlib
import argparse
import json
import re
import shutil
from pathlib import Path
from urllib.parse import quote, urlsplit, urlunsplit

import markdown

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "site"
SLUG = ""
TOPIC_DIR = ROOT / "topics"
IMG_SRC = TOPIC_DIR / "images"
SITE = OUTPUT
SRC_ASSETS = ROOT / "tools" / "site_assets"

BUILD_INPUTS = ([p for p in sorted(SRC_ASSETS.rglob("*")) if p.is_file()]
                + [Path(__file__).resolve(), ROOT / "tools" / "reference_topic.py"]
                + sorted((ROOT / "topics").glob("*/layout.json")))
BUILD = hashlib.sha256(b"".join(p.read_bytes() for p in BUILD_INPUTS)).hexdigest()[:12]
TOPIC_NO = ""
TOPIC_N = 0
DISCIPLINE = ""
TOPICS = []
CATALOG = False

PAGES = [  # порядок как в левом меню и в «Дальше / Назад»
    ("short", "Кратко", "Семь практических блоков для приёма"),
    ("full", "Полный материал", "Показания, подготовка, интерпретация, ограничения, следующий шаг"),
    ("card", "Шпаргалка", "Компактные правила со ссылками на пояснения и ограничения"),
    ("test", "Тест", "Режимы обучения и экзамена, повтор ошибок, история"),
    ("cases", "Клинические задачи", "Типичные случаи с поэтапным раскрытием данных"),
    ("images", "Схемы", "Иллюстрации с пояснением и увеличением"),
]
TOPIC_TITLE = ""   # заполняется в main()
ICONS = {
    "home": '<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
    "progress": '<circle cx="12" cy="12" r="9"/><path d="m8 12.5 3 3 5-6"/>',
    "repeat": '<path d="M20 11a8 8 0 1 0-2.3 5.7"/><path d="M20 4v7h-7"/>',
    "menu": '<path d="M4 6h16M4 12h16M4 18h16"/>',
    "card": '<path d="M7 3h10a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z"/><path d="M9 8h6M9 12h6M9 16h3"/>',
    "short": '<path d="M13 2 4 14h7l-1 8 9-12h-7l1-8z"/>',
    "full": '<path d="M4 4h6a3 3 0 0 1 3 3v13a2 2 0 0 0-2-2H4z"/><path d="M20 4h-6a3 3 0 0 0-3 3v13a2 2 0 0 1 2-2h7z"/>',
    "test": '<circle cx="12" cy="12" r="9"/><path d="M9.5 9.5a2.5 2.5 0 1 1 3.5 2.3c-.7.4-1 .9-1 1.7M12 17h.01"/>',
    "cases": '<path d="M4 7h16v12H4z"/><path d="M9 7V5h6v2M12 11v4M10 13h4"/>',
    "images": '<rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="9" cy="10" r="1.6"/><path d="m21 16-5-5-9 9"/>',
    "sources": '<path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1"/><path d="M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1"/>',
}


def icon(name, size=22):
    return (f'<svg class="ico" width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" '
            f'stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" '
            f'aria-hidden="true">{ICONS[name]}</svg>')


# ------------------------------------------------------------------ данные
def jload(name, default=None):
    p = TOPIC_DIR / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else (default if default is not None else {})


SRC_DATA = jload("sources.json", {"sources": []})
SOURCES = {s["id"]: s for s in SRC_DATA["sources"]}
VERIFY = jload("verify.json", {"items": {}, "findings": []})
STRUCT = jload("structure.json", {"parts": []})
FIGMETA = jload("figures.json", {})
CHECKED = ""

STATUS_LABEL = {"ok": "сверено", "part": "частично", "open": "не подтверждено", "local": "зависит от условий"}
CHIP_LABEL = {"ok": "сверено", "part": "частично", "open": "проверить", "local": "локально"}


def src_url(s):
    if s.get("pmid"):
        return f"https://pubmed.ncbi.nlm.nih.gov/{s['pmid']}/"
    if s.get("doi"):
        return f"https://doi.org/{s['doi']}"
    return s.get("url", "")


def esc(s):
    return html.escape(s, quote=True)


# ----------------------------------------------------------------- markdown
def read(name):
    return (TOPIC_DIR / name).read_text(encoding="utf-8")


def prep_md(text):
    """Починка списков под python-markdown: пустая строка перед списком, отступ вложенных."""
    out, prev = [], ""
    is_item = lambda s: re.match(r"^\s*([-*]|\d+\.)\s", s)
    for line in text.split("\n"):
        line = re.sub(r"^ {2,3}([-*]|\d+\.)\s", lambda m: "    " + m.group(0).lstrip(), line)
        if is_item(line) and prev.strip() and not is_item(prev) and not prev.startswith("    "):
            out.append("")
        out.append(line)
        prev = line
    return "\n".join(out)


def md_html(text):
    md = markdown.Markdown(extensions=["tables", "sane_lists", "md_in_html", "attr_list"])
    return rewrite_source_links(md.convert(prep_md(text)))


def md_inline(text):
    h = md_html(text).strip()
    return re.sub(r"^<p>(.*)</p>$", r"\1", h, flags=re.S)


def strip_tags(s):
    return html.unescape(re.sub(r"<[^>]+>", "", s))


def italic_pylori(s):
    return re.sub(r"(?<!\*)H\. pylori(?!\*)", "*H. pylori*", s)


# ------------------------------------------------------ текстовые подсветки
UNITS = (r"%|кПа|мкг/г|мм рт\. ст\.|ppm|мкмоль/л|ммоль/л|Ед/л|г/л|дБ/м|Ом|‰|×10⁹/л|мл|мкг|мг|г\b|л\b|"
         r"мм\b|см\b|мин(?:ут\w*)?|ч\b|час\w*|сут\w*|дн(?:ей|я|ь)\b|нед(?:ель|ели|елю|\.)?|мес(?:яц\w*|\.)?|лет\b|с\b|кг\b|ккал")
NUM_RE = re.compile(
    r"(?<![\w.,/-])((?:(?:не\s+)?(?:менее|более|свыше|до|от|около|≥|≤|>|<)\s+)?"
    r"\d+(?:[.,]\d+)?(?:\s?[–-]\s?\d+(?:[.,]\d+)?)?(?:\s?(?:и более|и менее))?"
    r"\s?(?:" + UNITS + r"))(?![\w])")
SKIP_TAGS = {"a", "code", "mark", "summary", "h1", "h2", "h3", "h4", "h5", "h6", "th", "button",
             "script", "style", "svg", "figcaption"}


def map_text_nodes(h, fn, extra_skip=()):
    """Применить fn к текстовым узлам HTML вне служебных тегов."""
    parts = re.split(r"(<[^>]+>)", h)
    stack, out = [], []
    skip = SKIP_TAGS | set(extra_skip)
    for p in parts:
        if p.startswith("<"):
            m = re.match(r"<(/?)([a-zA-Z0-9]+)", p)
            if m:
                name = m.group(2).lower()
                if m.group(1):
                    if name in stack:
                        while stack and stack.pop() != name:
                            pass
                elif not p.endswith("/>") and name not in ("br", "img", "hr", "input"):
                    stack.append(name)
            out.append(p)
        else:
            out.append(p if skip & set(stack) else fn(p))
    return "".join(out)


def hl_numbers(h):
    return map_text_nodes(h, lambda t: NUM_RE.sub(lambda m: f'<mark class="num">{m.group(1)}</mark>', t),
                          extra_skip=("p-basis",))


# ---------------------------------------------------- пометки «проверить»
def verify_chips(h, prefix=""):
    def rep(m):
        vid = m.group(1) or ""
        note = strip_tags(m.group(2)).strip().lstrip(": ").strip() or "уточнить по первоисточнику"
        it = VERIFY["items"].get(vid, {})
        st = it.get("st", "open")
        tip = note + (" — " + it["note"] if it.get("note") else "")
        href = f"{prefix}sources.html#v-{vid}" if vid else f"{prefix}sources.html"
        return (f'<a class="verify st-{st}" href="{href}" data-note="{esc(tip)}">'
                f'{CHIP_LABEL[st]}</a>')
    return re.sub(r"\[ПРОВЕРИТЬ(?:#(\w+))?(?::\s*)?(.*?)\]", rep, h, flags=re.S)


# ------------------------------------------------------ перекрёстные ссылки
REF_MAP = {}      # "8.3" -> (id, заголовок)
FULL_IDS = set()


def short_title(t):
    t = re.sub(r"\s*\([^)]*\)\s*$", "", t).strip()
    return t[:1].upper() + t[1:] if t else t


def link_refs(h, prefix=""):
    """«раздел 2.6», «разделы 8.2, 11.2» -> ссылки на полную версию (по названию раздела)."""
    def one(num):
        tgt = REF_MAP.get(num)
        if tgt:
            return f'<a class="xref" href="{prefix}#{tgt[0]}">«{html.escape(short_title(tgt[1]))}»</a>'
        return num

    def fn(t):
        def rep(m):
            nums = re.sub(r"\d+(?:\.\d+)*", lambda n: one(n.group(0)), m.group(2))
            return m.group(1) + nums
        return re.sub(r"((?i:раздел\w*|см\.)\s+)(\d+(?:\.\d+)*(?:(?:,\s*|\s+и\s+)\d+(?:\.\d+)*)*)", rep, t)
    return map_text_nodes(h, fn)


# ------------------------------------------------------------ разбор полной
def number_of(title):
    m = re.match(r"^(\d+(?:\.\d+)*)\.?\s", title)
    return m.group(1) if m else None


def parse_full(text):
    """Полный конспект -> словарь блоков по ключам: N, N.M, N#k, N*."""
    head, h2s, cur2, cur3 = [], [], None, None
    for ln in text.split("\n"):
        if ln.startswith("## "):
            cur2 = {"title": ln[3:].strip(), "intro": [], "h3": []}
            h2s.append(cur2)
            cur3 = None
        elif ln.startswith("### "):
            cur3 = {"title": ln[4:].strip(), "body": []}
            cur2["h3"].append(cur3)
        else:
            (cur3["body"] if cur3 else (cur2["intro"] if cur2 else head)).append(ln)
    blocks = {}
    for h2 in h2s:
        n = number_of(h2["title"]).rstrip(".")
        blocks[n] = {"title": h2["title"], "md": "\n".join(h2["intro"]).strip(), "h2": n, "loc": n}
        k = 0
        full = "\n".join(h2["intro"]).strip()
        for h3 in h2["h3"]:
            num = number_of(h3["title"])
            if num:
                key = num
            else:
                k += 1
                key = f"{n}#{k}"
            body = "\n".join(h3["body"]).strip()
            blocks[key] = {"title": h3["title"], "md": body, "h2": n, "loc": key}
            full += f"\n\n#### {re.sub(r'^[\\d.]+\\s+', '', h3['title'])}\n\n{body}"
        blocks[n + "*"] = {"title": h2["title"], "md": full.strip(), "h2": n, "loc": n}
    return "\n".join(head).strip(), blocks


def pull_figure(blocks, code):
    for b in blocks.values():
        if f"[ИЗОБРАЖЕНИЕ {code}]" not in b["md"]:
            continue
        lines, out, i, fig = b["md"].split("\n"), [], 0, None
        while i < len(lines):
            if lines[i].startswith(">") and f"[ИЗОБРАЖЕНИЕ {code}]" in lines[i]:
                j = i
                while j < len(lines) and lines[j].startswith(">"):
                    j += 1
                fig = "\n".join(lines[i:j])
                i = j
                continue
            out.append(lines[i])
            i += 1
        if fig:
            b["md"] = "\n".join(out)
            return fig
    return ""


def clean_template_intro(key, md):
    """Убирает служебные оговорки шаблона («Не применимо как …»), не затрагивая содержание."""
    if key in ("3", "4", "6"):
        md = re.sub(r"^Не применимо[^.]*\.\s*", "", md)
        md = re.sub(r"^Вместо [^—\n]+—\s*", "", md)
        md = re.sub(r"^\*\*[Оо]т жалобы к методу\*\*:\s*", "", md)
    if key == "1":
        md = re.sub(r"\s*Поэтому разделы[^\n]*", "", md, count=1)
    return md[:1].upper() + md[1:] if md else md


def basis_html(ids):
    if not ids:
        return ""
    chips = []
    for sid in ids:
        s = SOURCES.get(sid)
        if not s:
            continue
        url = src_url(s)
        chips.append(f'<a class="src-chip st-{s["status"]}" href="{esc(url)}" target="_blank" rel="noopener" '
                     f'title="{esc(s["cite"])}">{html.escape(s["short"])}</a>')
    return (f'<div class="basis"><span class="basis-l">Основание</span>{"".join(chips)}'
            f'<a class="basis-more" href="sources.html#src-{ids[0]}">проверка {CHECKED}</a></div>')


STEP_NAMES = {"ind": "Показания", "prep": "Подготовка", "read": "Как читать результат",
              "lim": "Ограничения", "next": "Следующий шаг"}


def classify(label):
    low = label.lower().strip(" :")
    if low.startswith("показан"):
        return "ind"
    if low.startswith(("подготовк", "как сдавать")):
        return "prep"
    if low.startswith(("противопоказ", "ограничен", "ловушк", "риск задержк", "лучевая нагрузка", "чего избегать")):
        return "lim"
    if low.startswith(("как читать", "как интерпретировать", "что получаем", "что может", "показатели качества",
                       "протоколы биопсии", "выбор эус", "виды", "беспроводная")):
        return "read"
    return None


def arrange_method(md, nxt):
    """Абзацы метода в порядке: показания → подготовка → интерпретация → ограничения → следующий шаг."""
    segs, cur = [], None
    prev_blank = True
    for ln in md.split("\n"):
        m = re.match(r"^\*\*([^*]+)\*\*", ln) if prev_blank else None
        if m:
            cur = {"step": classify(m.group(1)), "lines": [ln]}
            segs.append(cur)
        elif cur is None:
            cur = {"step": None, "lines": [ln]}
            segs.append(cur)
        else:
            cur["lines"].append(ln)
        prev_blank = not ln.strip()
    buckets = {"intro": [], "ind": [], "prep": [], "read": [], "lim": []}
    last = "intro"
    for s in segs:
        text = "\n".join(s["lines"]).strip()
        if not text:
            continue
        if s["step"] in ("ind", "prep"):      # заголовок шага уже назвал блок: убираем дублирующую метку
            lm = re.match(r"^\*\*([^*]+?)\*\*:?[ \t]*(.*)$", s["lines"][0])
            if lm:
                paren = re.search(r"\(([^)]*)\)", lm.group(1))
                note = f"*{paren.group(1)}*" if paren else ""
                rest = lm.group(2).lstrip(": ").strip()
                head = (note + (" — " if note and rest else "") + rest).strip()
                text = "\n".join(([head] if head else []) + s["lines"][1:]).strip()
                if not head and len(s["lines"]) > 1 and s["lines"][1].startswith(("-", "1.")):
                    text = "\n".join(s["lines"][1:]).strip()
        st = s["step"]
        if st:
            last = st
        elif last != "intro":
            st = last
        else:
            st = "intro"
        buckets[st if st in buckets else "intro"].append(text)
    out = []
    recognised = any(buckets[k] for k in ("ind", "prep", "read", "lim"))
    if buckets["intro"]:
        out.append("\n\n".join(buckets["intro"]))
    for key in ("ind", "prep", "read", "lim"):
        if buckets[key] and recognised:
            out.append(f"#### {STEP_NAMES[key]} {{.step .st-{key}}}\n\n" + "\n\n".join(buckets[key]))
        elif buckets[key]:
            out.append("\n\n".join(buckets[key]))
    if nxt:
        out.append(f"#### {STEP_NAMES['next']} {{.step .st-next}}\n\n{nxt}")
    return "\n\n".join(out)


def build_full_md(blocks):
    """Новый порядок полной версии. Возвращает (markdown, карта «ключ блока» -> id места)."""
    parts_md, loc_of = [], {}
    REF_MAP.clear()
    # карта ссылок вида «раздел N.M» -> (id, название)
    for part in STRUCT["parts"]:
        its = list(part.get("items", []))
        for g in part.get("groups", []):
            its += g["items"]
        for it in its:
            if "ref" in it:
                key = it["ref"].rstrip("*")
                REF_MAP[key] = (it["id"], it["title"])
                loc_of[key] = (it["id"], it["title"])
    for part in STRUCT["parts"]:       # номера разделов без собственного блока -> первый дочерний
        for it in part.get("items", []) + [x for g in part.get("groups", []) for x in g["items"]]:
            if "ref" in it and "." in it["ref"]:
                top = it["ref"].split(".")[0]
                REF_MAP.setdefault(top, (it["id"], it["title"]))
    figs = {c: pull_figure(blocks, c) for c in STRUCT.get("move_figs", [])}
    for pi, part in enumerate(STRUCT["parts"], 1):
        out = [f'## {pi}. {part["title"]} {{#{part["id"]}}}']
        out.append(f'<p class="part-lead">{html.escape(part.get("lead", ""))}</p>')
        if part.get("method"):
            out.append("@@mindex@@")

        def render(it):
            if "fig" in it:
                return figs.get(it["fig"], "")
            blk = blocks[it["ref"]]
            title = italic_pylori(it["title"])
            body = clean_template_intro(it["ref"], blk["md"])
            if part.get("method"):
                body = arrange_method(body, it.get("next", ""))
            extra = ""
            if it.get("studies"):
                body, extra = "@@studies@@", ""
            if it.get("sources"):
                body = "@@sources@@"
            cls = it.get("cls", "")
            kind = "method" if part.get("method") else "plain"
            ph = f"@@basis:{it['id']}@@\n\n" if it.get("basis") else ""
            return (f'<div class="item {kind} {cls}" markdown="1">\n\n### {title} {{#{it["id"]}}}\n\n'
                    f'{ph}{body}\n\n</div>')
        for it in part.get("items", []):
            out.append(render(it))
        for g in part.get("groups", []):
            out.append(f'<p class="grp">{html.escape(g["title"])}</p>')
            for it in g["items"]:
                out.append(render(it))
        parts_md.append("\n\n".join(out))
    return "\n\n".join(parts_md)


def mindex_html():
    chips = []
    for part in STRUCT["parts"]:
        if not part.get("method"):
            continue
        for g in part["groups"]:
            row = "".join(f'<a href="#{it["id"]}">{html.escape(it["title"].replace("H. pylori", "H. pylori"))}</a>'
                          for it in g["items"])
            chips.append(f'<div class="mi-row"><span>{html.escape(g["title"])}</span><div>{row}</div></div>')
    return f'<nav class="mindex" aria-label="Методы">{"".join(chips)}</nav>'


# --------------------------------------------------------- рисунки (схемы)
FIGS = []  # (code, title, desc_html)


def figure_html(code, title, desc, standalone=False):
    meta = FIGMETA.get(code, {})
    crop, w, h = meta.get("crop", 0), meta.get("w", 1000), meta.get("h", 1400)
    fixed_crop = "w" in meta and "h" in meta
    ratio = f"{w} / {h * (1 - crop / 100):.1f}" if fixed_crop else "auto"
    take = meta.get("takeaway", "")
    ref = meta.get("ref")
    link = ""
    if ref and ref in REF_MAP:
        link = f' <a class="xref" href="full.html#{REF_MAP[ref][0]}">Читать раздел</a>'
    tk = f'<div class="fig-take"><b>Что нужно понять.</b> {html.escape(take)}{link}</div>' if take else ""
    t = html.escape(title)
    shift = f"transform:translateY(-{crop}%)" if crop else ""
    if not fixed_crop:
        shift = "position:static;"  # Keep the source aspect ratio when no crop metadata exists.
    light = image_file(code, "light")
    dark = image_file(code, "dark")
    if not light or not dark:
        return (f'<figure class="fig" id="fig-{code}"><figcaption class="fig-title">{t}</figcaption>'
                f'<p>Схема пока не добавлена.</p><div class="fig-desc">{desc}</div></figure>')
    return (f'<figure class="fig" id="fig-{code}">'
            f'<figcaption class="fig-title"><span class="fig-no">Рис. {code}</span>{t}</figcaption>'
            f'<button class="fig-btn" type="button" data-full-light="img/{light}" data-full-dark="img/{dark}" '
            f'aria-label="Увеличить схему: {t}">'
            f'<span class="fig-crop" style="aspect-ratio:{ratio}">'
            f'<img class="img-light" style="{shift}" src="img/{light}" alt="{t}" loading="lazy">'
            f'<img class="img-dark" style="{shift}" src="img/{dark}" alt="{t}" loading="lazy">'
            f'</span><span class="fig-zoom" aria-hidden="true">Увеличить</span></button>'
            f'{tk}<details class="fig-desc"><summary>Описание схемы</summary><p>{desc}</p></details></figure>')


def replace_figures(h):
    def rep(m):
        block = m.group(0)
        code = re.search(r"ИЗОБРАЖЕНИЕ (\d+-\d+)", block).group(1)
        title = strip_tags(re.search(r"\[ИЗОБРАЖЕНИЕ [\d-]+\]\s*(.*?)</strong>", block, re.S).group(1)).strip()
        dm = re.search(r"Описание:\s*(.*?)</p>", block, re.S)
        desc = dm.group(1).strip() if dm else ""
        if code not in [f[0] for f in FIGS]:
            FIGS.append((code, title, desc))
        return figure_html(code, title, desc)
    def quote_figures(match):
        content = match.group(1)
        if "ИЗОБРАЖЕНИЕ" not in content:
            return match.group(0)
        # Adjacent Markdown quotes can contain several diagrams in distinct paragraphs.
        return re.sub(r"<p>(?:(?!</p>).)*?ИЗОБРАЖЕНИЕ(?:(?!</p>).)*?</p>", rep, content, flags=re.S)
    return re.sub(r"<blockquote>(.*?)</blockquote>", quote_figures, h, flags=re.S)


# ------------------------------------------------- исследования и источники
def studies_html(md_list, prefix=""):
    """Раздел «Ключевые исследования» -> карточки с источником и разбором."""
    order = ["lundell1999", "lai2009", "kaminski2010", "corley2014", "gyawali2024", "yadlapati2021"]
    cards = []
    items = re.split(r"(?m)^\d+\.\s+", md_list)[1:]
    for i, it in enumerate(items):
        m = re.match(r"\*\*(.*?)\*\*\s*—\s*(.*)", it.strip(), re.S)
        if not m:
            continue
        title, rest = m.group(1), m.group(2).strip()
        cm = re.match(r"(.*?\d{4})\.\s*(.*)", rest, re.S)
        who = cm.group(1).strip() if cm else ""
        body = cm.group(2) if cm else rest
        res = re.search(r"Результат:\s*(.*?)(?:\s*Что изменилось:|$)", body, re.S)
        chg = re.search(r"Что изменилось:\s*(.*)$", body, re.S)
        design = re.split(r"\s*Результат:", body)[0].strip()
        s = SOURCES.get(order[i]) if i < len(order) else None
        link = ""
        if s:
            link = (f'<a class="src-chip st-{s["status"]}" href="{esc(src_url(s))}" target="_blank" rel="noopener">'
                    f'{"PubMed" if s.get("pmid") else "DOI"}</a>'
                    f'<a class="basis-more" href="sources.html#src-{s["id"]}">{STATUS_LABEL[s["status"]]} · проверка {CHECKED}</a>')
        check = f'<p class="study-check"><b>Проверка:</b> {html.escape(s["note"])}</p>' if s else ""
        cards.append(
            f'<article class="study"><header><span class="study-no">{i + 1}</span><div><h4>{title}</h4>'
            f'<p class="study-who">{who}</p></div></header>'
            f'<p><b>Что изучали.</b> {design}</p>'
            f'<p><b>Результат.</b> {res.group(1).strip() if res else ""}</p>'
            f'<p><b>Что изменилось.</b> {chg.group(1).strip() if chg else ""}</p>'
            f'{check}<div class="study-links">{link}</div></article>')
    return f'<div class="studies">{"".join(cards)}</div>'


def sources_block_html(orig_md=""):
    items = []
    for s in SRC_DATA["sources"]:
        items.append(f'<li><a href="sources.html#src-{s["id"]}">{html.escape(s["short"])}</a> '
                     f'<span class="st-pill st-{s["status"]}">{STATUS_LABEL[s["status"]]}</span></li>')
    return ('<p>Полный реестр с ссылками, статусом проверки и замечаниями — на странице '
            '<a href="sources.html"><b>«Источники и проверка»</b></a>.</p>'
            f'<ul class="src-mini">{"".join(items)}</ul>'
            f'<details class="abbr"><summary>Список в авторской редакции (с пометками)</summary>{md_html(orig_md)}</details>')


# ----------------------------------------------------------- разбор документа
def decorate_blocks(h):
    """Callouts и сокращения."""
    h = re.sub(r"<p>(Сокращения:.*?)</p>",
               r'<details class="abbr"><summary>Сокращения</summary><p>\1</p></details>', h, count=1, flags=re.S)

    def callout(m):
        kind = "warn"
        lead = m.group(2)
        if lead.startswith(("Практические", "Расшифровка", "Что спросить")):
            kind = "tip"
        if m.group(1):
            return f'<p class="callout {kind}"><strong>{lead}'
        return f'<p class="callout {kind}"><strong>{lead}</strong>'
    h = re.sub(r"<p>(<strong>)?(Ловушки?|Важно|Подвох|Подводные камни|Ловушка)\b", callout, h)
    h = re.sub(r"<p>(<strong>)?(Практические выводы|Расшифровка вывода)\b", callout, h)
    return h


def build_doc(h, kind, parts_meta=None):
    """HTML (после верификации и подстановок) -> (intro_html, sections_html, toc_items)."""
    h = re.sub(r"^<h1>.*?</h1>\s*", "", h, count=1, flags=re.S)
    chunks = re.split(r"(?=<h2[ >])", h)
    intro, secs = chunks[0], chunks[1:]
    toc, out, counter = [], [], 0
    for i, ch in enumerate(secs):
        m = re.match(r"<h2(?: id=\"([^\"]+)\")?[^>]*>(.*?)</h2>\s*", ch, re.S)
        sid = m.group(1) or f"h2-{i + 1}"
        title, body = m.group(2), ch[m.end():]
        ttxt = strip_tags(title)
        num = number_of(ttxt)
        label = re.sub(r"^\d+(?:\.\d+)*\.?\s*", "", title)
        step = (parts_meta or {}).get(sid, "")
        toc.append({"id": sid, "title": ttxt, "step": step})
        cls = "sec"
        if kind == "short":
            low = label.lower()
            if low.startswith("срочно"):
                cls += " sec-urgent"
            elif low.startswith(("что искажает", "ошибки")):
                cls += " sec-limit"

        def h3_idx(mm):
            nonlocal counter
            if 'id="' in mm.group(0):
                return mm.group(0)
            counter += 1
            return f'<h3 id="h-{i}-{counter}"{mm.group(1)}>'
        body = re.sub(r"<h3((?: [^>]*)?)>", h3_idx, body)
        badge = f'<span class="secnum">{num}</span>' if num else ""
        stp = f'<small class="sec-step">{html.escape(step)}</small>' if step else ""
        opened = "" if sid == "p-docs" else " open"
        out.append(f'<section class="{cls}" id="{sid}"><details{opened}><summary>{badge}'
                   f'<span class="sec-ttl">{stp}<h2>{label}</h2></span><span class="chev" aria-hidden="true"></span></summary>'
                   f'<div class="sec-body">{body}</div></details></section>')
    return intro, "\n".join(out), toc


def finish(h, prefix=""):
    h = link_refs(h, prefix)
    h = hl_numbers(h)
    h = re.sub(r"<table>", '<div class="tbl"><table>', h)
    h = re.sub(r"</table>", "</table></div>", h)
    return h


def make_toc(toc):
    items = []
    for t in toc:
        items.append(f'<li><a href="#{t["id"]}" class="toc-h2">{html.escape(t["title"])}</a></li>')
    return '<ul class="toc-list">' + "".join(items) + "</ul>"


# ------------------------------------------------------------- шпаргалка
CARD_THEMES = [  # (ключ, класс)
    ("диагноз", "main"), ("красные", "red"), ("минимум", "main"), ("подготовка", "main"),
    ("когда", "main"), ("ловушки", "trap"),
]
META_RE = re.compile(r"\s*\{((?:ref|src|lim)=.*?)\}\s*$")


def parse_meta(text):
    m = META_RE.search(text)
    if not m:
        return text, {}
    meta = {}
    for part in re.split(r";\s*(?=(?:ref|src|lim)=)", m.group(1)):
        k, _, v = part.partition("=")
        meta[k.strip()] = v.strip()
    return text[:m.start()], meta


def meta_html(meta):
    if not meta:
        return ""
    bits = []
    if meta.get("ref"):
        tgt = REF_MAP.get(meta["ref"])
        if tgt:
            bits.append(f'<a class="rule-ref" href="full.html#{tgt[0]}" title="Пояснение: {esc(short_title(tgt[1]))}">Пояснение</a>')
    for sid in [x for x in meta.get("src", "").split(",") if x]:
        s = SOURCES.get(sid.strip())
        if s:
            bits.append(f'<a class="src-chip st-{s["status"]}" href="{esc(src_url(s))}" target="_blank" rel="noopener" '
                        f'title="{esc(s["cite"])}">{html.escape(s["short"])}</a>')
    lim = f'<span class="rule-lim">{md_inline(meta["lim"])}</span>' if meta.get("lim") else ""
    return f'<span class="rule-meta">{lim}<span class="rule-links">{"".join(bits)}</span></span>'


def card_items(lines, mode):
    items = []
    for ln in lines:
        txt = re.sub(r"^(?:[-*]|\d+\.)\s+", "", ln).strip()
        if not txt:
            continue
        txt, meta = parse_meta(txt)
        h = md_inline(txt)
        sep = None
        if mode == "arrow" and " → " in h:
            sep = " → "
        elif mode == "colon" and ": " in h and re.match(r"^[^:]{2,48}:\s", strip_tags(h)):
            sep = ": "
        mh = meta_html(meta)
        if sep:
            a, b = h.split(sep, 1)
            if mode == "arrow":
                items.append(f'<li class="pair"><span class="lead">{a}</span><span class="arrow">→</span>'
                             f'<span class="act">{b}</span>{mh}</li>')
            else:
                items.append(f'<li class="pair"><span class="tag">{a}</span><span class="act">{b}</span>{mh}</li>')
        else:
            items.append(f'<li class="plain"><span class="act">{h}</span>{mh}</li>')
    return items


CARD_TOC = []   # (id, заголовок) плиток шпаргалки — для левого меню
TILE_HEAD = 2.6  # высота заголовка плитки в «условных строках»


def item_heights(lines, mode, wide):
    """Оценка высоты каждой строки плитки в «условных строках» (1 = строка основного текста) — по длине текста,
    без вёрстки в браузере. wide=True — плитка на всю ширину, список в одну колонку."""
    act_cpl, tag_cpl, meta_cpl = (89, 24, 100) if wide else (33, 15, 40)
    out = []
    for ln in lines:
        txt = re.sub(r"^(?:[-*]|\d+\.)\s+", "", ln).strip()
        if not txt:
            continue
        txt, meta = parse_meta(txt)
        txt = re.sub(r"\*+", "", txt)
        a, b = None, txt
        if mode == "arrow" and " → " in txt:
            a, b = txt.split(" → ", 1)
        elif mode == "colon" and ": " in txt:
            a, b = txt.split(": ", 1)
        h = max(-(-len(b) // act_cpl), -(-len(a) // tag_cpl) if a else 1)
        meta_n = 0
        if meta.get("lim"):
            meta_n += -(-len(meta["lim"]) // meta_cpl)
        links = len("Пояснение ↗") if meta.get("ref") else 0
        links += sum(len(SOURCES[x.strip()]["short"]) + 3 for x in meta.get("src", "").split(",") if x.strip() in SOURCES)
        if links:
            meta_n += -(-links // meta_cpl)
        out.append(h + meta_n * 0.75 + 0.9)       # строка текста, строки пояснений, поля между строками
    return out


def split_balance(items):
    """Лучшее деление списка на две последовательные части: (разница высот, высота большей части)."""
    best = None
    for k in range(len(items) + 1):
        a, b = sum(items[:k]), sum(items[k:])
        if best is None or abs(a - b) < best[0]:
            best = (abs(a - b), max(a, b))
    return best


def pack_tiles(tiles):
    """Раскладка плиток шпаргалки с минимумом пустот (порядок плиток не меняется).

    Почему появлялись пустоты: плитки лежали в сетке 2×N, строка сетки равна высоте самой высокой плитки,
    и соседняя короткая плитка оставляла под собой пустое место. Растягивать текст по вертикали не нужно.
    Алгоритм (высоты — оценка по длине текста, см. item_heights):
      * у каждой плитки есть варианты: «половина» (одна колонка из двух), «на всю ширину» (wide1) и «на всю ширину,
        список в две колонки» (wide2);
      * плитки-половины подряд образуют сегмент из двух независимых колонок; делим плитки сегмента между
        колонками перебором (плиток немного) так, чтобы разница высот колонок была минимальной;
      * перебираются варианты всех плиток; выбирается раскладка с наименьшей суммарной «пустотой»
        (разница колонок в сегментах + перекос внутри плиток из двух колонок + небольшой штраф за wide2).
    На телефоне колонки «растворяются», плитки идут в исходном порядке (--i)."""
    import itertools

    def variants(t):
        if len(tiles) > 9:   # много плиток: перебор не нужен, оставляем пометки автора
            return ["wide1"] if t["wide"] else ["half"]
        return ["half", "wide1", "wide2"]

    def seg_best(seg):
        n = len(seg)
        if n == 1:
            return seg[0]["h_half"], seg, []
        best = None
        for mask in range(1, 2 ** n - 1):
            a = [t for i, t in enumerate(seg) if mask >> i & 1]
            b = [t for i, t in enumerate(seg) if not mask >> i & 1]
            order = [t["no"] for t in a + b]
            disorder = sum(1 for i in range(len(order)) for j in range(i + 1, len(order)) if order[i] > order[j])
            cost = abs(sum(t["h_half"] for t in a) - sum(t["h_half"] for t in b)) + 0.35 * disorder
            if best is None or cost < best[0]:
                best = (cost, a, b)
        return best

    def total(vs):
        cost, seg = 0.0, []
        for t, v in zip(tiles, vs):
            if v == "half":
                seg.append(t)
                continue
            if seg:
                cost += seg_best(seg)[0]
                seg = []
            if v == "wide2":
                cost += split_balance(t["items_half"])[0] + 1.0
            elif not t["wide"]:
                cost += 0.5     # на всю ширину без нужды — хуже, чем в колонке
        if seg:
            cost += seg_best(seg)[0]
        return cost

    best = min(itertools.product(*[variants(t) for t in tiles]), key=lambda vs: (total(vs), vs.count("wide2")))
    out, seg = [], []

    def flush():
        nonlocal seg
        if not seg:
            return
        if len(seg) == 1:   # одинокая плитка (сюда попадаем только если иначе не получилось) — на всю ширину
            out.append(seg[0]["html"].replace("@@cls@@", " tile-wide"))
        else:
            _, a, b = seg_best(seg)
            out.append('<div class="seg"><div class="col">' + "".join(t["html"].replace("@@cls@@", "") for t in a) +
                       '</div><div class="col">' + "".join(t["html"].replace("@@cls@@", "") for t in b) + '</div></div>')
        seg = []

    for t, v in zip(tiles, best):
        if v == "half":
            seg.append(t)
            continue
        flush()
        out.append(t["html"].replace("@@cls@@", " tile-wide" + (" tile-cols" if v == "wide2" else "")))
    flush()
    return "".join(out)


def build_card(md_text):
    lines = [l.rstrip() for l in md_text.split("\n")]
    abbr, hero, blocks, cur, preface = "", "", [], None, []
    for l in lines[1:]:
        if l.startswith("Сокращения:"):
            abbr = md_inline(l)
        elif l.startswith("Формат строки:"):
            continue
        elif l.startswith("**Одной строкой:**"):
            hero = md_inline(l.replace("**Одной строкой:**", "").strip())
            hero = hero[:1].upper() + hero[1:]
        elif re.match(r"^\*\*[^*]+\*\*(\s*\(.*\))?\s*$", l):
            m = re.match(r"^\*\*([^*]+)\*\*(?:\s*\((.*)\))?", l)
            cur = {"title": m.group(1).strip(), "hint": m.group(2) or "", "lines": []}
            blocks.append(cur)
        elif cur is not None and l.strip():
            cur["lines"].append(l)
        elif l.strip():
            preface.append(l)
    tiles = []
    for no, b in enumerate(blocks, 1):
        key = b["title"].lower()
        theme = next((c for k, c in CARD_THEMES if key.startswith(k)), "main")
        mode = "arrow" if theme == "red" else "colon" if key.startswith(("диагноз", "минимум", "подготовка")) else "none"
        lis = card_items(b["lines"], mode)
        tag = "ol" if theme == "trap" else "ul"
        hint = f'<span class="tile-hint">({html.escape(b["hint"])})</span>' if b["hint"] else ""
        title = b["title"]
        wide = key.startswith(("диагноз", "подготовка"))
        ih = item_heights(b["lines"], mode, False)
        tiles.append({"no": no, "theme": theme, "wide": wide, "title": title, "items_half": ih,
                      "h_half": TILE_HEAD + sum(ih),
                      "html": (f'<section class="tile tile-{theme}@@cls@@" id="tile-{no}" style="--i:{no}">'
                               f'<h2>{html.escape(title)}{hint}</h2><{tag} class="tile-list">{"".join(lis)}</{tag}></section>')})
    CARD_TOC.clear()
    CARD_TOC.extend({"id": f'tile-{t["no"]}', "title": t["title"]} for t in tiles)
    legend = ('<ul class="legend" aria-label="Значение цветов">'
              '<li><i class="lg lg-red"></i><b>Красный</b> — срочность</li>'
              '<li><i class="lg lg-warn"></i><b>Жёлтый</b> — ограничение или ошибка</li>'
              '<li><i class="lg lg-main"></i><b>Сливовый</b> — основное правило</li></ul>')
    body = (f'<div class="card-intro">{md_html(chr(10).join(preface))}</div>' if preface else '')
    body += f'<div class="hero-line"><span class="hero-label">Одной строкой</span><p>{hero}</p></div>{legend}'
    body += f'<div class="tiles">{pack_tiles(tiles)}</div>'
    if abbr:
        body += f'<details class="abbr"><summary>Сокращения</summary><p>{abbr}</p></details>'
    body = verify_chips(body)
    return hl_numbers(body)


# ------------------------------------------------------------------ тест
def parse_tests(text):
    body, answers = text.split("## Ответы")
    cat, questions = None, []
    cur = None
    for line in body.split("\n"):
        if line.startswith("### "):
            cat = line[4:].strip()
            continue
        if re.fullmatch(r"\*\*[^\d*][^*]*\*\*", line):
            cat = line.strip("*").strip()
            continue
        m = re.match(r"^(?:\*\*)?(\d+)\.(?:\*\*)?\s*(.*)", line)
        if m:
            cur = {"n": int(m.group(1)), "cat": cat, "q": m.group(2), "opts": []}
            questions.append(cur)
            continue
        m = re.match(r"^([АБВГ])\)\s*(.*)", line)
        if m and cur:
            cur["opts"].append(m.group(2))
        elif cur and line.strip() and not cur["opts"] and not line.startswith("#"):
            cur["q"] += " " + line.strip()
    amap = {}
    for line in answers.split("\n"):
        m = re.match(r"^(\d+)\.\s+\*\*([АБВГ])\.\*\*\s*(.*)", line)
        if m:
            amap[int(m.group(1))] = ("АБВГ".index(m.group(2)), m.group(3))
    for q in questions:
        idx, expl = amap[q["n"]]
        q["a"] = idx
        q["e"] = link_refs(verify_chips(md_inline(expl)), "full.html")
        q["q"] = md_inline(q["q"])
        q["opts"] = [md_inline(o) for o in q["opts"]]
        assert len(q["opts"]) == 4, q["n"]
    assert len(questions) == len(amap) >= 20, (len(questions), len(amap))   # в сеанс выдаётся 20 вопросов из банка
    assert len({q["n"] for q in questions}) == len(questions), "повторяющиеся номера вопросов"
    return questions


# ---------------------------------------------------------------- задачи
CASES_CFG = jload("cases.json", {})


def lab_tiles(key):
    t = CASES_CFG.get("tiles", {}).get(key)
    if not t:
        return ""
    return '<div class="lab-tiles">' + "".join(
        f'<div><span>{esc(a)}</span><mark class="lab-v">{esc(b)}</mark></div>' for a, b in t) + "</div>"


def case_shell(pos, kind, title, basis, panes, nxt):
    """Один случай: заголовок, шаги-«таблетки» и панели. Шаги открываются по мере прохождения (app.js)."""
    pills = "".join(
        f'<li><button type="button" class="cs{" on" if i == 1 else " locked"}" data-go="{i}"><i>{i}</i>'
        f'<span>{esc(p["label"])}</span></button></li>' for i, p in enumerate(panes, 1))
    body = "".join(f'<div class="pane{" on" if i == 1 else ""}" data-pane="{i}">{p["html"]}</div>'
                   for i, p in enumerate(panes, 1))
    nxt_btn = f'<a class="btn btn-primary" href="#case-{nxt}">Следующий случай →</a>' if nxt else ""
    body = body.replace("@@next@@", nxt_btn)
    return (f'<section class="case" id="case-{pos}" data-case="{pos}"><header class="case-head">'
            f'<span class="case-kicker">Случай {pos} / {kind}</span><h2>{title}</h2>{basis}</header>'
            f'<ol class="case-steps">{pills}</ol>{body}</section>')


OWN_FIELD = ('<label class="own"><span>Ваше решение <small>— по желанию, не сохраняется</small></span>'
             '<textarea rows="3" placeholder="Запишите ответ своими словами, затем сверьтесь с эталоном"></textarea></label>')


def build_staged_cases(text):
    """Типичные амбулаторные случаи: данные раскрываются по этапам. -> {исходный номер: dict}"""
    res = {}
    for c in re.split(r"(?m)^## ", text)[1:]:
        title, _, rest = c.partition("\n")
        key = re.match(r"Задача\s+(\d+)", title).group(1)
        label = re.sub(r"^Задача\s+\d+\.\s*", "", title.strip())
        basis = re.search(r"(?m)^\*\*Основание\.\*\*\s*(.*)$", rest)
        twist = re.search(r"(?m)^\*\*Подвох:\*\*\s*(.*)$", rest)
        stage_md = re.split(r"(?m)^### ", rest)[1:]
        total = len(stage_md)
        panes = []
        for si, s in enumerate(stage_md, 1):
            stitle, _, sbody = s.partition("\n")
            sbody = re.sub(r"(?m)^\*\*Подвох:\*\*.*$", "", sbody)
            q = re.search(r"\*\*Вопрос\.\*\*\s*(.*?)(?=\n\s*\*\*Ответ\.\*\*)", sbody, re.S).group(1).strip()
            a = re.search(r"\*\*Ответ\.\*\*\s*(.*)$", sbody, re.S).group(1).strip()
            data = sbody[:sbody.index("**Вопрос.**")].strip()
            name = re.sub(r"^Этап\s+\d+\.\s*", "", stitle.strip())
            if si < total:
                nxt = re.sub(r"^Этап\s+\d+\.\s*", "", re.split(r"(?m)^### ", rest)[si + 1].partition("\n")[0].strip())
                go = f'Дальше: {nxt}'
            else:
                go = "К разбору"
            panes.append({"label": name, "html": (
                f'<div class="pane-data">{md_html(data)}{lab_tiles(f"{key}.{si}")}</div>'
                f'<div class="pane-q"><h4>Вопрос</h4><p>{md_inline(q)}</p></div>{OWN_FIELD}'
                f'<div class="pane-act reveal-row"><button type="button" class="btn btn-primary reveal">Сформулировать решение <span aria-hidden="true">→</span></button>'
                f'<span class="act-hint">Ответ пока скрыт</span></div>'
                f'<div class="answer" hidden><h4>Эталонный ответ</h4>{md_html(a)}'
                f'<div class="pane-act"><button type="button" class="btn btn-primary go-next" data-go="{si + 1}">{esc(go)} <span aria-hidden="true">→</span></button></div></div>')})
        tw = f'<p class="callout warn"><strong>Подвох.</strong> {md_inline(twist.group(1)[:1].upper() + twist.group(1)[1:])}</p>' if twist else ""
        panes.append({"label": "Разбор", "html": (
            f'<h3 class="pane-h">Что запомнить</h3>{tw}'
            f'<div class="pane-act"><button type="button" class="btn restart">Пройти заново</button>@@next@@</div>')})
        b = f'<p class="case-basis"><b>Основание.</b> {md_inline(basis.group(1))}</p>' if basis else ""
        res[key] = {"kind": "Типичный амбулаторный случай", "title": md_inline(label), "basis": b, "panes": panes}
    return res


def build_pub_cases(text):
    """Случаи из публикаций (Условие / Вопросы / Эталонные ответы). -> (сокращения, {номер: dict})"""
    parts = re.split(r"(?m)^## ", text)
    head, cases = parts[0], parts[1:]
    abbr = ""
    m = re.search(r"^Сокращения:.*$", head, re.M)
    if m:
        abbr = f'<details class="abbr"><summary>Сокращения</summary><p>{md_inline(m.group(0))}</p></details>'
    res = {}
    for c in cases:
        title, _, rest = c.partition("\n")
        key = re.match(r"Задача\s+(\d+)", title).group(1)
        label = re.sub(r"^Задача\s+\d+\.\s*", "", title.strip())
        pos = {}
        for lab in ["Условие", "Вопросы", "Эталонные ответы", "Подвох", "Источник случая"]:
            mm = re.search(r"(?m)^\*\*" + lab + r"[.:]\*\*\s*", rest)
            if mm:
                pos[lab] = (mm.start(), mm.end())
        order = sorted(pos.items(), key=lambda kv: kv[1][0])
        seg = {}
        for j, (lab, (s, e)) in enumerate(order):
            end = order[j + 1][1][0] if j + 1 < len(order) else len(rest)
            seg[lab] = rest[e:end].strip()
        qs = [re.sub(r"(?m)^ {1,3}", "", re.sub(r"^\d+\.\s*", "", x.strip()))
              for x in re.split(r"(?m)^(?=\d+\.\s)", seg.get("Вопросы", "")) if x.strip()]
        # Each answer is rendered independently, outside its original numbered list.
        # Dedent continuation lines to keep nested bullets from becoming code blocks.
        ans = [re.sub(r"(?m)^ {1,3}", "", re.sub(r"^\d+\.\s*", "", x.strip()))
               for x in re.split(r"(?m)^(?=\d+\.\s)", seg.get("Эталонные ответы", "")) if x.strip()]
        qlist = "".join(f"<li>{md_inline(q)}</li>" for q in qs)
        pairs = "".join(
            f'<li class="qa"><div class="q-text">{md_inline(q)}</div><div class="ans-box">{md_html(ans[i]) if i < len(ans) else ""}</div></li>'
            for i, q in enumerate(qs))
        twist = f'<p class="callout warn"><strong>Подвох.</strong> {md_inline(seg["Подвох"][:1].upper() + seg["Подвох"][1:])}</p>' if seg.get("Подвох") else ""
        src = f'<p class="case-src"><strong>Источник случая.</strong> {md_inline(seg["Источник случая"])}</p>' if seg.get("Источник случая") else ""
        panes = [
            {"label": "Условие", "html": (
                f'<div class="pane-data">{md_html(seg.get("Условие", ""))}{lab_tiles(key)}</div>'
                f'<div class="pane-q"><h4>Вопросы</h4><ol class="q-plain">{qlist}</ol></div>{OWN_FIELD}'
                f'<div class="pane-act reveal-row"><button type="button" class="btn btn-primary go-next" data-go="2">Сформулировать решение <span aria-hidden="true">→</span></button>'
                f'<span class="act-hint">Ответ пока скрыт</span></div>')},
            {"label": "Решение", "html": (
                f'<h3 class="pane-h">Эталонные ответы</h3><ol class="qa-list">{pairs}</ol>'
                f'<div class="pane-act"><button type="button" class="btn btn-primary go-next" data-go="3">К разбору <span aria-hidden="true">→</span></button></div>')},
            {"label": "Разбор", "html": (
                f'<h3 class="pane-h">Что запомнить</h3>{twist}{src}'
                f'<div class="pane-act"><button type="button" class="btn restart">Пройти заново</button>@@next@@</div>')},
        ]
        res[key] = {"kind": "Из публикации", "title": html.escape(label), "basis": "", "panes": panes}
    return abbr, res


def build_cases_page(staged_md, pub_md):
    """Страница задач: список случаев слева, выбранный случай справа (как в макете)."""
    staged = build_staged_cases(staged_md)
    abbr, pub = build_pub_cases(pub_md)
    allc = {**staged, **pub}
    order = [k for k in CASES_CFG.get("order", []) if k in allc] + [k for k in allc if k not in CASES_CFG.get("order", [])]
    titles = CASES_CFG.get("titles", {})
    items, views, pos_of = [], [], {}
    for pos, key in enumerate(order, 1):
        pos_of[key] = pos
    for pos, key in enumerate(order, 1):
        c = allc[key]
        nxt = pos + 1 if pos < len(order) else None
        views.append(case_shell(pos, c["kind"], c["title"], c["basis"], c["panes"], nxt))
        short = titles.get(key) or re.sub(r"<[^>]+>", "", c["title"])
        items.append(f'<li><a href="#case-{pos}" data-case="{pos}"><b>{pos:02d}</b><span>{html.escape(short)}</span></a></li>')
    body = (f'<div class="cases-top"><span class="kicker">Типичные ситуации</span><span class="cases-count">Случаев в теме: {len(order)}</span></div>'
            f'<div class="cases-layout"><nav class="cases-list" aria-label="Случаи темы"><h2>Случаи темы</h2><ol>{"".join(items)}</ol></nav>'
            f'<div class="cases-view">{"".join(views)}</div></div>{abbr}')
    return body, pos_of


# ---------------------------------------------------------- страница источников
SRC_LABEL = {"ok": "Сверено по аннотации", "part": "Частично", "local": "Зависит от условий", "open": "Не подтверждено"}
GROUP_LABEL = {"eu": "Руководство", "trial": "Исследование", "case": "Случай из публикации",
               "ru": "Российский документ", "ref": "Справочник"}


def build_sources_page(locs):
    items = VERIFY["items"]
    open_n = sum(1 for it in items.values() if it["st"] == "open")
    used = {}
    for part in STRUCT["parts"]:
        for it in part.get("items", []) + [x for g in part.get("groups", []) for x in g["items"]]:
            for sid in it.get("basis", []):
                used.setdefault(sid, []).append(it)
    scnt = {}
    for s in SRC_DATA["sources"]:
        scnt[s["status"]] = scnt.get(s["status"], 0) + 1

    stats = (f'<div class="stat-row"><div><b>{len(SRC_DATA["sources"])}</b><span>источников</span></div>'
             f'<div><b>{len(items)}</b><span>замечаний в разборе</span></div>'
             f'<div><b>{open_n}</b><span>остаются неопределёнными</span></div></div>')
    note = (f'<div class="note-box"><h3>Что означает статус проверки</h3>'
            f'<p>Библиография и аннотации сверены. Полные тексты не проверены; неопределённость в числовых правилах сохранена. '
            f'{html.escape(SRC_DATA["how"])}</p>'
            '<ul class="st-legend">'
            '<li><span class="src-status st-ok">Сверено по аннотации</span> найдено и согласуется с текстом</li>'
            '<li><span class="src-status st-part">Частично</span> часть утверждений не проверена</li>'
            '<li><span class="src-status st-local">Зависит от условий</span> прибор, лаборатория, регион, инструкция</li>'
            '<li><span class="src-status st-open">Не подтверждено</span> нужна сверка по первоисточнику</li></ul></div>')
    chips = [f'<button type="button" class="chip on" data-st="all">Все <small>{len(SRC_DATA["sources"])}</small></button>']
    for st in ("ok", "part", "local", "open"):
        if scnt.get(st):
            chips.append(f'<button type="button" class="chip" data-st="{st}">{SRC_LABEL[st]} <small>{scnt[st]}</small></button>')
    filt = f'<div class="chips" role="group" aria-label="Фильтр источников по статусу" data-filter="#src-list .src-card">{"".join(chips)}</div>'

    group_order = list(GROUP_LABEL)
    srcs = sorted(SRC_DATA["sources"], key=lambda s: group_order.index(s["group"]) if s["group"] in group_order else 99)
    cards = []
    for s in srcs:
        links = []
        if s.get("pmid"):
            links.append(f'<a href="https://pubmed.ncbi.nlm.nih.gov/{s["pmid"]}/" target="_blank" rel="noopener">PubMed</a>')
        if s.get("doi"):
            links.append(f'<a href="https://doi.org/{s["doi"]}" target="_blank" rel="noopener">DOI</a>')
        if s.get("url"):
            links.append(f'<a href="{esc(s["url"])}" target="_blank" rel="noopener">Документ</a>')
        where = ""
        if s["id"] in used:
            where = ('<p class="src-where">Используется: ' +
                     ", ".join(f'<a href="full.html#{it["id"]}">{html.escape(it["title"])}</a>' for it in used[s["id"]]) + "</p>")
        cards.append(
            f'<article class="src-card" id="src-{s["id"]}" data-st="{s["status"]}">'
            f'<div class="src-main"><span class="src-kind">{GROUP_LABEL.get(s["group"], "")}</span><h3>{html.escape(s["short"])}</h3>'
            f'<p class="src-cite">{html.escape(s["cite"])}</p><p class="src-note">{html.escape(s["note"])}</p>{where}</div>'
            f'<div class="src-side"><span class="src-status st-{s["status"]}">{SRC_LABEL[s["status"]]}</span>'
            f'<span class="src-links">{" / ".join(links)}</span></div></article>')

    finds = "".join(f'<li><b>{html.escape(f["title"])}.</b> {html.escape(f["text"])}</li>' for f in VERIFY["findings"])
    rows = []
    for k in sorted(items, key=lambda k: ("fsc".index(k[0]), int(k[1:]))):
        it = items[k]
        loc = locs.get(k, {})
        where = (f'<a href="{loc["page"]}#{loc["id"]}">{html.escape(loc["title"])}</a>' if loc.get("id") else html.escape(loc.get("title", "")))
        src = " ".join(f'<a class="src-ref" href="#src-{x}">{html.escape(SOURCES[x]["short"])}</a>' for x in it.get("src", []) if x in SOURCES)
        rows.append(
            f'<tr id="v-{k}" data-st="{it["st"]}"><td class="v-no">{k}</td><td>{where}</td>'
            f'<td class="v-snip">{html.escape(loc.get("snippet", ""))}</td>'
            f'<td><span class="src-status st-{it["st"]}">{SRC_LABEL[it["st"]] if it["st"] != "ok" else "Сверено"}</span>'
            f'{" <small>пометка снята</small>" if it.get("closed") else ""}</td>'
            f'<td>{html.escape(it["note"])} {src}</td></tr>')
    rcnt = {}
    for it in items.values():
        rcnt[it["st"]] = rcnt.get(it["st"], 0) + 1
    rchips = [f'<button type="button" class="chip on" data-st="all">Все <small>{len(items)}</small></button>']
    for st in ("open", "part", "local", "ok"):
        if rcnt.get(st):
            rchips.append(f'<button type="button" class="chip" data-st="{st}">{SRC_LABEL[st] if st != "ok" else "Закрыто источником"} <small>{rcnt[st]}</small></button>')
    rfilt = f'<div class="chips" role="group" aria-label="Фильтр замечаний по статусу" data-filter="#remarks-table tbody tr">{"".join(rchips)}</div>'
    table = (f'<div class="tbl v-tbl" id="remarks-table"><table><thead><tr><th>№</th><th>Где в тексте</th><th>Что отмечено</th>'
             f'<th>Статус</th><th>Что выяснили</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>')
    return (f'<div class="page-head">{crumbs("Источники")}<h1>Источники</h1>'
            f'<p class="lead-p">Первоисточники, версии документов и границы проверки.</p>'
            f'<p class="stamp">Срез реестра: {CHECKED}</p></div>'
            f'{note}{stats}'
            f'<section id="sources-list" class="src-sec">{filt}<div class="src-list" id="src-list">{"".join(cards)}</div></section>'
            f'<section id="remarks" class="src-sec"><h2 class="sh">Замечания проверки</h2>'
            f'<p class="sec-lead">Каждая пометка «проверить» из текста разобрана отдельно. Жёлтым отмечено то, что остаётся неподтверждённым.</p>'
            f'<h3 class="sh3">Главное</h3><ul class="finds">{finds}</ul>'
            f'<h3 class="sh3">Все пометки</h3>{rfilt}{table}</section>')


# ---------------------------------------------------------------- шаблон
NAV = [("index", "Обзор", "home"), ("short", "Кратко", "short"), ("full", "Полный материал", "full"),
       ("card", "Шпаргалка", "card"), ("test", "Тест", "test"), ("cases", "Клинические задачи", "cases"),
       ("images", "Схемы", "images"), ("sources", "Источники", "sources")]
NAV_LABEL = {k: lab for k, lab, _ in NAV}
SUBNAV = {}   # страница -> [(ссылка, подпись)]; заполняется в main(), раскрывается в левом меню под активным разделом


def crumbs(last=None):
    topic = html.escape(f"Тема {TOPIC_N}. {TOPIC_TITLE}")
    t = f'<a href="index.html">{topic}</a>' if last else f'<span aria-current="page">{topic}</span>'
    tail = f'<i>/</i><span aria-current="page">{html.escape(last)}</span>' if last else ""
    return f'<nav class="crumbs" aria-label="Путь"><a href="../../topics.html">Все темы</a><i>/</i>{t}{tail}</nav>'


def side_html(fname):
    if CATALOG:
        return ('<aside class="side" id="side" aria-label="Меню"><div class="side-head"><b>Меню</b>'
                '<button type="button" class="side-close" aria-label="Закрыть меню">×</button></div>'
                '<nav><ul class="side-list"><li><a class="side-link" href="index.html">Главная</a></li>'
                '<li><a class="side-link" href="topics.html">Все темы</a></li></ul></nav></aside>')
    learn = [("../../topics.html", "Все темы", "home", fname == "topics"),
             ("test.html#quiz-hist", "Мой прогресс", "progress", False),
             ("test.html?mode=errors", "Повторить ошибки", "repeat", False)]
    if not STRUCT.get("parts") and not jload("layout.json").get("reference"):
        learn = learn[:1]
    own = "".join(f'<li><a class="side-link{" is-on" if on else ""}" href="{h}">{icon(ic, 20)}<span>{lab}</span></a></li>'
                  for h, lab, ic, on in learn)
    items = []
    for k, lab, ic in NAV:
        href = "index.html" if k == "index" else f"{k}.html"
        active = k == fname
        sub = ""
        if SUBNAV.get(k):
            sub = (f'<ul class="side-sub"{"" if active else " hidden"}>' + "".join(
                f'<li><a href="{k}.html{h}">{html.escape(l)}</a></li>' for h, l in SUBNAV[k]) + "</ul>")
        cur = ' aria-current="page"' if active else ""
        items.append(f'<li data-page="{k}" class="side-item{" is-active" if active else ""}"><a class="side-link{" is-on" if active else ""}" '
                     f'href="{href}"{cur}>{icon(ic, 20)}<span>{lab}</span></a>{sub}</li>')
    return (f'<aside class="side" id="side" aria-label="Меню"><div class="side-head"><b>Меню</b>'
            f'<button type="button" class="side-close" aria-label="Закрыть меню">×</button></div>'
            f'<nav><div class="side-h">Моё обучение</div><ul class="side-list">{own}</ul>'
            f'<div class="side-h">Эта тема</div><ul class="side-list">{"".join(items)}</ul></nav></aside>')


def page_shell(fname, title, body, desc="", extra_body_class="", head_extra="", script_extra=""):
    asset_root = "assets/" if CATALOG else "../../assets/"
    home_url = "index.html" if CATALOG else "../../index.html"
    topics_url = "topics.html" if CATALOG else "../../topics.html"
    source_footer = (f' · <a href="sources.html">Источники</a>'
                     + (f' · дата сверки источников: {CHECKED}' if CHECKED else '')) if not CATALOG else ''
    tabs = "".join(
        f'<a href="{k}.html" class="tab{" is-active" if k == fname else ""}">{icon(k, 20)}<span>{lab.replace("Клинические задачи", "Задачи").replace("Полный материал", "Полностью")}</span></a>'
        for k, lab, _ in PAGES)
    if CATALOG:
        tabs = ''
    fab = (f'<button type="button" class="menu-fab" id="menu-fab"'
           f'{"" if SUBNAV.get(fname) else " hidden"}>{icon("full", 18)}<span>Разделы</span></button>')
    topic_line = html.escape(f"Тема {TOPIC_N} · {TOPIC_TITLE}")
    if CATALOG:
        topic_line = f"Тем: {len(TOPICS)}"
    page_title = (title if title == DISCIPLINE else f"{title} · {DISCIPLINE}") if CATALOG else f"{title} · Тема {TOPIC_N} · {DISCIPLINE}"
    fonts = "".join(f'<link rel="preload" href="{asset_root}fonts/{f}" as="font" type="font/ttf" crossorigin>'
                    for f in ("Montserrat-Medium.ttf", "Montserrat-SemiBold.ttf", "CormorantGaramond-Bold.ttf"))
    return f"""<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{html.escape(page_title)}</title>
<meta name="description" content="{html.escape(desc)}">
<meta name="color-scheme" content="light dark">
<link rel="icon" type="image/svg+xml" href="{asset_root}brand/favicon.svg">
<script>try{{var t=localStorage.getItem('theme');if(!t)t=matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light';document.documentElement.dataset.theme=t}}catch(e){{document.documentElement.dataset.theme='light'}}</script>
{fonts}
<link rel="stylesheet" href="{asset_root}style.css?v={BUILD}">
{head_extra}
</head>
<body class="page-{fname} {extra_body_class}" data-page="{fname}" data-topic="{esc(SLUG) if not CATALOG else ''}" data-search-src="assets/search.js">
<div class="progress" id="progress" aria-hidden="true"></div>
<header class="topbar">
  <button type="button" class="tool menu-btn" id="menu-btn" aria-label="Открыть меню">{icon("menu", 22)}</button>
  <a class="brand" href="{home_url}" aria-label="gunina.doctor — на главную"><img class="b-sign b-light" src="{asset_root}brand/signature-light.svg" alt="gunina.doctor, врач Анастасия Гунина"><img class="b-sign b-dark" src="{asset_root}brand/signature-dark.svg" alt=""><img class="b-mark b-light" src="{asset_root}brand/mark-plum.svg" alt="АГ"><img class="b-mark b-dark" src="{asset_root}brand/mark-light.svg" alt=""></a>
  <a class="disc" href="{topics_url}" title="Все темы"><b>{html.escape(DISCIPLINE)}</b><span>{topic_line}</span></a>
  <div class="tools">
    <button type="button" class="tool" id="search-btn" aria-label="Поиск (Ctrl+K)" title="Поиск (Ctrl+K)"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg></button>
    <button type="button" class="tool" id="theme-btn" aria-label="Сменить тему" title="Светлая / тёмная тема"><svg class="i-moon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/></svg><svg class="i-sun" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg></button>
  </div>
</header>
<div class="shell">
{side_html(fname)}
<div class="side-scrim" id="side-scrim"></div>
<main class="content" id="main">
{body}
</main>
</div>
{fab}
<nav class="tabbar" aria-label="Разделы темы">{tabs}</nav>
<div class="search-modal" id="search-modal" hidden>
  <div class="search-box" role="dialog" aria-label="Поиск по теме">
    <input type="search" id="search-input" placeholder="Поиск по теме: например, «Бостонская», «кальпротектин», «ИПП»" autocomplete="off">
    <div class="search-results" id="search-results"></div>
    <div class="search-foot">Esc — закрыть</div>
  </div>
</div>
<div class="lightbox" id="lightbox" hidden>
  <div class="lb-bar">
    <button type="button" class="lb-btn" data-z="out" aria-label="Уменьшить">−</button>
    <button type="button" class="lb-btn" data-z="in" aria-label="Увеличить">+</button>
    <button type="button" class="lb-btn lb-reset" data-z="reset">Сбросить</button>
    <span class="lb-hint">Колесо или щипок — масштаб, перетаскивание — перемещение</span>
    <button type="button" class="lb-close" aria-label="Закрыть">×</button>
  </div>
  <div class="lb-stage" id="lb-stage"><img alt="" draggable="false"></div>
</div>
<footer class="site-foot"><b>gunina<span>.</span>doctor</b> · врач Анастасия Гунина · {html.escape(DISCIPLINE)}{source_footer}</footer>
<script src="{asset_root}app.js?v={BUILD}" defer></script>
<script src="{asset_root}navigation.js?v={BUILD}" defer></script>
{script_extra}
</body>
</html>"""


def pager(fname):
    keys = [k for k, _, _ in PAGES]
    i = keys.index(fname)
    prev_ = f'<a class="pg pg-prev" href="{keys[i-1]}.html"><small>Назад</small><span>{PAGES[i-1][1]}</span></a>' if i > 0 else "<span></span>"
    next_ = f'<a class="pg pg-next" href="{keys[i+1]}.html"><small>Дальше</small><span>{PAGES[i+1][1]}</span></a>' if i < len(keys) - 1 else "<span></span>"
    return f'<nav class="pager">{prev_}{next_}</nav>'


def page_head(fname, title, sub, words=None):
    meta = ""
    if words:
        meta = f'<span class="meta-pill">≈ {max(1, round(words / 200))} мин чтения</span>'
    return (f'<div class="page-head">{crumbs(NAV_LABEL[fname])}'
            f'<h1>{html.escape(title)}</h1><p class="lead-p">{sub}</p>{meta}</div>')


def word_count(h):
    return len(strip_tags(h).split())


def fmt_min(m):
    m = int(round(m))
    if m < 90:
        return f"{m} мин"
    h, r = divmod(m, 60)
    return f"{h} ч {r:02d} мин" if r else f"{h} ч"


# ---------------------------------------------------------------- сборка
def build_detailed_topic():
    (SITE / "assets").mkdir(parents=True, exist_ok=True)
    (SITE / "img").mkdir(exist_ok=True)
    copy_images()

    full_md, short_md = read("1_full.md"), read("2_short.md")
    card_md, tests_md, cases_md = read("3_card.md"), read("4_tests.md"), read("5_cases.md")
    staged_md = read("5_cases_staged.md")
    topic_title = TOPIC_TITLE

    search = []

    def index_doc(page, label, secs_html):
        for m in re.finditer(r'<section class="[^"]*" id="([^"]+)">(.*?)</section>', secs_html, re.S):
            sid, inner = m.group(1), m.group(2)
            parts = re.split(r'(?=<h3[^>]* id=")', inner)
            h2t = strip_tags(re.search(r"<h2[^>]*>(.*?)</h2>", inner, re.S).group(1))
            for p in parts:
                m3 = re.match(r'<h3[^>]* id="([^"]+)"[^>]*>(.*?)</h3>', p, re.S)
                text = re.sub(r"\s+", " ", strip_tags(re.sub(r"</(p|li|tr|h\d|div)>", " </\\1>", p))).strip()
                search.append({"p": page, "l": label, "a": m3.group(1) if m3 else sid,
                               "t": h2t if not m3 else f"{h2t} › {strip_tags(m3.group(2))}", "x": text})

    # --- полная версия: новый порядок
    head_md, blocks = parse_full(full_md)
    new_md = head_md + "\n\n" + build_full_md(blocks)
    for part in STRUCT["parts"]:
        FULL_IDS.add(part["id"])
        for it in part.get("items", []) + [x for g in part.get("groups", []) for x in g["items"]]:
            if "id" in it:
                FULL_IDS.add(it["id"])
    studies_src = blocks["19"]["md"]
    h = md_html(new_md)
    h = h.replace("<p>@@mindex@@</p>", mindex_html())
    h = h.replace("<p>@@studies@@</p>", studies_html(studies_src))
    h = h.replace("<p>@@sources@@</p>", sources_block_html(blocks["22"]["md"]))
    h = re.sub(r"<p>@@basis:([\w-]+)@@</p>",
               lambda m: basis_html(next((it.get("basis", []) for it in all_items() if it.get("id") == m.group(1)), [])), h)
    FIGS.clear()
    h = replace_figures(h)
    h = verify_chips(h)
    h = decorate_blocks(h)
    parts_meta = {p["id"]: p["step"] for p in STRUCT["parts"]}
    f_intro, f_secs, f_toc = build_doc(h, "full", parts_meta)
    figs_full = list(FIGS)
    f_secs_final = finish(f_secs)
    f_intro_final = finish(f_intro)
    index_doc("full.html", "Полный материал", f_secs_final)

    # --- краткая
    FIGS.clear()
    hs = md_html(short_md)
    hs = verify_chips(hs)
    hs = decorate_blocks(hs)
    s_intro, s_secs, s_toc = build_doc(hs, "short")
    s_secs_final = hl_numbers(re.sub(r"<table>", '<div class="tbl"><table>', s_secs).replace("</table>", "</table></div>"))
    s_intro_final = hl_numbers(s_intro)
    index_doc("short.html", "Кратко", s_secs_final)

    # --- шпаргалка
    card_body = build_card(card_md)
    for m in re.finditer(r'<section class="tile[^"]*"[^>]*id="(tile-\d+)"[^>]*><h2>(.*?)</h2>(.*?)</section>', card_body, re.S):
        search.append({"p": "card.html", "l": "Шпаргалка", "a": m.group(1), "t": strip_tags(m.group(2)),
                       "x": re.sub(r"\s+", " ", strip_tags(m.group(3)))})

    # --- тесты
    questions = parse_tests(tests_md)   # в поиск вопросы не попадают: нет якорей, а разбор раскрыл бы ответ

    # --- задачи
    cases_body, case_pos = build_cases_page(staged_md, cases_md)
    cases_body = hl_numbers(link_refs(verify_chips(cases_body), "full.html"))
    for m in re.finditer(r'<section class="case" id="(case-\d+)"[^>]*>(.*?)</section>', cases_body, re.S):
        search.append({"p": "cases.html", "l": "Клинические задачи", "a": m.group(1),
                       "t": strip_tags(re.search(r"<h2>(.*?)</h2>", m.group(2)).group(1)),
                       "x": re.sub(r"\s+", " ", strip_tags(m.group(2)))})

    # --- места пометок для страницы источников
    locs = {}
    id_by_key = {}
    for part in STRUCT["parts"]:
        for it in part.get("items", []) + [x for g in part.get("groups", []) for x in g["items"]]:
            if "ref" in it:
                id_by_key[it["ref"]] = it

    def scan(md, prefix, page, kv=None):
        for m in re.finditer(r"\[ПРОВЕРИТЬ#(\w+)(?::\s*)?(.*?)\]", md, re.S):
            vid = m.group(1)
            if vid in locs:
                continue
            ctx = md[max(0, m.start() - 90):m.start()].replace("\n", " ").lstrip("-*| ").strip()
            ctx = re.sub(r"[*|]", "", ctx)
            if len(ctx) > 80:
                ctx = "…" + ctx[-80:].split(" ", 1)[-1]
            snippet = ((ctx + " ") if ctx else "") + (m.group(2).strip() or "без пояснения")
            locs[vid] = {"snippet": snippet, "page": page}
            if kv:
                locs[vid].update(kv)
    for key, b in blocks.items():
        if key.endswith("*"):
            continue
        it = id_by_key.get(key) or id_by_key.get(key + "*")
        before = set(locs)
        scan(b["md"], "f", "full.html")
        for vid in set(locs) - before:
            if it:
                locs[vid].update({"id": it["id"], "title": it["title"]})
            else:
                locs[vid].update({"id": "p-docs", "title": "Паспорт темы и опорные документы"})
    for vid in VERIFY["items"]:
        if vid.startswith("f") and vid not in locs:
            it = VERIFY["items"][vid]
            locs[vid] = {"page": "full.html", "id": "s-19", "title": "Ключевые исследования", "snippet": it.get("was", "")}
    scan(short_md, "s", "short.html", {"id": "", "title": "Кратко: вводный абзац"})
    scan(cases_md, "c", "cases.html", {"id": f"case-{case_pos['1']}", "title": "Случаи из публикаций"})
    for vid, it in VERIFY["items"].items():
        if vid.startswith("c") and vid not in locs:
            locs[vid] = {"page": "cases.html", "id": f"case-{case_pos['2']}", "title": "Случаи из публикаций (источник случая)", "snippet": it.get("was", "")}
        if vid.startswith("f") and it.get("closed"):
            locs[vid]["snippet"] = it.get("was", "")
            locs[vid]["id"], locs[vid]["title"] = "s-19", "Ключевые исследования"
    for vid, l in locs.items():
        if l.get("title") == "Случаи из публикаций" and vid.startswith("c"):
            l["id"] = f"case-{case_pos['1']}" if vid in ("c1", "c2", "c3") else f"case-{case_pos['2']}"
    src_body = build_sources_page(locs)
    for s in SRC_DATA["sources"]:
        search.append({"p": "sources.html", "l": "Источники", "a": f"src-{s['id']}", "t": s["short"],
                       "x": s["cite"] + " " + s["note"]})

    wc_full, wc_short = word_count(f_secs_final), word_count(s_secs_final)
    card_sub = strip_tags(re.search(r'<div class="hero-line">.*?<p>(.*?)</p>', card_body, re.S).group(1))
    t_short, t_full = wc_short / 200, wc_full / 200

    # ===== страницы
    # главная: три маршрута
    def step(k, label, minutes, note=""):
        n = f"<small>{note}</small>" if note else ""
        return (f'<li><a href="{k}"><span class="rt-t">{label}{n}</span><span class="rt-m">{fmt_min(minutes)}</span></a></li>')

    routes = [
        ("first", "Изучаю впервые", "От общей картины к деталям, затем практика.",
         [step("short.html", "Кратко: семь блоков", t_short),
          step("images.html", "Схемы с пояснениями", 10),
          step("full.html", "Полностью: по частям", t_full, "показания → методы → подготовка → интерпретация → ограничения → шаг"),
          step("test.html", "Тест в режиме обучения", 35, "ответ и разбор сразу"),
          step("cases.html", "Клинические задачи: поэтапные случаи", 40),
          step("card.html", "Шпаргалка", 10)],
         t_short + t_full, t_short + t_full + 10 + 35 + 40 + 10 + 30),
        ("repeat", "Повторяю", "Быстро вернуть главное и закрыть пробелы.",
         [step("card.html", "Шпаргалка", 10),
          step("short.html", "Кратко", t_short),
          step("test.html", "Тест: повтор ошибок", 15, "режим «Повтор ошибок»"),
          step("cases.html", "Одна поэтапная задача", 20)],
         10 + t_short, 10 + t_short + 15 + 20),
        ("check", "Проверяю себя", "Без подсказок, потом разбор.",
         [step("test.html", "Тест в режиме экзамена", 10, "20 случайных вопросов банка, таймер 10 минут"),
          step("test.html", "Разбор ошибок и повтор", 20),
          step("cases.html", "Поэтапные задачи без подглядывания", 40),
          step("card.html", "Шпаргалка: сверить пробелы", 10)],
         30, 30 + 20 + 40 + 10),
    ]
    rcards = []
    for rid, rt, rd, steps_, tread, tprep in routes:
        rcards.append(
            f'<section class="route route-{rid}"><header><h3>{rt}</h3><p>{rd}</p></header>'
            f'<ol class="rt-steps">{"".join(steps_)}</ol>'
            f'<dl class="rt-time"><div><dt>Чтение</dt><dd>≈ {fmt_min(tread)}</dd></div>'
            f'<div><dt>Полная подготовка</dt><dd>≈ {fmt_min(tprep)}</dd></div></dl></section>')
    tiles = []
    unit = {"card": "≈ 10 мин", "short": f"≈ {fmt_min(t_short)}", "full": f"≈ {fmt_min(t_full)}",
            "test": f"20 вопросов из банка в {len(questions)}", "cases": f"{len(case_pos)} задач", "images": f"{len(figs_full)} схем"}
    steps = {"short": "1", "full": "2", "card": "3", "test": "4", "cases": "5", "images": "+"}
    for k, lab, sub in PAGES:
        tiles.append(f'<a class="home-tile ht-{k}" href="{k}.html"><span class="ht-ico">{icon(k, 26)}</span>'
                     f'<span class="ht-step">{steps[k]}</span><b>{lab}</b><span class="ht-sub">{sub}</span>'
                     f'<span class="ht-meta">{unit[k]}</span></a>')

    # левое меню: под активным разделом раскрывается его собственная навигация
    SUBNAV.clear()
    SUBNAV["short"] = [(f'#{t["id"]}', t["title"]) for t in s_toc]
    SUBNAV["full"] = [(f'#{t["id"]}', t["title"]) for t in f_toc]
    SUBNAV["card"] = [(f'#{t["id"]}', t["title"]) for t in CARD_TOC]
    SUBNAV["images"] = [(f"#fig-{c}", t) for c, t, _ in sorted(figs_full)]
    SUBNAV["sources"] = [("#sources-list", "Источники"), ("#remarks", "Замечания проверки")]

    index_body = f"""
<div class="home-hero">
  {crumbs()}
  <div class="eyebrow">Тема {TOPIC_N} · всего тем: {len(TOPICS)}</div>
  <h1>{html.escape(topic_title)}</h1>
  <p class="lead-p">{card_sub}</p>
</div>
<h2 class="home-h">Выберите маршрут</h2>
<p class="home-hint">Время — оценка: чтение считается по 200 слов в минуту, подготовка включает практику и разбор ошибок.</p>
<div class="routes">{"".join(rcards)}</div>
<h2 class="home-h">Все материалы</h2>
<div class="home-grid">{''.join(tiles)}</div>
<div class="home-note"><b>Как читать цвета.</b>
 <span class="lg-inline"><i class="lg lg-red"></i><b>Красный</b> — срочность;</span>
 <span class="lg-inline"><i class="lg lg-warn"></i><b>жёлтый</b> — ограничение или ошибка;</span>
 <span class="lg-inline"><i class="lg lg-main"></i><b>сливовый</b> — главное правило.</span>
 <b>Жирным</b> выделен термин или правило, <mark class="num">подчёркнутые числа</mark> — пороги.
 Метка <a class="verify st-open" href="sources.html" data-note="Пример пометки: нажмите, чтобы увидеть разбор">проверить</a> ведёт к разбору источника на странице «<a href="sources.html">Источники</a>».</div>
"""
    index_body = re.sub(r'(<div class="home-note">.*?</div>)', lambda m: hl_numbers(m.group(1)), index_body, flags=re.S)
    (SITE / "index.html").write_text(page_shell("index", topic_title, index_body,
                                                desc=f"Тема {TOPIC_N}. {TOPIC_TITLE}", extra_body_class="home"), encoding="utf-8")

    # все темы

    # card
    body = (page_head("card", "Шпаргалка", "Компактные правила. У каждой строки — ссылка на пояснение, источник и ограничение.") +
            '<div class="card-actions"><button type="button" class="btn" id="print-btn">Распечатать / сохранить в PDF</button></div>' +
            card_body + pager("card"))
    (SITE / "card.html").write_text(page_shell("card", "Шпаргалка", body, desc=card_sub), encoding="utf-8")

    # short
    body = (page_head("short", "Кратко", "Семь практических блоков: от жалобы до ошибок. Подробности — в полной версии.", wc_short) +
            '<div class="doc-actions"><button type="button" class="btn btn-sm" data-fold="open">Развернуть всё</button><button type="button" class="btn btn-sm" data-fold="close">Свернуть всё</button></div>' +
            s_intro_final + s_secs_final + pager("short"))
    (SITE / "short.html").write_text(page_shell("short", "Кратко", body), encoding="utf-8")

    # full
    body = (page_head("full", "Полный материал", "Показания → подготовка → интерпретация → ограничения → следующий шаг: в таком порядке построен текст и каждый метод.", wc_full) +
            '<div class="doc-actions"><button type="button" class="btn btn-sm" data-fold="open">Развернуть всё</button><button type="button" class="btn btn-sm" data-fold="close">Свернуть всё</button></div>' +
            f_intro_final + f_secs_final + pager("full"))
    (SITE / "full.html").write_text(page_shell("full", "Полный материал", body), encoding="utf-8")

    # test: банк вопросов целиком уходит в страницу, в попытку берутся 20 случайных
    quiz_json = json.dumps({"topic": SLUG, "perSession": 20, "questions": questions}, ensure_ascii=False)
    body = (page_head("test", "Тест", "Тренировка с разбором или проверка знаний без подсказок.") +
            '<div class="qz-top"><div class="seg-toggle" id="qz-mode" role="group" aria-label="Режим теста"></div>'
            '<span class="qz-hint" id="qz-hint"></span>'
            '<label class="qz-shuf"><input type="checkbox" id="qz-shuf" checked> Перемешивать</label></div>'
            '<div class="qz-grid"><div class="qz-main"><div id="qz-result" hidden></div><article class="qz-card" id="qz-card" aria-live="polite"></article></div>'
            '<aside class="qz-side"><div class="qz-navcard"><h2>Навигация по тесту</h2><div class="qz-timer" id="qz-timer" hidden></div><div class="qz-nums" id="qz-nums"></div>'
            '<p class="qz-saved" id="qz-saved"></p><div class="qz-links"><button type="button" class="link-btn danger" id="qz-finish">Завершить попытку</button>'
            '<button type="button" class="link-btn" id="qz-new">Новая попытка</button></div></div>'
            '<p class="qz-note" id="qz-note"></p></aside></div>'
            '<section class="quiz-hist" id="quiz-hist"></section>' + pager("test"))
    shell = page_shell("test", "Тест", body, script_extra=f'<script type="application/json" id="quiz-data">{quiz_json.replace("</", "<\\/")}</script>'
                       f'<script src="../../assets/quiz.js?v={BUILD}" defer></script>')
    (SITE / "test.html").write_text(shell, encoding="utf-8")

    # cases
    body = (page_head("cases", "Клинические задачи", "От клинической ситуации — к обоснованному решению.") + cases_body + pager("cases"))
    (SITE / "cases.html").write_text(page_shell("cases", "Клинические задачи", body), encoding="utf-8")

    # images
    gal = "".join(figure_html(c, t, d, True) for c, t, d in sorted(figs_full))
    body = (page_head("images", "Схемы", "Название схемы вынесено в подпись, под рисунком — что нужно понять. Нажмите на схему: её можно увеличить и перемещать.") +
            f'<div class="gallery">{gal}</div>' + pager("images"))
    (SITE / "images.html").write_text(page_shell("images", "Схемы", body), encoding="utf-8")

    # sources
    (SITE / "sources.html").write_text(page_shell("sources", "Источники", src_body, desc="Источники темы и разбор пометок «проверить»",
                                                  extra_body_class="page-sources"), encoding="utf-8")

    (SITE / "assets" / "search.js").write_text("window.SEARCH_INDEX=" + json.dumps(search, ensure_ascii=False) + ";", encoding="utf-8")
    print("OK: слов (полная/краткая):", wc_full, wc_short, "| индекс поиска:", len(search),
          "| вопросов в банке:", len(questions), "| задач:", len(case_pos),
          "| пометки:", len(VERIFY["items"]), "| блоков полной:", len(f_toc))


def all_items():
    for part in STRUCT["parts"]:
        yield from part.get("items", [])
        for g in part.get("groups", []):
            yield from g["items"]


# ---------------------------------------------------- переносимая сборка
IMAGE_EXTENSIONS = (".webp", ".svg", ".png", ".jpg", ".jpeg")
SOURCE_PAGES = {"full": "1_full.md", "short": "2_short.md", "card": "3_card.md",
                "test": "4_tests.md", "cases": "5_cases.md", "images": "6_images.md"}


def rewrite_source_links(rendered):
    """Retain relative cross-topic routes while translating source filenames to HTML."""
    pages = {filename: f"{kind}.html" for kind, filename in SOURCE_PAGES.items()}
    pages["5_cases_staged.md"] = "cases.html"

    def replace(match):
        url = urlsplit(html.unescape(match[1]))
        if url.scheme or url.netloc:
            return match[0]
        prefix, _, filename = url.path.rpartition("/")
        if filename not in pages:
            return match[0]
        path = (prefix + "/" if prefix else "") + pages[filename]
        return f'href="{esc(urlunsplit(("", "", path, url.query, url.fragment)))}"'

    return re.sub(r'href="([^"]+)"', replace, rendered)


def discover_topics():
    """meta.json is the only registry; folders without it are not published."""
    topics, numbers = [], set()
    for folder in sorted((ROOT / "topics").iterdir()):
        if not folder.is_dir() or folder.name.startswith((".", "_")):
            continue
        meta_path = folder / "meta.json"
        if not meta_path.is_file():
            continue
        if not re.fullmatch(r"\d{2,}_[a-z0-9_]+", folder.name):
            raise ValueError(f"Invalid topic folder: {folder.name}")
        meta = json.loads(meta_path.read_text(encoding="utf-8-sig"))
        number = meta.get("number")
        if type(number) is not int or number < 1 or number != int(folder.name.split("_")[0]):
            raise ValueError(f"{meta_path.relative_to(ROOT)}: number must match the folder number")
        for key in ("title", "discipline"):
            if not isinstance(meta.get(key), str) or not meta[key].strip():
                raise ValueError(f"{meta_path.relative_to(ROOT)}: missing {key}")
            meta[key] = meta[key].strip()
        identity = (meta["discipline"], number)
        if identity in numbers:
            raise ValueError(f"Duplicate topic number: {identity}")
        numbers.add(identity)
        for filename in SOURCE_PAGES.values():
            if not (folder / filename).is_file():
                raise ValueError(f"{folder.name}: missing {filename}")
        topics.append({**meta, "slug": folder.name})
    if not topics:
        raise ValueError("No topics/<NN_slug>/meta.json found")
    return sorted(topics, key=lambda t: (t["discipline"], t["number"], t["slug"]))


def configure_topic(topic):
    global SLUG, TOPIC_DIR, IMG_SRC, SITE, TOPIC_NO, TOPIC_N, TOPIC_TITLE, DISCIPLINE
    global SRC_DATA, SOURCES, VERIFY, STRUCT, FIGMETA, CHECKED, CASES_CFG
    SLUG = topic["slug"]
    TOPIC_DIR = ROOT / "topics" / SLUG
    IMG_SRC = TOPIC_DIR / "images"
    SITE = OUTPUT / "topics" / SLUG
    TOPIC_N, TOPIC_NO = topic["number"], str(topic["number"]).zfill(2)
    TOPIC_TITLE, DISCIPLINE = topic["title"], topic["discipline"]
    SRC_DATA = jload("sources.json", {"sources": []})
    SOURCES = {s["id"]: s for s in SRC_DATA["sources"]}
    VERIFY = jload("verify.json", {"items": {}, "findings": []})
    STRUCT, FIGMETA, CASES_CFG = jload("structure.json", {"parts": []}), jload("figures.json", {}), jload("cases.json", {})
    CHECKED = ".".join(reversed(SRC_DATA.get("checked", "").split("-")))
    for obj in (REF_MAP, FULL_IDS, FIGS, SUBNAV, CARD_TOC):
        obj.clear()


def image_file(code, theme):
    return next((f"{code}-{theme}{ext}" for ext in IMAGE_EXTENSIONS
                 if (IMG_SRC / f"{code}-{theme}{ext}").is_file()), None)


def copy_images():
    (SITE / "img").mkdir(parents=True, exist_ok=True)
    if IMG_SRC.is_dir():
        for path in sorted(IMG_SRC.iterdir()):
            if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS:
                shutil.copyfile(path, SITE / "img" / path.name)


def generic_document(text, kind):
    """Preserve source order and all clinical wording, without topic-1 section assumptions."""
    if kind == "test":
        text = re.sub(r"(?m)^([АБВГ]\)[^\n]*)$", r"\1  ", text)
    rendered = md_html(text)
    # Register source heading anchors before rewriting cross-references.
    if kind == "full":
        for index, heading in enumerate(re.findall(r"<h[23][^>]*>(.*?)</h[23]>", rendered, re.S), 1):
            number = number_of(strip_tags(heading))
            if number:
                REF_MAP[number] = (f"section-{index}", strip_tags(heading))
    counter = 0

    def anchor(match):
        nonlocal counter
        counter += 1
        return f'<h{match[1]} id="section-{counter}">{match[2]}</h{match[1]}>'

    rendered = re.sub(r"<h([23])[^>]*>(.*?)</h\1>", anchor, rendered, flags=re.S)
    rendered = replace_figures(rendered)
    rendered = link_refs(verify_chips(rendered), "full.html")
    rendered = re.sub(r"<table>", '<div class="tbl"><table>', rendered).replace("</table>", "</table></div>")
    rendered = re.sub(r"^<h1>.*?</h1>\s*", "", rendered, count=1, flags=re.S)
    return rendered


def build_generic_topic():
    (SITE / "assets").mkdir(parents=True, exist_ok=True)
    copy_images()
    rendered, search = {}, []
    # Full first: other pages can refer to its original section numbers.
    for kind, filename in SOURCE_PAGES.items():
        text = read(filename)
        if kind == "images":
            continue
        if kind == "cases" and (TOPIC_DIR / "5_cases_staged.md").is_file():
            text += "\n\n" + read("5_cases_staged.md")
        rendered[kind] = generic_document(text, kind)
    figures = list(FIGS)
    # 6_images.md contains generation prompts. Publish actual diagrams and their source captions.
    rendered["images"] = ('<div class="gallery">' + "".join(figure_html(*fig, standalone=True) for fig in figures) + '</div>'
                          if figures else '<p>Схемы пока не добавлены.</p>')
    for kind, label, sub in PAGES:
        document = rendered[kind]
        SUBNAV[kind] = [("#" + anchor, strip_tags(title)) for anchor, title in
                        re.findall(r'<h2 id="([^"]+)">(.*?)</h2>', document, re.S)]
        if kind != "test":
            search.append({"p": f"{kind}.html", "l": label, "a": "", "t": label,
                           "x": re.sub(r"\s+", " ", strip_tags(document))})
    for kind, label, sub in PAGES:
        body = page_head(kind, label, html.escape(TOPIC_TITLE)) + rendered[kind] + pager(kind)
        (SITE / f"{kind}.html").write_text(page_shell(kind, label, body), encoding="utf-8")
    # No inferred source registry or verification status. Retain original source sections in full.html.
    source_links = [(anchor, title) for anchor, title in SUBNAV.get("full", [])
                    if re.search(r"источник|литератур|документ|рекомендац|исследован", title, re.I)]
    links = "".join(f'<li><a href="full.html{anchor}">{html.escape(title)}</a></li>' for anchor, title in source_links)
    body = page_head("sources", "Источники", "Источники и пометки сохранены в исходном материале темы.")
    body += f'<ul>{links}</ul>' if links else '<p><a href="full.html">Открыть полный материал темы</a></p>'
    (SITE / "sources.html").write_text(page_shell("sources", "Источники", body), encoding="utf-8")
    tiles = "".join(f'<a class="home-tile ht-{kind}" href="{kind}.html"><span class="ht-ico">{icon(kind, 26)}</span>'
                    f'<b>{label}</b></a>' for kind, label, _ in PAGES)
    body = f'<div class="home-hero">{crumbs()}<div class="eyebrow">Тема {TOPIC_N}</div><h1>{html.escape(TOPIC_TITLE)}</h1></div>'
    body += f'<h2 class="home-h">Все материалы</h2><div class="home-grid">{tiles}</div>'
    (SITE / "index.html").write_text(page_shell("index", TOPIC_TITLE, body, extra_body_class="home"), encoding="utf-8")
    (SITE / "assets" / "search.js").write_text("window.SEARCH_INDEX=" + json.dumps(search, ensure_ascii=False).replace("</", "<\\/") + ";", encoding="utf-8")
    print(f"OK: {SLUG}: Markdown, {len(figures)} схем")


def build_catalog():
    global CATALOG, DISCIPLINE, SITE
    CATALOG, SITE = True, OUTPUT
    disciplines = sorted({topic["discipline"] for topic in TOPICS})
    DISCIPLINE = disciplines[0] if len(disciplines) == 1 else "Учебные материалы"
    cards, search = [], []
    for discipline in disciplines:
        cards.append(f'<h2 class="home-h">{html.escape(discipline)}</h2>')
        for topic in TOPICS:
            if topic["discipline"] != discipline:
                continue
            url = f'topics/{quote(topic["slug"])}/index.html'
            cards.append(f'<a class="topic-card" href="{url}"><span class="tc-n">Тема {topic["number"]}</span>'
                         f'<b>{html.escape(topic["title"])}</b><span class="tc-sub">Материалы темы →</span></a>')
            search.append({"p": url, "l": discipline, "a": "", "t": topic["title"], "x": f'Тема {topic["number"]} {discipline}'})
    listing = "".join(cards)
    for fname, title in (("index", DISCIPLINE), ("topics", "Все темы")):
        body = f'<div class="home-hero"><h1>{html.escape(title)}</h1><p class="lead-p">Тем: {len(TOPICS)}. Выберите материал для изучения.</p></div>' + listing
        (OUTPUT / f"{fname}.html").write_text(page_shell(fname, title, body, extra_body_class="home"), encoding="utf-8")
    (OUTPUT / "assets" / "search.js").write_text("window.SEARCH_INDEX=" + json.dumps(search, ensure_ascii=False) + ";", encoding="utf-8")
    CATALOG = False


def main():
    global TOPICS
    parser = argparse.ArgumentParser(description="Build all topics into site/ for GitHub Pages")
    parser.parse_args()
    TOPICS = discover_topics()  # Validate before replacing existing build.
    # Only this fixed generated directory is removed, independent of the working directory.
    if OUTPUT.is_symlink():
        raise ValueError("site/ must not be a symlink")
    OUTPUT.mkdir(exist_ok=True)
    for child in OUTPUT.iterdir():
        if child.is_symlink() or child.is_file():
            child.unlink()
        else:
            shutil.rmtree(child)
    shutil.copytree(SRC_ASSETS, OUTPUT / "assets")
    for topic in TOPICS:
        configure_topic(topic)
        if STRUCT.get("parts") and (TOPIC_DIR / "5_cases_staged.md").is_file():
            build_detailed_topic()
        elif jload("layout.json").get("reference"):
            from reference_topic import build_reference_topic
            import sys
            build_reference_topic(sys.modules[__name__])
        else:
            build_generic_topic()
    build_catalog()
    (OUTPUT / ".nojekyll").touch()
    print(f"Built {len(TOPICS)} topics into site/")


if __name__ == "__main__":
    main()


