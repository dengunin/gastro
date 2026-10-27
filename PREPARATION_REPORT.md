# Подготовка локального репозитория GitHub Pages

Исторический отчёт подготовки от 25.10.2026. После первоначального переноса в приватный репозиторий владелец 27.10.2026 разрешил открыть `dengunin/gastro` и опубликовать сайт без пароля через GitHub Pages. Используется workflow `pages.yml`; актуальная инструкция находится в README.

Дата: 25.10.2026. Корень будущего репозитория — эта папка `github-pages/`.

Подготовлены **43 темы**, **264 исходника Markdown/JSON**, **342 изображения** и 43 файла `meta.json`. Оригиналы в рабочей папке `Claude/` сохранены. Для каждой темы использован отдельный агент; агенты запускались последовательно. Перенос не меняет медицинские формулировки и не является проверкой их клинической корректности.

## Дерево файлов

```text
github-pages/
├── .github/workflows/pages.yml
├── .gitignore
├── README.md
├── PREPARATION_REPORT.md
├── SOURCE_MANIFEST.json
├── requirements.txt
├── topics/
│   ├── 01_metody_diagnostiki/
│   ├── 02_farmakologiya/
│   ├── 03_organizatsiya_pomoshchi/
│   ├── 04_gerb_barrett/
│   ├── 05_eozinofilnyy_ezofagit/
│   ├── 06_akhalaziya_motorika/
│   ├── 07_disfagiya_ezofagity/
│   ├── 08_helicobacter_pylori/
│   ├── 09_gastrit_atrofiya/
│   ├── 10_yazvennaya_bolezn_nsaid/
│   ├── 11_funkcionalnaya_dispepsiya/
│   ├── 12_zhkk/
│   ├── 13_predrak_rak_verkhnih_otdelov/
│   ├── 14_celiakiya/
│   ├── 15_sibr_malabsorbciya/
│   ├── 16_khronicheskaya_diareya/
│   ├── 17_srk/
│   ├── 18_zapor/
│   ├── 19_yazvennyy_kolit/
│   ├── 20_infekcionnaya_diareya_cdiff/
│   ├── 21_bolezn_krona/
│   ├── 22_divertikulyarnaya_bolezn/
│   ├── 23_ishemicheskiy_kolit_anorektalnye/
│   ├── 24_polipy_skrining_krr/
│   ├── 25_pechenochnye_proby_zheltukha/
│   ├── 26_lekarstvennoe_porazhenie_pecheni/
│   ├── 27_mazhbp/
│   ├── 28_alkogolnaya_bolezn_pecheni/
│   ├── 29_autoimmunnyy_gepatit/
│   ├── 30_virusnye_gepatity/
│   ├── 31_pbkh_psh_igg4/
│   ├── 32_gemokhromatoz_vilson_a1at/
│   ├── 33_cirroz_oslozhneniya/
│   ├── 34_ochagovye_obrazovaniya_gck/
│   ├── 35_pechen_beremennost/
│   ├── 36_zhkb_polipy_zhp/
│   ├── 37_funkcionalnye_biliarnye_phes/
│   ├── 38_ostryy_pankreatit/
│   ├── 39_khronicheskiy_pankreatit_vnpzh/
│   ├── 40_kisty_rak_pzh/
│   ├── 41_nutriciologiya/
│   ├── 42_osobye_gruppy/
│   ├── 43_ot_zhaloby_k_diagnozu/
│   └── В каждой теме: meta.json, 1_full.md, 2_short.md, 3_card.md,
│       4_tests.md, 5_cases.md, 6_images.md, images/
│       В Теме 1 дополнительно: 5_cases_staged.md,
│       cases.json, figures.json, sources.json, structure.json, verify.json
├── tools/
│   ├── build_site.py
│   ├── check_site.py
│   ├── tests/test_build_site.py
│   └── site_assets/
│       ├── app.js
│       ├── quiz.js
│       ├── style.css
│       ├── brand/                 # 5 SVG
│       └── fonts/                 # 4 TTF и 2 лицензии OFL
└── site/                          # сборка; игнорируется Git
    ├── .nojekyll
    ├── index.html
    ├── topics.html
    ├── assets/
    └── topics/<slug>/
        ├── index.html, short.html, full.html, card.html
        ├── test.html, cases.html, images.html, sources.html
        ├── assets/search.js
        └── img/
```

## Что изменено в build_site.py

