"""Small per-topic migration inspection and verification; never rebuilds the full site."""
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

import build_site as b
from reference_topic import build_reference_topic, normalize_card, reference_questions

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / 'reports' / 'reference-migration'
WORK = ROOT / '.work' / 'reference-migration'


def topic_by_number(number):
    b.TOPICS = b.discover_topics()
    return next(t for t in b.TOPICS if t['number'] == number)


def normalize(text):
    return re.sub(r'\s+', '', text).casefold().replace('сокращениясокращения:', 'сокращения:')


def update_status():
    rows = []
    for topic in b.discover_topics():
        if topic['number'] < 3:
            continue
        path = REPORTS / f'{topic["slug"]}.json'
        report = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
        rows.append({'number': topic['number'], 'slug': topic['slug'],
                     'agent': f'topic_{topic["number"]:02}',
                     'status': 'passed' if report.get('passed') else 'needs_fix' if report else 'pending'})
    count = sum(r['status'] == 'passed' for r in rows)
    payload = {'mode': 'one_separate_agent_per_topic_sequential', 'total': 41, 'passed': count, 'topics': rows}
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / 'state.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    status = ['# Перенос тем 3–43', '', f'Проверено: {count}/41. Отдельные агенты запускаются последовательно.', '',
              '| Тема | Агент | Проверка |', '|---|---|---|']
    status.extend(f'| {r["slug"]} | {r["agent"]} | {r["status"]} |' for r in rows)
    (REPORTS / 'STATUS.md').write_text('\n'.join(status) + '\n', encoding='utf-8')


