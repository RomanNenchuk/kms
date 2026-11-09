# Схема витягу знань та інструкція розмітки

Домен: управління авіаційними перевезеннями. Корпус: фрагменти англомовної Вікіпедії (`data/sources.csv`, 26 документів).
Одиниця оцінювання — **твердження (claim)**: трійка *суб'єкт – відношення – об'єкт* з цитатою-доказом у тексті.
Версія схеми: **v1.2** (після пілоту на 5 фрагментах, див. розділи 7–8).

## 1. Типи сутностей (9)

| Тип | Що це | Приклад | Контрприклад |
|---|---|---|---|
| `Airline` | авіакомпанія за назвою | Lufthansa, UIA, Ukraine International Airlines PJSC | «the airline», «carriers» |
| `Airport` | аеропорт за назвою | Warsaw Chopin Airport, Boryspil International Airport | «the airport»; «Okęcie» як район → `Location` |
| `AircraftType` | модель/сімейство/варіант літака | Boeing 767, 767-300ER, Airbus A320neo | «wide-body airliner»; бортовий номер SP-CEA (окремі борти поза схемою) |
| `Organization` | неавіакомпанія: виробник, регулятор, інвестор, лізингова, альянс | Boeing Commercial Airplanes, EASA, EBRD, Swissair, Star Alliance | «the Ministry» без назви; авіакомпанії → `Airline` |
| `Location` | місто, район, країна, регіон | Kyiv, Włochy, Poland | «Warsaw» усередині «Warsaw Chopin Airport» |
| `Flight` | іменований рейс | US Airways Flight 1549, Germanwings Flight 9525 | «a Kyiv–London flight» (маршрут без ідентифікатора) |
| `Event` | іменована подія, що має власну назву | Tenerife airport disaster, Euro 2012 | «the crash», «the strike» без назви |
| `Person` | названа особа | Ignacy Mościcki | «the captain», «pilots» |
| `Regulation` | норма, директива, стандарт | ETOPS rules, ICAO Annex 6, Regulation (EC) No 261/2004 | «the rules», «regulations» загалом |

## 2. Типи відношень (10)

Напрямок фіксований сигнатурою. Приклади — з корпусу.

| Відношення | Сигнатура (суб'єкт → об'єкт) | Приклад | Контрприклад |
|---|---|---|---|
| `HUB_AT` | Airline → Airport | «central hub for LOT Polish Airlines», «a base for Wizz Air» → (LOT, WAW), (Wizz Air, WAW) | «Delta flies to Frankfurt» → `SERVES` |
| `SERVES` | Airline/Flight → Airport/Location | «Kyiv–London flight» → (UIA, London); «scheduled to fly from LaGuardia Airport to Seattle–Tacoma International Airport» → (Flight 1549, Seattle–Tacoma…) | рейс без названого пункту; пункт названо і містом, і аеропортом → лише аеропорт |
| `OPERATES` | Airline → AircraftType | «Delta … 77 aircraft» → (Delta, Boeing 767), count=77 | «Boeing built 767s» → `MANUFACTURED_BY` |
| `MANUFACTURED_BY` | AircraftType → Organization | «767 … manufactured by Boeing Commercial Airplanes» | двигуни (GE CF6) — поза схемою |
| `OWNS_STAKE_IN` | Organization/Airline/Person → Airline/Airport/Organization | «EBRD became a shareholder» → (EBRD, UIA) | лізинг літака (GPA lease) — поза схемою |
| `LOCATED_IN` | Airport/Airline/Organization/Location → Location | «head office in Kyiv» → (UIA, Kyiv) | «hub at Boryspil» → `HUB_AT` |
| `OPERATED_BY` | Flight → Airline | «a regularly scheduled US Airways domestic flight» → (US Airways Flight 1549, US Airways) | «Delta … 77 aircraft» → `OPERATES` |
| `INVOLVED_IN` | Person/Flight/Airline/AircraftType/Airport → Event/Flight | (KLM Flight 4805, Tenerife airport disaster); (Chesley Sullenberger, US Airways Flight 1549), role=pilot in command | авіакомпанія рейсу → `OPERATED_BY` |
| `ISSUED_BY` | Regulation → Organization | «directives are issued by the FAA» | «Boeing complied with the rule» |
| `AGREEMENT_WITH` | Airline/Organization → Airline/Organization; `kind` обов'язковий | «risk-sharing agreements» → (Boeing, Aeritalia), kind=risk_sharing; «Continental paid … from GB Airways» → (Continental Airlines, GB Airways), kind=slot_trade | акціонерство → `OWNS_STAKE_IN` |