- Вместо выбора одной темы по аргументу командной строки генератор находит все `topics/<NN_slug>/meta.json`. Номер, название и дисциплина загружаются из метаданных; число тем и списки нигде не закреплены вручную.
- Добавлены проверка метаданных, сортировка по дисциплине и номеру, группировка дисциплин в каталоге. Папки без `meta.json` и служебные папки с `_` или `.` в начале не публикуются.
- Главная и «Все темы» строятся из одного списка метаданных. На страницах темы название дисциплины в шапке берётся из её `meta.json`.
- Все темы собираются за один запуск в `site/topics/<slug>/`; состояние ссылок, источников, схем и навигации сбрасывается между темами. Общие CSS, JS, бренд и шрифты копируются один раз в `site/assets/`, поисковые индексы остаются отдельными.
- Ссылки между исходными Markdown-файлами преобразуются в адреса HTML-страниц: например, `../18_zapor/1_full.md` → `../18_zapor/full.html`. Исходный Markdown остаётся неизменным.
- Корень определяется через `Path(__file__).resolve()`. Ссылки относительные, включая общие ресурсы, поиск, галерею и переходы в каталог. Имя GitHub-репозитория и пути к компьютеру не нужны.
- Схемы читаются из `topics/<slug>/images/`; поддерживаются WebP, SVG, PNG и JPEG. Сохранены пары light/dark и кадрирование Темы 1. При отсутствии метаданных размеров сохраняются исходные пропорции.
- Исправлен разбор соседних схем: несколько изображений внутри одного Markdown-блока больше не теряются; другие цитаты и текст вокруг схем сохраняются.
- Тема 1 сохраняет специальную вёрстку, интерактивный тест и задачи. Остальные темы отображают исходный Markdown в том же фирменном оформлении; тесты с ответами и задачи остаются текстовыми. Для них не создаются вымышленные реестры проверки источников.
- Убраны фиксированные строки «одна тема», «из 30» и название дисциплины. В заголовках страниц используется `meta.json`; дата сверки показывается только при наличии её в исходном реестре.
- Пересборка очищает только свою сгенерированную папку `site/`; проверка метаданных выполняется до очистки.

В `tools/site_assets/app.js` путь к индексу поиска берётся из атрибута страницы, чтобы общий скрипт работал на любой глубине.

## Локальная проверка

Из корня `github-pages/`:

```sh
python -m pip install -r requirements.txt
python -m unittest discover -s tools/tests
python tools/build_site.py
python tools/check_site.py
python -m http.server 8000
```

Для проверки подпапки откройте `http://localhost:8000/site/`.

Результат технических проверок: **346 HTML-страниц**, **21165 внутренних ссылок и ресурсов**, ошибок ссылок, якорей и выхода за адрес `/repository-name/` — **0**. Четыре регрессионные проверки покрывают автоматическое подключение тем и разные дисциплины, сборку из другого рабочего каталога, очистку устаревших страниц, отказ при ошибочных метаданных до очистки, несколько соседних схем и преобразование межтематических Markdown-ссылок в HTML.

В браузере выборочно проверены каталог, переход в Тему 1, интерактивный тест и поиск, общий шаблон Темы 2 и её схемы. Полная визуальная и клиническая проверка всех материалов не выполнялась.

SHA-256 всех скопированных учебных исходников и изображений сверены с оригиналами; перечень находится в `SOURCE_MANIFEST.json`.

В исходной папке ресурсов отсутствуют готовые пары изображений для **10 схем**: `23-02`, `23-04`, `24-01`, `24-02`, `25-01`, `25-02`, `26-01`, `27-02`, `28-01`, `28-02`. Их описания сохранены; на сайте показывается пометка «Схема пока не добавлена», без битых ссылок. Новые изображения не генерировались. Это ограничение исходного набора ресурсов, а не ошибка копирования. Перечень также записан в `SOURCE_MANIFEST.json`.

## Исключения и перенос в Git

В чистую папку не переносились `_archive_*`, `_system/`, рабочие аудиты, макеты, личные заметки и `7_images_status.md`. `.gitignore` также исключает `site/`, окружения, кэши, временные файлы и личные папки. Исходный ZIP сформирован по разрешённому списку; `site/` и `.work/` в него не входят.

GitHub-репозиторий и публикация не создавались. После переноса этой папки в корень репозитория с веткой `main` выберите **Settings → Pages → Source: GitHub Actions**. Workflow собирает `python tools/build_site.py`, проверяет результат и публикует `site/`. Конфигурация основана на [официальной документации GitHub Pages](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages). Сам workflow пока не запускался на GitHub.

## Перенесённые темы