def capture():
    REPORTS.mkdir(parents=True, exist_ok=True)
    WORK.mkdir(parents=True, exist_ok=True)
    baseline = WORK / 'baseline.json'
    if baseline.exists():
        print('Baseline already exists; preserved.')
        return
    hashes, pages = {}, {}
    for topic in b.discover_topics():
        folder = ROOT / 'topics' / topic['slug']
        for path in folder.glob('*.md'):
            hashes[path.relative_to(ROOT).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
        if topic['number'] < 3:
            continue
        for kind in ('full', 'short', 'card', 'cases'):
            path = ROOT / 'site' / 'topics' / topic['slug'] / f'{kind}.html'
            pages[f'{topic["slug"]}/{kind}'] = path.read_text(encoding='utf-8')
    baseline.write_text(json.dumps({'hashes': hashes, 'pages': pages}, ensure_ascii=False), encoding='utf-8')
    print(f'Captured {len(hashes)} Markdown hashes, {len(pages)} source pages.')


def inspect(number):
    topic = topic_by_number(number)
    b.configure_topic(topic)
    card = normalize_card(b.read('3_card.md'))
    payload = {'slug': b.SLUG, 'title': b.TOPIC_TITLE,
               'full': re.findall(r'(?m)^## (.+)', b.read('1_full.md')),
               'short': re.findall(r'(?m)^## (.+)', b.read('2_short.md')),
               'card': [h for h in re.findall(r'(?m)^\*\*([^*]+)\*\*(?:\s*\([^\n]*\))?\s*$', card) if h != 'Одной строкой:']}
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def fidelity(slug, output):
    from bs4 import BeautifulSoup
    baseline = json.loads((WORK / 'baseline.json').read_text(encoding='utf-8'))
    errors = []
    for relative, digest in baseline['hashes'].items():
        if f'/{slug}/' in relative and hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() != digest:
            errors.append(f'Markdown changed: {relative}')
    for kind in ('full', 'short', 'card', 'cases'):
        old = BeautifulSoup(baseline['pages'][f'{slug}/{kind}'], 'html.parser').select_one('main')
        new = BeautifulSoup((output / f'{kind}.html').read_text(encoding='utf-8'), 'html.parser').select_one('main')
        for node in old.select('.page-head, .pager'):
            node.decompose()
        if kind in ('full', 'short'):
            for node in new.select('.page-head, .doc-actions, .pager, .sec > details > summary'):
                node.decompose()
            if normalize(old.get_text()) != normalize(new.get_text()):
                errors.append(f'{kind}: source text sequence changed')
        else:
            for node in new.select('a.rule-ref'):
                node.decompose()
            if kind == 'cases':
                # Questions are retained in the condition pane; answer panes repeat them for context.
                for node in new.select('.q-text'):
                    node.decompose()
                for node in new.select('.case-src > strong, .callout > strong'):
                    if normalize(node.get_text()).rstrip('.:') in ('источникслучая', 'подвох'):
                        node.decompose()
            corpus = normalize(new.get_text()).replace(':', '')
            for fragment in old.select('p, li, td, th'):
                original = fragment.get_text()
                if kind == 'cases':
                    # Old malformed nested lists could expose the next answer's list ordinal as text.
                    original = re.sub(r'(?m)^\d+\.\s+', '', original)
                raw = re.sub(r'^однойстрокой[.:]', '', normalize(original))
                if kind == 'cases':
                    raw = re.sub(r'^условие[.:]', '', raw)
                    raw = re.sub(r'^источник(?:случая)?[.:]', '', raw)
                    raw = re.sub(r'^подвох(?:задачи)?[.:]', '', raw)
                    if raw.rstrip('.:') in ('вопросы', 'эталонныеответы'):
                        continue
                if raw.replace(':', '') and raw.replace(':', '') not in corpus:
                    errors.append(f'{kind}: missing source fragment: {raw[:140]}')
    return errors


def validate(number):
    topic = topic_by_number(number)
    b.configure_topic(topic)
    if not b.jload('layout.json').get('reference'):
        raise ValueError('layout.json with reference=true is required')
    parts = b.jload('layout.json')['parts']
    if len(parts) != 7 or len({p['id'] for p in parts}) != 7:
        raise ValueError('Exactly seven distinct parts required')
    output = WORK / 'checks' / b.SLUG
    output.mkdir(parents=True, exist_ok=True)
    b.SITE = output
    b.copy_images = lambda: None  # Rendering reads image inventory from original images/.
    build_reference_topic(b)
    errors = fidelity(b.SLUG, output)
    shapes = []
    for kind in ('index', 'short', 'full', 'card', 'test', 'cases', 'images', 'sources'):
        text = (output / f'{kind}.html').read_text(encoding='utf-8')
        side = re.search(r'<aside class="side".*?</aside>', text, re.S)[0]
        shapes.append(re.sub(r' is-active| is-on| aria-current="page"| hidden', '', side))
        if kind in ('short', 'full') and len(re.findall(r'<section class="sec"', text)) != 7:
            errors.append(f'{kind}: expected seven rendered parts')
    if len(set(shapes)) != 1:
        errors.append('Sidebar structure differs between pages')
    quiz = json.loads(re.search(r'id="quiz-data">(.*?)</script>', (output / 'test.html').read_text(encoding='utf-8'), re.S)[1])
    expected, missing = reference_questions(b, b.read('4_tests.md'), b.jload('layout.json').get('quiz_unkeyed_policy') == 'preserve')
    if quiz['questions'] != expected:
        errors.append('Question bank altered')
    if len(b.CARD_TOC) != len(b.jload('layout.json').get('card_refs', [])) and number != 2:
        errors.append('card_refs must match every card block')
    if any(str(ref) not in b.REF_MAP for ref in b.jload('layout.json').get('card_refs', []) if ref):
        errors.append('A card reference points to an absent full-material section')
    case_text = (output / 'cases.html').read_text(encoding='utf-8')
    if 'class="q-plain"></ol>' in case_text or 'class="qa-list"></ol>' in case_text:
        errors.append('A case has no parsed questions or answers')
    result = {'number': number, 'slug': b.SLUG, 'passed': not errors, 'errors': errors,
              'questions_with_keys': len(quiz['questions']), 'unkeyed_preserved': bool(missing),
              'questions_without_keys': len(re.findall(r'(?m)^(?:\*\*)?\d+\.(?:\*\*)?\s', missing)),
              'cases': len(re.findall(r'<section class="case"', case_text)), 'card_tiles': len(b.CARD_TOC)}
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / f'{b.SLUG}.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    update_status()
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=('capture', 'inspect', 'validate'))
    parser.add_argument('number', type=int, nargs='?')
    args = parser.parse_args()
    if args.command == 'capture':
        capture()
    elif args.command == 'inspect':
        inspect(args.number)
    else:
        sys.exit(validate(args.number))
