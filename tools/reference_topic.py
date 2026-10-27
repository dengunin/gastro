"""Reference components for topics with layout.json; medical Markdown stays unchanged."""
import html
import json
import re


def normalize_card(text):
    """Accept Markdown headings as well as the reference's bold block labels."""
    text = re.sub(r"(?m)^\*\*Одной строкой[.:]?\*\*[:.]?\s*", "**Одной строкой:** ", text)
    text = re.sub(r"(?m)^(\*\*[^*\n]+\*\*(?:\s*\([^\n]*\))?):\s*$", r"\1", text)
    if not re.search(r"(?m)^## ", text):
        return text
    lines, hero, body = [], False, []
    for line in text.splitlines():
        if line.startswith("## "):
            if hero:
                lines.append("**Одной строкой:** " + " ".join(body).strip())
                body, hero = [], False
            title = line[3:].strip()
            if title.casefold().rstrip(":") == "одной строкой":
                hero = True
            else:
                lines.append(f"**{title}**")
        elif hero:
            if line.strip():
                body.append(line.strip())
        else:
            lines.append(line)
    if hero:
        lines.append("**Одной строкой:** " + " ".join(body).strip())
    return "\n".join(lines)


def reference_questions(b, text, allow_unkeyed=False):
    """Normalize syntax only; missing answer keys are never inferred."""
    body, answers = text.split("## Ответы")
    body = re.sub(r"(?m)^[ \t]*(?:[-*][ \t]+)?([АБВГ]\))", r"\1", body)
    body = re.sub(r"(?m)^## (?!Вопросы\s*$)(.+)$", r"### \1", body)
    answers = answers.replace("**", "")
    answers = re.sub(r"(?m)^(\d+)\.\s*([АБВГ])(?:\.|\s*[—–-])\s*", r"\1. **\2.** ", answers)
    numbers = {int(n) for n in re.findall(r"(?m)^(?:\*\*)?(\d+)\.(?:\*\*)?\s", body)}
    keys = {int(n) for n in re.findall(r"(?m)^(\d+)\.\s+\*\*[АБВГ]\.\*\*", answers)}
    if keys - numbers:
        raise ValueError(f"Answer keys without questions: {sorted(keys - numbers)}")
    missing, unkeyed = numbers - keys, []
    if missing:
        if not allow_unkeyed:
            raise ValueError(f"Missing answer keys: {sorted(missing)}; set quiz_unkeyed_policy=preserve to retain them separately")
        chunks = re.split(r"(?m)(?=^(?:\*\*)?\d+\.(?:\*\*)?\s)", body)
        kept = []
        for chunk in chunks:
            match = re.match(r"^(?:\*\*)?(\d+)\.", chunk)
            if match and int(match[1]) in missing:
                unkeyed.append(chunk)
            else:
                kept.append(chunk)
        body = "\n".join(kept)
    return b.parse_tests(body + "\n## Ответы\n" + answers), "\n".join(unkeyed)


def normalize_cases(text):
    text = re.sub(r"(?m)^\*\*Источник:\*\*", "**Источник случая.**", text)
    text = re.sub(r"(?m)^\*\*Подвох задачи:\*\*", "**Подвох.**", text)
    labels = r"Условие|Вопросы|Эталонные ответы|Подвох|Источник случая"
    text = re.sub(r"(?m)^### (" + labels + r")[.:]?\s*$", r"**\1.**", text)
    return re.sub(r"(?m)^\*\*(" + labels + r")\*\*", r"**\1.**", text)