| № | Название | Папка | Агент |
|---|---|---|---|
| 1 | Методы диагностики в гастроэнтерологии | `topics/01_metody_diagnostiki/` | `topic_01` |
| 2 | Фармакология основных групп | `topics/02_farmakologiya/` | `topic_02` |
| 3 | Организация помощи по профилю «гастроэнтерология» | `topics/03_organizatsiya_pomoshchi/` | `topic_03` |
| 4 | ГЭРБ и пищевод Барретта | `topics/04_gerb_barrett/` | `topic_04` |
| 5 | Эозинофильный эзофагит | `topics/05_eozinofilnyy_ezofagit/` | `topic_05` |
| 6 | Ахалазия и нарушения моторики пищевода | `topics/06_akhalaziya_motorika/` | `topic_06` |
| 7 | Дисфагия; инфекционные и лекарственные эзофагиты | `topics/07_disfagiya_ezofagity/` | `topic_07` |
| 8 | Инфекция H. pylori | `topics/08_helicobacter_pylori/` | `topic_08` |
| 9 | Хронический гастрит, атрофия, кишечная метаплазия, аутоиммунный гастрит | `topics/09_gastrit_atrofiya/` | `topic_09` |
| 10 | Язвенная болезнь и НПВП-гастропатия | `topics/10_yazvennaya_bolezn_nsaid/` | `topic_10` |
| 11 | Функциональная диспепсия и гастропарез | `topics/11_funkcionalnaya_dispepsiya/` | `topic_11` |
| 12 | Желудочно-кишечное кровотечение: распознать и направить | `topics/12_zhkk/` | `topic_12` |
| 13 | Предраковые состояния и рак пищевода и желудка | `topics/13_predrak_rak_verkhnih_otdelov/` | `topic_13` |
| 14 | Целиакия и глютен-ассоциированные состояния | `topics/14_celiakiya/` | `topic_14` |
| 15 | СИБР, мальабсорбция, лактазная недостаточность | `topics/15_sibr_malabsorbciya/` | `topic_15` |
| 16 | Хроническая диарея, микроскопический колит, желчнокислотная диарея | `topics/16_khronicheskaya_diareya/` | `topic_16` |
| 17 | Синдром раздражённого кишечника | `topics/17_srk/` | `topic_17` |
| 18 | Хронический запор, диссинергия | `topics/18_zapor/` | `topic_18` |
| 19 | Язвенный колит | `topics/19_yazvennyy_kolit/` | `topic_19` |
| 20 | Инфекционная диарея, C. difficile, антибиотик-ассоциированная диарея | `topics/20_infekcionnaya_diareya_cdiff/` | `topic_20` |
| 21 | Болезнь Крона | `topics/21_bolezn_krona/` | `topic_21` |
| 22 | Дивертикулярная болезнь | `topics/22_divertikulyarnaya_bolezn/` | `topic_22` |
| 23 | Ишемический колит, аноректальные болезни | `topics/23_ishemicheskiy_kolit_anorektalnye/` | `topic_23` |
| 24 | Колоректальные полипы и скрининг колоректального рака | `topics/24_polipy_skrining_krr/` | `topic_24` |
| 25 | Изменённые печёночные пробы, желтуха, синдром Жильбера | `topics/25_pechenochnye_proby_zheltukha/` | `topic_25` |
| 26 | Лекарственное поражение печени | `topics/26_lekarstvennoe_porazhenie_pecheni/` | `topic_26` |
| 27 | МАЖБП | `topics/27_mazhbp/` | `topic_27` |
| 28 | Алкогольная болезнь печени | `topics/28_alkogolnaya_bolezn_pecheni/` | `topic_28` |
| 29 | Аутоиммунный гепатит | `topics/29_autoimmunnyy_gepatit/` | `topic_29` |
| 30 | Хронические вирусные гепатиты B, C, D | `topics/30_virusnye_gepatity/` | `topic_30` |
| 31 | ПБХ, ПСХ, IgG4-ассоциированная болезнь | `topics/31_pbkh_psh_igg4/` | `topic_31` |
| 32 | Гемохроматоз, болезнь Вильсона, дефицит А1АТ | `topics/32_gemokhromatoz_vilson_a1at/` | `topic_32` |
| 33 | Цирроз печени и его осложнения | `topics/33_cirroz_oslozhneniya/` | `topic_33` |
| 34 | Очаговые образования печени, скрининг ГЦК | `topics/34_ochagovye_obrazovaniya_gck/` | `topic_34` |
| 35 | Болезни печени при беременности | `topics/35_pechen_beremennost/` | `topic_35` |
| 36 | ЖКБ, сладж, полипы желчного пузыря | `topics/36_zhkb_polipy_zhp/` | `topic_36` |
| 37 | Функциональные расстройства желчного пузыря и сфинктера Одди, постхолецистэктомический синдром | `topics/37_funkcionalnye_biliarnye_phes/` | `topic_37` |
| 38 | Острый панкреатит: амбулаторный этап | `topics/38_ostryy_pankreatit/` | `topic_38` |
| 39 | Хронический панкреатит и внешнесекреторная недостаточность | `topics/39_khronicheskiy_pankreatit_vnpzh/` | `topic_39` |
| 40 | Кистозные образования и рак поджелудочной железы | `topics/40_kisty_rak_pzh/` | `topic_40` |
| 41 | Нутрициология в гастроэнтерологии | `topics/41_nutriciologiya/` | `topic_41` |
| 42 | Особые группы | `topics/42_osobye_gruppy/` | `topic_42` |
| 43 | От жалобы к диагнозу: синдромный подход | `topics/43_ot_zhaloby_k_diagnozu/` | `topic_43` |