**Необов'язкові уточнення (`qualifiers`)**: `time` (ISO 8601: `1996`, `1992-11`, `1992-11-25`), `count` (ціле), `amount` (`{value, currency}`), `role` (для `INVOLVED_IN`: pilot in command, first officer, flight attendant…), `kind` (обов'язковий для `AGREEMENT_WITH`: `codeshare`, `alliance`, `risk_sharing`, `slot_trade`, `other`). Для симетричних видів (`codeshare`, `alliance`, `risk_sharing`) порядок — за появою в тексті; для `slot_trade` суб'єкт — покупець, об'єкт — продавець.
**Модальність**: `asserted` (факт) | `planned` (плани, наміри, «slated for»). Заперечення й припущення **не розмічаємо**.

**Поза схемою (свідомо):** лізинг, двигуни й комплектуючі, конкуренти, окремі літаки за бортовим номером (N106US), нагороди, членство в органах (склад Worldwide Airport Slot Board),
самостійні числові факти («24.1 million passengers in 2025»), погода, час доби — це атрибути, а не відношення. Їх не розмічаємо й не штрафуємо.

## 3. Інструкція розмітки

Розмітник працює з файлом `data/raw/Dxx.txt` як є (назва + порожній рядок + текст); офсети — у символах Unicode від початку файлу.

1. **R1. Лише те, що сказано в тексті.** Світові знання не використовуємо: якщо зв'язок не підтверджений реченням — твердження немає.
2. **R2. Мінімальний іменований проміжок.** Мітка (mention) — власна назва без артикля, описових слів і присвійного «'s»: «LOT Polish Airlines», а не «the national carrier LOT Polish Airlines»; «New York City's LaGuardia Airport» → «New York City» + «LaGuardia Airport». Прізвисько всередині імені залишається в мітці: `Chesley "Sully" Sullenberger`.
3. **R3. Вкладені назви.** Анотуємо найдовшу: у «Warsaw Chopin Airport» окремої `Location` «Warsaw» немає.
4. **R4. Узагальнення й анафора.** «The airline», «it», «its» не розмічаємо як мітки. Єдиний виняток — **тема документа** (сутність із заголовка): якщо вона пропущена або виражена анафорою, ставимо `implicit_topic: true` (див. розділ 4).
5. **R5. Перелік розбиваємо.** «Berlin, Paris, Frankfurt» → окреме твердження на кожен елемент із тим самим доказом.
6. **R6. Напрямок за сигнатурою.** Якщо в тексті порядок інший (пасив, «with X»), міняємо суб'єкт/об'єкт так, щоб відповідати сигнатурі.
7. **R7. Доказ (evidence).** Точний фрагмент тексту (зазвичай одне речення, ≤ 300 символів), що містить обидві мітки або (для `implicit_topic`) підтверджує зв'язок. Парафраз не допускається.
8. **R8. Час.** Дату з речення записуємо у `qualifiers.time`; історичність не скасовує твердження («was the flag carrier» — теж твердження).
9. **R9. Модальність.** «Plans for expansion», «slated for completion» → `planned`; «may», «could», «not» → не розмічаємо.
10. **R10. Тип за контекстом.** «Okęcie» як назва аеропорту — `Airport`, як район — `Location`.
11. **R11. Відносні дати.** «A year before» розв'язуємо лише якщо опорна дата є в тому ж тексті (лютий 2016 → 2015); інакше `time` не ставимо.
12. **R12. Прізвиська та колишні назви** («Miracle on the Hudson», «Sully», «CACTUS 1549», «Warsaw Okęcie Airport») — аліаси сутності (див. нормалізацію), а не окремі сутності чи відношення.