def build_reference_topic(b):
    (b.SITE / "assets").mkdir(parents=True, exist_ok=True)
    b.copy_images()
    layout = b.jload("layout.json")
    documents, search = {}, []
    for kind in ("full", "short"):
        raw = b.generic_document(b.read(b.SOURCE_PAGES[kind]), kind)
        chunks = re.split(r'(?=<h2 id=")', raw)
        intro, sections = b.decorate_blocks(chunks[0]), chunks[1:]
        grouped, assigned = [], set()
        for part in layout["parts"]:
            contents = []
            for i, section in enumerate(sections):
                heading = re.search(r'<h2 id="([^"]+)">(.*?)</h2>', section, re.S)
                number = re.match(r"(\d+)", b.strip_tags(heading[2]))
                if not ((number and int(number[1]) in part["sections"]) or
                        (not number and part.get("include_unnumbered"))):
                    continue
                if i in assigned:
                    raise ValueError(f"{b.SLUG}/{kind}: duplicate source section in layout")
                assigned.add(i)
                section = re.sub(r'<(/?)h3\b', r'<\1h4', section)
                section = re.sub(r'<(/?)h2\b', r'<\1h3', section)
                source_number = int(number[1]) if number else 0
                cls = " urgent" if source_number == 7 else " limit" if source_number in (14, 21) else ""
                contents.append(f'<div class="item{cls}">{b.decorate_blocks(section)}</div>')
            if contents:
                title = f'{len(grouped) + 1}. {part["title"]}' if kind == "short" else part["title"]
                grouped.append(f'<h2 id="{part["id"]}">{html.escape(title)}</h2>' + "".join(contents))
        if len(assigned) != len(sections):
            raise ValueError(f"{b.SLUG}/{kind}: layout must include every source section")
        steps = ["Основа", "Безопасность", "Контроль", "Лечение", "Особые группы", "Наблюдение", "Практика"]
        parts_meta = {part["id"]: part.get("step", step) for part, step in zip(layout["parts"], steps)} if kind == "full" else None
        _, body, toc = b.build_doc("".join(grouped), kind, parts_meta)
        documents[kind] = b.hl_numbers(intro + body)
        b.SUBNAV[kind] = [("#" + t["id"], t["title"]) for t in toc]
        for section in sections:
            h = re.search(r'<h2 id="([^"]+)">(.*?)</h2>', section, re.S)
            search.append({"p": f"{kind}.html", "l": b.NAV_LABEL[kind], "a": h[1],
                           "t": b.strip_tags(h[2]), "x": re.sub(r"\s+", " ", b.strip_tags(section))})

    figures = list(b.FIGS)
    card_lines, block = [], 0
    targets = layout.get("card_refs", ["8", "7", "9", "12", "15", "21"])
    for line in normalize_card(b.read("3_card.md")).splitlines():
        if re.fullmatch(r"\*\*[^*]+\*\*(?:\s*\(.*\))?", line) and not line.startswith("**Одной строкой:"):
            block += 1
        if re.match(r"^(?:[-*]|\d+\.)\s", line) and 0 < block <= len(targets):
            line += " {ref=" + str(targets[block - 1]) + "}"
        card_lines.append(line)
    documents["card"] = b.build_card("\n".join(card_lines))
    b.SUBNAV["card"] = [("#" + t["id"], t["title"]) for t in b.CARD_TOC]
    for tile in b.CARD_TOC:
        content = re.search(r'<section[^>]*id="' + re.escape(tile["id"]) + r'"[^>]*>(.*?)</section>', documents["card"], re.S)
        search.append({"p": "card.html", "l": "Шпаргалка", "a": tile["id"], "t": tile["title"],
                       "x": b.strip_tags(content[1]) if content else ""})

    # Only typography is normalized for the parser: original questions, distractors and keys remain intact.
    tests = b.read("4_tests.md")
    questions, unkeyed = reference_questions(b, tests, layout.get("quiz_unkeyed_policy") == "preserve")
    case_md = b.read("5_cases.md")
    documents["cases"], case_positions = b.build_cases_page("", normalize_cases(case_md))
    case_intro = re.split(r"(?m)^## ", case_md)[0]
    case_intro = re.sub(r"(?m)^# .*\n|^Сокращения:.*\n?", "", case_intro).strip()
    documents["cases"] = b.md_html(case_intro) + documents["cases"]
    documents["cases"] = b.hl_numbers(b.link_refs(b.verify_chips(documents["cases"]), "full.html"))
    b.SUBNAV["cases"] = [(f"#case-{pos}", f"Случай {pos}") for pos in case_positions.values()]
    search.append({"p": "cases.html", "l": "Клинические задачи", "a": "", "t": "Клинические задачи",
                   "x": b.strip_tags(documents["cases"])})
    documents["images"] = '<div class="gallery">' + "".join(b.figure_html(*f, standalone=True) for f in figures) + '</div>'
    b.SUBNAV["images"] = [(f"#fig-{code}", title) for code, title, _ in figures]
    for code, title, desc in figures:
        search.append({"p": "images.html", "l": "Схемы", "a": f"fig-{code}", "t": title, "x": desc})

    # Bibliography is displayed as supplied, without inventing evidence or claiming verification.
    full_source = b.read("1_full.md")
    bibliography_match = re.search(r"(?ms)^## \d+\.\s*Источники[^\n]*\n(.*)", full_source)
    if not bibliography_match:
        raise ValueError(f"{b.SLUG}: missing source bibliography section")
    bibliography = bibliography_match[1]
    citations = re.split(r"(?m)^(?=\d+\.\s)", bibliography)
    cards = []
    for citation in citations:
        citation = citation.strip()
        if not citation:
            continue
        number = re.match(r"(\d+)\.\s*", citation)
        cid = number[1] if number else str(len(cards) + 1)
        cards.append(f'<article class="src-card" id="src-{cid}"><div>{b.verify_chips(b.md_html(citation))}</div></article>')
        search.append({"p": "sources.html", "l": "Источники", "a": f"src-{cid}", "t": f"Источник {cid}", "x": citation})
    remarks = []
    for kind, filename in b.SOURCE_PAGES.items():
        if kind == "images":
            continue
        for line in b.read(filename).splitlines():
            if "[ПРОВЕРИТЬ" in line:
                remarks.append(f'<article class="src-card"><div><b>{b.NAV_LABEL[kind]}</b>'
                               f'{b.md_html(line)}<a href="{kind}.html">К материалу →</a></div></article>')
    b.SUBNAV["sources"] = [("#sources-list", "Источники"), ("#remarks", "Замечания проверки")]
    documents["sources"] = (b.page_head("sources", "Источники", "Библиография темы и сохранённые пометки к материалу.") +
        f'<div class="stat-row"><div><b>{len(cards)}</b><span>источников в материале</span></div>'
        f'<div><b>{len(remarks)}</b><span>фрагментов с пометками</span></div></div>'
        '<div class="note-box"><h3>Статус источников</h3><p>Библиография перенесена из материала темы. '
        'Пометки «проверить» сохранены и требуют сверки по первоисточникам.</p></div>'
        '<section id="sources-list"><h2>Источники</h2><div class="src-list">' + "".join(cards) + '</div></section>'
        '<section id="remarks"><h2>Замечания проверки</h2><div class="src-list">' + "".join(remarks) + '</div></section>')

    short_time = b.word_count(documents["short"]) / 200
    full_time = b.word_count(documents["full"]) / 200
    hero = b.strip_tags(re.search(r'<div class="hero-line">.*?<p>(.*?)</p>', documents["card"], re.S)[1])
    overview = overview_html(b, hero, short_time, full_time, len(questions), len(case_positions), len(figures))
    (b.SITE / "index.html").write_text(b.page_shell("index", b.TOPIC_TITLE, overview, extra_body_class="home"), encoding="utf-8")
    descriptions = {
        "short": "Семь практических блоков: механизмы, безопасность, дозы и контроль.",
        "full": "Основы → безопасность → диагностика → лечение → особые группы → наблюдение → практика.",
        "card": "Компактные правила, дозы, красные флаги и ловушки.",
        "cases": "От клинической ситуации — к обоснованному решению.",
        "images": "Схемы с пояснениями. Нажмите на схему, чтобы увеличить и перемещать её.",
    }
    if b.TOPIC_N != 2:
        descriptions["card"] = "Компактные правила, красные флаги и ограничения."
    descriptions.update(layout.get("descriptions", {}))
    for kind in ("short", "full", "card", "cases", "images"):
        words = b.word_count(documents[kind]) if kind in ("short", "full") else None
        controls = ('<div class="doc-actions"><button type="button" class="btn btn-sm" data-fold="open">Развернуть всё</button>'
                    '<button type="button" class="btn btn-sm" data-fold="close">Свернуть всё</button></div>') if words else ""
        if kind == "card":
            controls = '<div class="card-actions"><button type="button" class="btn" id="print-btn">Распечатать / сохранить в PDF</button></div>'
        body = b.page_head(kind, b.NAV_LABEL[kind], descriptions[kind], words) + controls + documents[kind] + b.pager(kind)
        (b.SITE / f"{kind}.html").write_text(b.page_shell(kind, b.NAV_LABEL[kind], body), encoding="utf-8")
    (b.SITE / "sources.html").write_text(b.page_shell("sources", "Источники", documents["sources"]), encoding="utf-8")
    # Use the exact reference quiz component; only the serialized question bank differs.
    quiz_page(b, questions, unkeyed)
    (b.SITE / "assets" / "search.js").write_text("window.SEARCH_INDEX=" + json.dumps(search, ensure_ascii=False).replace("</", "<\\/") + ";", encoding="utf-8")
    print(f"OK: {b.SLUG}: reference layout, {len(questions)} questions, {len(case_positions)} cases, {len(figures)} diagrams")


