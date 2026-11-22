# RecurKit

Це навчальний проєкт: бібліотека на Python для календарних повторень за стандартом RFC 5545 (iCalendar). Вона розбирає правила RRULE, генерує дати повторень і враховує часові пояси. Ядро написане лише на стандартній бібліотеці Python; `dateutil` і `zoneinfo` використовуються як еталон у тестах.

Статус: проміжний етап 1 (календарна арифметика, правила, генератор дат, набори повторень, часові пояси, рядки iCalendar).

## Технологічний стек

- **Мова:** Python 3.12
- **Залежності ядра:** лише стандартна бібліотека
- **Тестування:** pytest + Hypothesis
- **Лінтер:** ruff
- **Перевірка типів:** mypy (strict)
- **Шари імпортів:** import-linter

## Приклади використання

### Правило і його дати

```python
from datetime import datetime
from recurkit import RecurrenceSet, Rule, describe

rule = Rule.parse("FREQ=MONTHLY;BYDAY=-1FR;COUNT=4", datetime(2026, 11, 16, 9, 30))
describe(rule)
list(RecurrenceSet(rule))
```

`describe(rule)` повертає `'monthly on the last Friday at 09:30, 4 times'`, а `list(...)` дає:

```text
[datetime(2026, 11, 27, 9, 30), datetime(2026, 12, 25, 9, 30),
 datetime(2027, 1, 29, 9, 30), datetime(2027, 2, 26, 9, 30)]
```

Наївний DTSTART дає «плаваючий» час, DTSTART в UTC дає значення в UTC, а `date` дає серію на цілий день. Дати генеруються ліниво, тому нескінченні правила працюють: беріть потрібну кількість через `itertools.islice` або запитуйте вікно.

### Текст iCalendar з часовим поясом

```python
from recurkit.ical import format_recurrence, parse_recurrence

rset = parse_recurrence("""DTSTART;TZID=Europe/Kyiv:20260106T100000
RRULE:FREQ=MONTHLY;BYDAY=2TU;COUNT=6
EXDATE;TZID=Europe/Kyiv:20260310T100000
RDATE;TZID=Europe/Kyiv:20260320T120000""")

window = rset.between(datetime(2026, 2, 1), datetime(2026, 4, 1))
rset.after(datetime.fromisoformat("2026-03-01T00:00+02:00"))
format_recurrence(rset)
```

`between` ліниво повертає 10.02 10:00+02:00 і 20.03 12:00+02:00 (10.03 виключено через EXDATE). `after` дає `datetime(2026, 3, 20, 12, 0, tzinfo=+02:00)`. `format_recurrence` знову видає рядки DTSTART/RRULE/RDATE/EXDATE, згорнуті й розділені CRLF.

Значення набору з поясом — aware datetime зі зміщенням пояса в цей момент. Для місцевого часу, якого не існує або який трапляється двічі, діють фіксовані правила (див. [docs/decisions.md](docs/decisions.md), D-05):

- екземпляр правила, що потрапив у «дірку» переходу на літній час, відкидається і не рахується в COUNT;
- явні DTSTART, RDATE або EXDATE у «дірці» зсуваються вперед на її довжину;
- подвійний час означає його перше входження.

```python
k = parse_recurrence("DTSTART;TZID=Europe/Kyiv:20260327T033000\nRRULE:FREQ=DAILY;COUNT=3")
```

Дати: 27.03 03:30+02:00, 28.03 03:30+02:00, 30.03 03:30+03:00 (29.03 03:30 не існує).

Часові пояси надає `TimeZoneProvider`: `ZoneInfoProvider` (база IANA через `zoneinfo`, за замовчуванням) або `FakeProvider` із синтетичними поясами, зокрема заданими POSIX TZ-рядками на кшталт `EST5EDT,M3.2.0,M11.1.0`.

### Помилки

Усі помилки походять від `RecurKitError`. Некоректні правила дають `RuleSyntaxError` (з позицією в тексті) або `RuleValidationError` з ідентифікатором порушеної вимоги з [docs/requirements.md](docs/requirements.md):

```python
Rule.parse("FREQ=WEEKLY;BYWEEKNO=10", datetime(2026, 1, 1))
```

```text
RuleValidationError: [RRULE-24] BYWEEKNO may only be used with FREQ=YEARLY
```

`TimeZoneError` повідомляє про невідомий пояс, `ICalParseError` про некоректний текст iCalendar із номером рядка.

## Архітектура

```
recurkit/
  ical/             рядки вмісту, DTSTART/RRULE/RDATE/EXDATE -> RecurrenceSet
  recurrence_set.py RRULE + RDATE - EXDATE, часові пояси, запити
  expand/           генератор дат у місцевому часі: періоди, BY-фільтри й розширювачі, BYSETPOS
  rule/             модель Rule, парсер RRULE, валідація, опис англійською
  calendar_math.py  високосні роки, довжини місяців, дні тижня, номери тижнів
  timezones/        TimeZoneProvider, ZoneInfoProvider, FakeProvider, POSIX TZ
```

Шари імпортують лише згори вниз (`ical -> recurrence_set -> expand -> rule -> calendar_math`), це перевіряє `import-linter` у CI. Генератор працює в місцевому часі й нічого не знає про пояси: `recurrence_set` перетворює його значення через провайдера і відкидає неіснуючий місцевий час. `zoneinfo` імпортує лише `timezones/zoneinfo_provider.py`, а бібліотека ніколи не читає поточний час.

## Тести

```
tests/unit           поведінка кожного модуля; ID вимог у назвах тестів
tests/property       властивості Hypothesis проти наївного оракула «день за днем»
tests/differential   порівняння з dateutil.rrule і zoneinfo
tests/rfc_examples   приклади повторень з RFC 5545, розділ 3.8.5.3
tests/perf           пам'ять і обсяг роботи лінивої ітерації та запитів за вікном
```

## Інструкції з налаштування

1. Клонуйте репозиторій:

   ```
   git clone https://github.com/Anasstassik/recurkit.git
   ```

2. Перейдіть в каталог проєкту:

   ```
   cd recurkit
   ```

3. Створіть і активуйте віртуальне оточення:

   ```
   python -m venv .venv
   .venv\Scripts\activate
   ```

4. Встановіть проєкт із залежностями для розробки:

   ```
   pip install -e ".[dev]"
   ```

5. Запустіть перевірки й тести:

   ```
   ruff check .
   mypy recurkit
   lint-imports
   pytest -q --cov
   ```

   Змінна `HYPOTHESIS_PROFILE=ci` дає більше прикладів на кожну властивість.