**Граничні випадки (рішення):**
- *Ланцюг локацій* («Włochy district of Warsaw, Poland»): лише перша ланка — суб'єкт → найближча названа локація; решту не розмічаємо.
- *Скорочення* («UIA», «PJSC») — це та сама сутність, аліас, не окремі твердження.
- *Заголовки розділів* («History», «Developments since 2013») — не розмічаємо.
- *Технічні артефакти тексту* («asa base», «Bythis», «officein» — склеєні слова з вилучення Вікіпедії): мітки й докази беремо **без виправлень**, символ у символ, як у файлі.
- *Варіант і сімейство* («767-200» і «Boeing 767») — окремі `AircraftType`; ієрархії між ними схема не має.
- *Подія названа рейсом* (US Airways Flight 1549) — лише `Flight`, окремого `Event` немає; учасники (екіпаж) пов'язуються з рейсом через `INVOLVED_IN` із `role`.
- *Пункт названо і містом, і аеропортом* (Charlotte / Charlotte Douglas International Airport) — `SERVES` лише до аеропорту.
- *Купівля слотів* — `AGREEMENT_WITH`, `kind=slot_trade`, покупець → продавець, сума в `amount`.

## 4. Формат виходу (JSON Schema)

Один рядок `data/gold.jsonl` = одне твердження. Метод Б (LLM) повертає ті самі поля, але **без `start`/`end`**: офсети обчислює код пошуком `text` у документі, і якщо підрядка немає — твердження позначається як «без підтвердженої цитати» (це й є метрика вигаданих тверджень).

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "Claim",
  "type": "object",
  "required": ["claim_id", "doc_id", "subject", "relation", "object", "evidence", "modality"],
  "additionalProperties": false,
  "properties": {
    "claim_id": {"type": "string", "pattern": "^D\\d{2}-\\d{3}$"},
    "doc_id": {"type": "string", "pattern": "^D\\d{2}$"},
    "subject": {"$ref": "#/$defs/entity"},
    "relation": {"enum": ["HUB_AT", "SERVES", "OPERATES", "MANUFACTURED_BY", "OWNS_STAKE_IN",
                          "LOCATED_IN", "OPERATED_BY", "INVOLVED_IN", "ISSUED_BY", "AGREEMENT_WITH"]},
    "object": {"$ref": "#/$defs/entity"},
    "evidence": {
      "type": "object", "required": ["text"], "additionalProperties": false,
      "properties": {"text": {"type": "string", "maxLength": 300},
                     "start": {"type": "integer", "minimum": 0}, "end": {"type": "integer", "minimum": 1}}
    },
    "qualifiers": {
      "type": "object", "additionalProperties": false,
      "properties": {
        "time": {"type": "string", "pattern": "^\\d{4}(-\\d{2}(-\\d{2})?)?$"},
        "count": {"type": "integer", "minimum": 0},
        "amount": {"type": "object", "required": ["value", "currency"],
                   "properties": {"value": {"type": "number"}, "currency": {"type": "string", "pattern": "^[A-Z]{3}$"}}},
        "role": {"type": "string", "pattern": "^[a-z ]+$"},
        "kind": {"enum": ["codeshare", "alliance", "risk_sharing", "slot_trade", "other"]}
      }
    },
    "modality": {"enum": ["asserted", "planned"]},
    "annotator": {"type": "string"},
    "confidence": {"type": "number", "minimum": 0, "maximum": 1}
  },
  "$defs": {
    "entity": {
      "type": "object", "required": ["type", "canonical"], "additionalProperties": false,
      "properties": {
        "type": {"enum": ["Airline", "Airport", "AircraftType", "Organization", "Location",
                          "Flight", "Event", "Person", "Regulation"]},
        "canonical": {"type": "string", "pattern": "^[a-z]+:[a-z0-9_]+$"},
        "text": {"type": "string"},
        "start": {"type": "integer", "minimum": 0},
        "end": {"type": "integer", "minimum": 1},
        "implicit_topic": {"type": "boolean"}
      }
    }
  }
}
```

Додаткові правила валідації (код, не JSON Schema): `relation` узгоджується з типами за таблицею розділу 2; для `AGREEMENT_WITH` обов'язковий `qualifiers.kind`; `text` суб'єкта/об'єкта й `evidence.text` — точні підрядки документа; при `implicit_topic: true` поля `text/start/end` відсутні, а `canonical` збігається з сутністю із заголовка документа; `evidence` містить обидві мітки.

Приклад (D06; офсети рахуються від початку файлу, заголовок «Warsaw Chopin Airport» + `\n\n` займають перші 23 символи):

```json
{"claim_id":"D06-001","doc_id":"D06",
 "subject":{"type":"Airport","canonical":"airport:warsaw_chopin_airport","text":"Warsaw Chopin Airport","start":0,"end":21},
 "relation":"LOCATED_IN",
 "object":{"type":"Location","canonical":"location:wlochy","text":"Włochy","start":186,"end":192},
 "evidence":{"text":"Warsaw Chopin Airport (Polish: Lotnisko Chopina w Warszawie, Polish pronunciation: [lɔtˈɲiskɔ ʂɔˈpɛna]) (IATA: WAW, ICAO: EPWA) is an international airport in the Włochy district of Warsaw, Poland.","start":23,"end":220},
 "modality":"asserted","annotator":"A1"}