def overview_html(b, hero, short_time, full_time, questions, cases, figures):
    routes = [
        ("first", "Изучаю впервые", "От общей картины к деталям, затем практика.",
         [("short.html", "Кратко: семь блоков", short_time), ("images.html", "Схемы с пояснениями", 10),
          ("full.html", "Полностью: по частям", full_time), ("test.html?mode=learn", "Тест в режиме обучения", 35),
          ("cases.html", "Клинические задачи", 40), ("card.html", "Шпаргалка", 10)], short_time + full_time, short_time + full_time + 95),
        ("repeat", "Повторяю", "Быстро вернуть главное и закрыть пробелы.",
         [("card.html", "Шпаргалка", 10), ("short.html", "Кратко", short_time),
          ("test.html?mode=errors", "Тест: повтор ошибок", 15), ("cases.html", "Одна клиническая задача", 20)], short_time + 10, short_time + 45),
        ("check", "Проверяю себя", "Без подсказок, потом разбор.",
         [("test.html?mode=exam", "Тест в режиме экзамена", 10), ("test.html", "Разбор ошибок и повтор", 20),
          ("cases.html", "Задачи без подглядывания", 40), ("card.html", "Шпаргалка: сверить пробелы", 10)], 30, 80),
    ]
    cards = []
    for rid, title, desc, steps, reading, total in routes:
        items = "".join(f'<li><a href="{url}"><span class="rt-t">{label}</span><span class="rt-m">{b.fmt_min(minutes)}</span></a></li>' for url, label, minutes in steps)
        cards.append(f'<section class="route route-{rid}"><header><h3>{title}</h3><p>{desc}</p></header>'
                     f'<ol class="rt-steps">{items}</ol><dl class="rt-time"><div><dt>Чтение</dt><dd>≈ {b.fmt_min(reading)}</dd></div>'
                     f'<div><dt>Полная подготовка</dt><dd>≈ {b.fmt_min(total)}</dd></div></dl></section>')
    units = {"short": f"≈ {b.fmt_min(short_time)}", "full": f"≈ {b.fmt_min(full_time)}", "card": "≈ 10 мин",
             "test": f"20 вопросов из банка в {questions}", "cases": f"Задач: {cases}", "images": f"Схем: {figures}"}
    notes = {"short": "Семь практических блоков для приёма", "full": "Механизмы, дозы, безопасность, контроль и следующий шаг",
             "card": "Компактные правила, дозы и ограничения", "test": "Режимы обучения и экзамена, повтор ошибок, история",
             "cases": "Случаи с отдельными этапами решения и разбора", "images": "Иллюстрации с пояснением и увеличением"}
    if b.TOPIC_N != 2:
        notes["full"] = "Основные сведения, практические решения и наблюдение"
        notes["card"] = "Компактные правила и ограничения"
    notes.update({key: value for key, value in b.jload("layout.json").get("material_notes", {}).items() if key in notes})
    tiles = "".join(f'<a class="home-tile ht-{kind}" href="{kind}.html"><span class="ht-ico">{b.icon(kind, 26)}</span>'
                    f'<span class="ht-step">{i if kind != "images" else "+"}</span><b>{label}</b>'
                    f'<span class="ht-sub">{notes[kind]}</span><span class="ht-meta">{units[kind]}</span></a>'
                    for i, (kind, label, _) in enumerate(b.PAGES, 1))
    return (f'<div class="home-hero">{b.crumbs()}<div class="eyebrow">Тема {b.TOPIC_N} · всего тем: {len(b.TOPICS)}</div>'
            f'<h1>{html.escape(b.TOPIC_TITLE)}</h1><p class="lead-p">{html.escape(hero)}</p></div>'
            '<h2 class="home-h">Выберите маршрут</h2><p class="home-hint">Время — оценка: чтение считается по 200 слов в минуту, '
            'подготовка включает практику и разбор ошибок.</p><div class="routes">' + "".join(cards) + '</div>'
            '<h2 class="home-h">Все материалы</h2><div class="home-grid">' + tiles + '</div>'
            '<div class="home-note"><b>Как читать цвета.</b> <span class="lg-inline"><i class="lg lg-red"></i><b>Красный</b> — срочность;</span> '
            '<span class="lg-inline"><i class="lg lg-warn"></i><b>жёлтый</b> — ограничение или ошибка;</span> '
            '<span class="lg-inline"><i class="lg lg-main"></i><b>сливовый</b> — главное правило.</span> '
            '<b>Жирным</b> выделен термин или правило, <mark class="num">подчёркнутые числа</mark> — пороги. '
            'Метка <a class="verify st-open" href="sources.html#remarks">проверить</a> ведёт к замечаниям в источниках.</div>')


