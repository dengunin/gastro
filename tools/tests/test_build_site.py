"""Regression checks for discovery, metadata and independent topic state."""
import json
import importlib.util
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class BuildSiteTest(unittest.TestCase):
    def setUp(self):
        temporary_root = ROOT / ".work"
        temporary_root.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=temporary_root)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "repo"
        shutil.copytree(ROOT / "tools", self.root / "tools", ignore=shutil.ignore_patterns("__pycache__"))

    def topic(self, slug, number, title, discipline="Пробная дисциплина"):
        topic = self.root / "topics" / slug
        topic.mkdir(parents=True)
        (topic / "meta.json").write_text(json.dumps(dict(number=number, title=title, discipline=discipline), ensure_ascii=False), encoding="utf-8")
        for name in ("1_full", "2_short", "3_card", "4_tests", "5_cases", "6_images"):
            (topic / f"{name}.md").write_text("# Исходный заголовок\n\n## 1. Раздел\n\nТекст без изменений.\n\n### 1.1. Подраздел\n\nСм. раздел 1.1.\n", encoding="utf-8")
        return topic

    def build(self):
        return subprocess.run([sys.executable, str(self.root / "tools" / "build_site.py")], cwd=self.temp.name,
                              capture_output=True, encoding="utf-8", errors="replace")

    def test_discovery_metadata_subpath_and_rebuild(self):
        self.topic("02_second", 2, "Вторая & тема")
        self.topic("01_first", 1, "Первая тема", "Другая дисциплина")
        ignored = self.root / "topics" / "03_without_meta"
        ignored.mkdir()
        result = self.build()
        self.assertEqual(result.returncode, 0, result.stderr)
        home = (self.root / "site" / "index.html").read_text(encoding="utf-8")
        self.assertIn("Вторая &amp; тема", home)
        self.assertIn("Другая дисциплина", home)
        self.assertNotIn("03_without_meta", home)
        full = (self.root / "site" / "topics" / "02_second" / "full.html").read_text(encoding="utf-8")
        self.assertIn("<b>Пробная дисциплина</b>", full)
        self.assertIn('href="../../assets/style.css', full)
        self.assertIn('href="full.html#section-2"', full)
        self.assertIn("Текст без изменений.", full)
        check = subprocess.run([sys.executable, str(self.root / "tools" / "check_site.py")], capture_output=True, encoding="utf-8")
        self.assertEqual(check.returncode, 0, check.stdout + check.stderr)
        shutil.rmtree(self.root / "topics" / "01_first")
        self.assertEqual(self.build().returncode, 0)
        self.assertFalse((self.root / "site" / "topics" / "01_first").exists())

    def test_invalid_meta_fails_before_replacing_build(self):
        self.topic("01_first", 2, "Wrong number")
        (self.root / "site").mkdir()
        marker = self.root / "site" / "preserve.txt"
        marker.touch()
        result = self.build()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("number must match", result.stderr)
        self.assertTrue(marker.exists())

    def test_reference_topic_preserves_sections_quiz_and_persistent_menu(self):
        source = ROOT / "topics" / "02_farmakologiya"
        shutil.copytree(source, self.root / "topics" / source.name, ignore=shutil.ignore_patterns("images"))
        result = self.build()
        self.assertEqual(result.returncode, 0, result.stderr)
        folder = self.root / "site" / "topics" / source.name
        sidebar_shapes = []
        for kind in ("index", "short", "full", "card", "test", "cases", "images", "sources"):
            text = (folder / f"{kind}.html").read_text(encoding="utf-8")
            side = re.search(r'<aside class="side".*?</aside>', text, re.S)[0]
            side = re.sub(r' is-active| is-on| aria-current="page"| hidden', '', side)
            sidebar_shapes.append(side)
        self.assertEqual(len(set(sidebar_shapes)), 1, "Menu nodes must be present on every page")
        for kind, filename in (("short", "2_short.md"), ("full", "1_full.md")):
            text = (folder / f"{kind}.html").read_text(encoding="utf-8")
            self.assertEqual(text.count('<section class="sec"'), 7)
            # Every source heading keeps its original locator after grouping.
            for index, _ in enumerate(re.findall(r'^#{2,3} ', (source / filename).read_text(encoding="utf-8"), re.M), 1):
                self.assertIn(f'id="section-{index}"', text)
        test = (folder / "test.html").read_text(encoding="utf-8")
        data = json.loads(re.search(r'id="quiz-data">(.*?)</script>', test, re.S)[1])
        self.assertEqual(len(data["questions"]), 100)
        self.assertEqual(data["questions"][0]["a"], 2)
        self.assertEqual(data["questions"][0]["cat"], "Диагностика")
        self.assertTrue(all(len(q["opts"]) == 4 for q in data["questions"]))
        card = (folder / "card.html").read_text(encoding="utf-8")
        self.assertIn('href="full.html#section-7"', card)
        self.assertEqual(len(re.findall(r'<section class="tile ', card)), 6)
        cases = (folder / "cases.html").read_text(encoding="utf-8")
        self.assertEqual(len(re.findall(r'<section class="case"', cases)), 3)
        self.assertIn("магний ниже", cases)
        self.assertIn("33707905", cases)

    def test_reference_parser_formats_and_missing_keys(self):
        def module(name, filename):
            spec = importlib.util.spec_from_file_location(name, self.root / 'tools' / filename)
            value = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(value)
            return value
        build = module('build_fixture', 'build_site.py')
        reference = module('reference_fixture', 'reference_topic.py')
        questions = ['# Тест', '## Вопросы', '## Диагностика']
        for n in range(1, 22):
            questions.extend([f'**{n}.** Исходный вопрос {n}', '   - А) первый', '   - Б) второй', '   - В) третий', '   - Г) четвёртый', ''])
        answers = ['## Ответы'] + [f'{n}. Б — исходное пояснение {n}' for n in range(1, 21)]
        text = '\n'.join(questions + answers)
        with self.assertRaisesRegex(ValueError, 'Missing answer keys'):
            reference.reference_questions(build, text)
        bank, unkeyed = reference.reference_questions(build, text, allow_unkeyed=True)
        self.assertEqual(len(bank), 20)
        self.assertTrue(all(q['a'] == 1 and q['cat'] == 'Диагностика' for q in bank))
        self.assertIn('Исходный вопрос 21', unkeyed)
        self.assertIn('Г) четвёртый', unkeyed)
        self.assertNotIn('Исходный вопрос 20', unkeyed)
        card = reference.normalize_card('# Карточка\n\n## Одной строкой\nИсходный тезис.\n\n## Красные флаги\n- Исходное правило.\n')
        self.assertIn('**Одной строкой:** Исходный тезис.', card)
        self.assertIn('**Красные флаги**\n- Исходное правило.', card)
        cases = reference.normalize_cases('## Задача 1\n### Условие\nПациент 45 лет.\n### Вопросы\n1. Вопрос?\n### Эталонные ответы\n1. Ответ.\n')
        self.assertIn('**Условие.**\nПациент 45 лет.', cases)
        self.assertIn('**Вопросы.**\n1. Вопрос?', cases)
        self.assertIn('**Эталонные ответы.**\n1. Ответ.', cases)
        nested = reference.normalize_cases('## Задача 1. Проверка\n### Условие\nИсходные данные.\n### Вопросы\n1. Что делать?\n### Эталонные ответы\n1. План:\n   - **Первый пункт.**\n   - Второй пункт.\n')
        _, parsed = build.build_pub_cases(nested)
        answer = parsed['1']['panes'][1]['html']
        self.assertNotIn('<pre>', answer)
        self.assertIn('<strong>Первый пункт.</strong>', answer)
        rule = build.card_items(['**Метка:** исходное правило.'], 'colon')[0]
        self.assertIn('<strong>Метка:</strong>', rule)
        self.assertIn('исходное правило.', rule)
        variant = reference.normalize_card('# Карточка\n**Одной строкой.** Исходный тезис.\n\n**Диагноз ставим, если** (исходные критерии):\n- Порог 1,1.\n')
        self.assertIn('**Одной строкой:** Исходный тезис.', variant)
        self.assertIn('**Диагноз ставим, если** (исходные критерии)\n', variant)
        rendered_card = build.build_card(variant)
        self.assertIn('исходные критерии', rendered_card)
        self.assertIn('Порог 1,1.', rendered_card)
        self.assertNotIn('Диагноз ставим, если…', rendered_card)
        with_preface = reference.normalize_card('# Карточка\n\nЖП — желчный пузырь.\n\n## Одной строкой\nТезис.\n\n## Красные флаги\n- Правило.\n')
        self.assertIn('ЖП — желчный пузырь.', build.build_card(with_preface))

    def test_adjacent_figures_do_not_drop_content(self):
        topic = self.topic("01_first", 1, "Схемы")
        (topic / "1_full.md").write_text(
            '# Материал\n\n> Важная цитата.\n\n## 1. Раздел\n\nТекст до схем.\n\n'
            '> **[ИЗОБРАЖЕНИЕ 01-01] Первая схема**\n> Описание: Первое описание.\n>\n'
            '> **[ИЗОБРАЖЕНИЕ 01-02] Вторая схема**\n> Описание: Второе описание.\n\nТекст после схем.\n', encoding="utf-8")
        result = self.build()
        self.assertEqual(result.returncode, 0, result.stderr)
        text = (self.root / "site" / "topics" / "01_first" / "full.html").read_text(encoding="utf-8")
        for fragment in ('Важная цитата.', 'Текст до схем.', 'Текст после схем.', 'id="fig-01-01"', 'id="fig-01-02"'):
            self.assertIn(fragment, text)

    def test_cross_topic_markdown_links_become_html(self):
        first = self.topic("01_first", 1, "Первая")
        self.topic("02_second", 2, "Вторая")
        with (first / "1_full.md").open("a", encoding="utf-8") as out:
            out.write('\n[Другая тема](../02_second/1_full.md)\n\n[Кратко](2_short.md)\n\n'
                      '[Внешний Markdown](https://example.test/1_full.md)\n')
        result = self.build()
        self.assertEqual(result.returncode, 0, result.stderr)
        text = (self.root / "site" / "topics" / "01_first" / "full.html").read_text(encoding="utf-8")
        self.assertIn('href="../02_second/full.html"', text)
        self.assertIn('href="short.html"', text)
        self.assertIn('href="https://example.test/1_full.md"', text)


if __name__ == "__main__":
    unittest.main()