```

## 5. Правила нормалізації

1. **Рядки:** Unicode NFC; обрізання пробілів по краях; регістр і діакритика в `text` зберігаються, у `canonical` — ні.
2. **Ідентифікатор `canonical`:** `<тип_малими>:<slug>`, де slug — повна назва з Вікіпедії, ASCII-транслітерація (ł→l, ó→o), малі літери, усе, що не `[a-z0-9]`, → `_`. Приклад: `airline:ukraine_international_airlines`, `aircrafttype:boeing_767`, `location:wlochy`.
3. **Аліаси → одна сутність:** скорочення (UIA, NTSB), повні форми («Ukraine International Airlines PJSC»), колишні назви («Warsaw Okęcie Airport»), прізвиська («Miracle on the Hudson», «Sully», «CACTUS 1549»). Таблиця аліасів — `data/aliases.csv` (створюється під час розмітки); `canonical` береться з неї.
4. **Коди:** IATA (2/3 літери), ICAO (4 літери) великими літерами; зберігаються як атрибути сутності, а не як окремі мітки.
5. **Час:** ISO 8601 (`YYYY`, `YYYY-MM`, `YYYY-MM-DD`); «November 25, 1992» і «25 November 1992» → `1992-11-25`.
6. **Числа й гроші:** без роздільників тисяч; «US$9 million» → `{"value": 9000000, "currency": "USD"}`.
7. **Тип сутності незмінний у межах `canonical`:** один `canonical` — один тип.

## 6. Контроль якості розмітки

- Два розмітники незалежно розмічають ≥ 30 тверджень; κ (Коена) рахується за рішенням «твердження збігається» (суб'єкт, відношення, об'єкт, документ) окремо від типів сутностей.
- Розбіжності розбираються за інструкцією; зміни фіксуються в журналі нижче й підвищують версію схеми.

## 7. Пілотна розмітка

Фрагменти: **P1** — D06 (Warsaw Chopin Airport), вступ; **P2** — D04 (UIA), вступ та «Early history»; **P3** — D20 (Boeing 767), вступ і «Development»; **P4** — D14 (US Airways Flight 1549), вступ і «Background»; **P5** — D21 (Airport slot), вступ і абзац про торгівлю слотами. *Чернетка підготовлена за допомогою Claude, автор перевірив кожне твердження за текстом (позначка перевірки — у `claims/claims.csv`).*

| # | Фр. | Суб'єкт | Відношення | Об'єкт | Доказ (скорочено) | Уточнення |
|---|---|---|---|---|---|---|
| 1 | P1 | Warsaw Chopin Airport | LOCATED_IN | Włochy | «…international airport in the Włochy district of Warsaw, Poland.» | |
| 2 | P1 | LOT Polish Airlines | HUB_AT | *(тема: аеропорт)* | «The airport is a central hub for LOT Polish Airlines…» | implicit_topic |
| 3 | P1 | Enter Air | HUB_AT | *(тема)* | «…a base for Enter Air and Wizz Air.» | R5 |
| 4 | P1 | Wizz Air | HUB_AT | *(тема)* | те саме речення | R5 |
| 5 | P2 | Ukraine International Airlines | LOCATED_IN | Kyiv | «…with its head office in Kyiv…» | |
| 6 | P2 | Ukraine International Airlines | HUB_AT | Boryspil International Airport | «…its main hub at Kyiv's Boryspil International Airport.» | R3 |
| 7 | P2 | Austrian Airlines | OWNS_STAKE_IN | *(тема: UIA)* | «In 1996, Austrian Airlines and Swissair became shareholders, investing US$9 million…» | time=1996, amount |
| 8 | P2 | Swissair | OWNS_STAKE_IN | *(тема)* | те саме речення | R5 |
| 9 | P2 | European Bank for Reconstruction and Development | OWNS_STAKE_IN | *(тема)* | «In 2000, the EBRD became a shareholder by investing US$5.4 million.» | time=2000 |
| 10 | P2 | *(тема: UIA)* | SERVES | London | «…beginning with a Kyiv-London flight on 25 November 1992.» | time=1992-11-25 |
| 11–15 | P2 | *(тема)* | SERVES | Berlin / Paris / Frankfurt / Vienna / Amsterdam | «Other routes … connected Kyiv with Berlin, Paris, Frankfurt, Vienna, and Amsterdam.» | R5 |
| 16 | P3 | Boeing 767 | MANUFACTURED_BY | Boeing Commercial Airplanes | «…developed and manufactured by Boeing Commercial Airplanes.» | |
| 17 | P3 | United Airlines | OPERATES | Boeing 767-200 | «…767-200 variant entered service on September 8, 1982, with United Airlines» | time=1982-09-08, R6 |
| 18 | P3 | Delta Air Lines | OPERATES | Boeing 767 | «…Delta Air Lines being the largest operator with 77 aircraft…» | count=77, time=2018-07 |
| 19 | P3 | Boeing | AGREEMENT_WITH | Aeritalia | «Boeing signed risk-sharing agreements with … Aeritalia and the … (CTDC)» | kind=risk_sharing, R5 |
| 20 | P3 | Boeing | AGREEMENT_WITH | Civil Transport Development Corporation | те саме речення | kind=risk_sharing, R5 |
| 21 | P4 | US Airways Flight 1549 | OPERATED_BY | US Airways | «US Airways Flight 1549 was a regularly scheduled US Airways domestic flight from…» | v1.2 |
| 22 | P4 | US Airways Flight 1549 | SERVES | LaGuardia Airport | «…was scheduled to fly from New York City's LaGuardia Airport (LGA) to Seattle–Tacoma International Airport (SEA), with a planned intermediate stop at Charlotte Douglas International Airport (CLT)…» | лише аеропорт |
| 23 | P4 | US Airways Flight 1549 | SERVES | Seattle–Tacoma International Airport | те саме речення | |
| 24 | P4 | US Airways Flight 1549 | SERVES | Charlotte Douglas International Airport | те саме речення | |
| 25 | P4 | LaGuardia Airport | LOCATED_IN | New York City | те саме речення | R2 («'s») |
| 26 | P4 | Charlotte Douglas International Airport | LOCATED_IN | Charlotte | «…Charlotte Douglas International Airport (CLT) in Charlotte, North Carolina.» | R3 |
| 27 | P4 | Chesley "Sully" Sullenberger | INVOLVED_IN | *(тема: рейс)* | «The pilot in command was 57-year-old Captain Chesley "Sully" Sullenberger…» | role=pilot in command |
| 28 | P4 | Jeffrey Skiles | INVOLVED_IN | *(тема)* | «The second in command (co-pilot) was 49-year-old First Officer Jeffrey Skiles…» | role=first officer |
| 29–31 | P4 | Sheila Dail / Donna Dent / Doreen Welsh | INVOLVED_IN | *(тема)* | «There were 150 passengers and 3 flight attendants—Sheila Dail, Donna Dent and Doreen Welsh—on board.» | role=flight attendant, R5 |
| 32 | P5 | Continental Airlines | AGREEMENT_WITH | GB Airways | «In 2008 Continental Airlines paid US$209 million for four pairs of landing slots from GB Airways…» | kind=slot_trade, 209 млн USD, time=2008 |
| 33 | P5 | Oman Air | AGREEMENT_WITH | Air France–KLM | «…was $75m, paid by Oman Air to Air France–KLM…, reported in February 2016.» | slot_trade, 75 млн USD, time=2016-02 |
| 34 | P5 | American Airlines | AGREEMENT_WITH | Scandinavian Airlines | «A year before, American Airlines paid $60m to Scandinavian Airlines.» | slot_trade, 60 млн USD, time=2015, R11 |

**Не розмічено за інструкцією:** лізинг 2 Boeing 737-400 від GPA; двигуни GE CF6/RB211/JT9D і CFM56; конкуренти A300/A310/A330-200; борт N106US і дата його випуску; нагорода Guild of Air Pilots; погода й час (15:24:56); склад Worldwide Airport Slot Board; 24.1 млн пасажирів, 834 га тощо (атрибути).

Усього в пілоті — 34 твердження на 5 фрагментах; після кожного фрагмента інструкцію уточнено (розділ 8).

## 8. Журнал уточнень інструкції (за результатами пілоту)

| № | Проблема в пілоті | Рішення | Правило |
|---|---|---|---|
| 1 | Суб'єкт/об'єкт — тема документа, але без назви в реченні («The airport is a hub for…», «became shareholders») | Дозволено `implicit_topic: true` без офсетів; лише для сутності із заголовка | R4 |
| 2 | Ланцюг «Włochy district of Warsaw, Poland» породжує тривіальні твердження | Анотується лише перша ланка | граничні випадки |
| 3 | У текстах склеєні слова («asa base», «Bythis») і заголовки розділів без тексту | Мітки беруться без виправлень; заголовки не розмічаються | граничні випадки |
| 4 | Лізинг, двигуни, конкуренти й числа не вкладаються в 10 відношень | Свідомо винесені за схему; список наведено в розділі 2 | розділ 2 |
| 5 | Рейс-подія (Flight 1549) дублювався як `Event` | Подія, названа рейсом, — лише `Flight`; екіпаж пов'язується через `INVOLVED_IN` (об'єкт може бути `Flight`) з `role` | граничні випадки, розділ 2 |
| 6 | Колишні назви й прізвиська (Okęcie, «Miracle on the Hudson») не потребують окремого відношення | `FORMERLY_KNOWN_AS` видалено; це аліаси в `aliases.csv`; звільнений слот віддано `OPERATED_BY` | R12 |
| 7 | Для рейсу немає зв'язку з авіакомпанією та пунктами маршруту (P4) | Додано `OPERATED_BY` (Flight → Airline); `SERVES` дозволено для суб'єкта `Flight` | розділ 2 |
| 8 | Пункт названо і містом, і аеропортом (Charlotte / CLT) дублює твердження | Лише аеропорт | граничні випадки |
| 9 | Торгівля слотами (P5) — ядро домену, але не є партнерством | `PARTNER_OF` замінено на `AGREEMENT_WITH` з обов'язковим `kind` (codeshare, alliance, risk_sharing, slot_trade, other); для slot_trade покупець → продавець | розділ 2 |
| 10 | Присвійне «'s» і прізвисько всередині імені ламають межі мітки («New York City's», `Chesley "Sully" Sullenberger`) | «'s» поза міткою; прізвисько в імені залишається | R2 |
| 11 | «A year before» без дати в реченні | Розв'язується лише за явною опорною датою в тексті | R11 |

## 9. Використання генеративного ШІ (декларація)

Інструмент: Claude. Призначення: чернетка типів, правил і пілотної розмітки. Приклад запиту: «Побудуй схему витягу для авіадомену за наведеними фрагментами». Перевірка: кожне пілотне твердження звірено з текстом документа автором; правила R1–R10 переглянуто й узгоджено з прикладами корпусу. Журнал — `llm_log/`.