def quiz_page(b, questions, unkeyed=""):
    body = (b.page_head("test", "Тест", "Тренировка с разбором или проверка знаний без подсказок.") +
        '<div class="qz-top"><div class="seg-toggle" id="qz-mode" role="group" aria-label="Режим теста"></div>'
        '<span class="qz-hint" id="qz-hint"></span><label class="qz-shuf"><input type="checkbox" id="qz-shuf" checked> Перемешивать</label></div>'
        '<div class="qz-grid"><div class="qz-main"><div id="qz-result" hidden></div><article class="qz-card" id="qz-card" aria-live="polite"></article></div>'
        '<aside class="qz-side"><div class="qz-navcard"><h2>Навигация по тесту</h2><div class="qz-timer" id="qz-timer" hidden></div><div class="qz-nums" id="qz-nums"></div>'
        '<p class="qz-saved" id="qz-saved"></p><div class="qz-links"><button type="button" class="link-btn danger" id="qz-finish">Завершить попытку</button>'
        '<button type="button" class="link-btn" id="qz-new">Новая попытка</button></div></div><p class="qz-note" id="qz-note"></p></aside></div>'
        '<section class="quiz-hist" id="quiz-hist"></section>' + b.pager("test"))
    if unkeyed:
        unkeyed = re.sub(r"(?m)^([АБВГ]\)[^\n]*)$", r"\1  ", unkeyed)
        body += ('<section class="sec" id="quiz-unkeyed"><details><summary><span class="sec-ttl"><h2>Вопросы без ключа ответа в исходнике</h2></span></summary>'
                 '<div class="sec-body"><p class="callout warn">Эти вопросы сохранены для самостоятельного разбора. '
                 'В исходнике нет ключей ответа; они не участвуют в автоматической оценке.</p>' + b.md_html(unkeyed) + '</div></details></section>')
    data = json.dumps({"topic": b.SLUG, "perSession": 20, "questions": questions}, ensure_ascii=False).replace("</", "<\\/")
    extra = f'<script type="application/json" id="quiz-data">{data}</script><script src="../../assets/quiz.js?v={b.BUILD}" defer></script>'
    (b.SITE / "test.html").write_text(b.page_shell("test", "Тест", body, script_extra=extra), encoding="utf-8")
