# Примітки до чернетки золотого набору (схема v1.2 не змінювалась)

Чернетка: `data/gold_draft_raw.jsonl` → `data/gold_draft.jsonl` (153 твердження, 24 документи з 26; `validate` — OK).
Усі твердження потребують ручної перевірки автором (чернетка, не фінальний gold).

## Чому менше 170 і менше 5 на деякий документ
Текст корпусу не підтримує більше тверджень без порушення R1. Документи, де їх менше 5:
- D23 (Air traffic control), D24 (Bird strike): 0 — немає жодного відношення між названими сутностями з 10 типів.
- D10 (EASA), D11 (ICAO): по 1 — переважно історія та опис функцій; відношення «агентство ЄК», «агентство ООН» поза схемою.
- D13 (Gimli Glider): 2 — решта (двигуни, борт C-GAUN, комісія) поза схемою.
- D19 (E-Jet E2): 2; D18 (A320neo): 3; D21 (Airport slot): 3; D22 (Codeshare): 2; D26: 2; D06/D07/D15: 4.
- D06: 4, а не 5: «Okęcie neighborhood» можна було б розмітити як LOCATED_IN, але `fill` бере першу позицію «Okęcie» в evidence — це всередині назви «Warsaw Okęcie Airport» (R3), тому твердження пропущено.

## Рішення за неоднозначними місцями (для перевірки)
1. **Регіони в SERVES (D04):** «services to Europe, the Middle East, the United States, Canada, and Asia» розмічено як SERVES → `Location` (5 тверджень, R5). У пілоті ці рядки не розмічались; якщо регіони/континенти не вважати `Location`, ці 5 слід видалити.
2. **Ryanair bases (D02):** «bases at Dublin, London Stansted, and Milan Bergamo» → HUB_AT лише для London Stansted та Milan Bergamo (Airport). «Dublin» — місто, не назва аеропорту в тексті, пропущено.
3. **«focus city» (D08)** Wizz Air Ukraine → HUB_AT (ближче за змістом до «base», ніж до SERVES). Без `time`: 2015-04 — це дата закінчення.
4. **Ланцюг локацій:** Swords (D02), Budapest (D03), Cologne (D10), Quartier international de Montréal (D11), Anchorage/Aurora/Federal Way (D12) — лише перша ланка (граничні випадки).
5. **Модальність у D14:** «was scheduled to fly … with a planned intermediate stop at Charlotte Douglas» — для всіх трьох SERVES поставлено `asserted`, як у пілоті (#22–24). Лише Charlotte сформульовано як «planned stop»; за R9 його можна було б перевести в `planned`.
6. **D13 (Gimli Glider):** заголовок — прізвисько рейсу, тому `implicit_topic` не використовувався (його canonical має збігатись зі slug заголовка «gimli_glider», а правильний canonical — `flight:air_canada_flight_143`, див. aliases.csv). OPERATED_BY не розмічено: «Air Canada» є лише в назві рейсу (R3), прямого твердження «operated by» нема.
7. **D25 (Airworthiness directive):** перелік органів — окремі рядки після «including:». Як evidence використано діапазон від речення «ADs are issued by … including:» до відповідного пункту переліку (≤ 300 символів, але це не одне речення в строгому сенсі, а речення + пункти списку). Якщо evidence має бути строго реченням, ці 6 тверджень слід переглянути.
8. **D08 (Lviv), D09 (Frankfurt):** для LOCATED_IN використано фрагмент речення замість повного, бо в повному першому реченні є транслітерації («"Lviv"», «Flughafen Frankfurt Main»), що ставили б офсет об'єкта на невірне входження. Суб'єкт — implicit_topic. D08 HUB/SERVES для Wizz Air Ukraine та D26 MAGSA теж використовують обрізаний фрагмент речення (≤ 300).
9. **Анафора в INVOLVED_IN (D14, D16, D17):** `AircraftType` («Airbus A320», «Boeing 777») та екіпаж («The crew consisted of …», D17) пов'язано з рейсом через `implicit_topic` — речення прямо не містить назви рейсу. За R4 це дозволено лише для теми документа; тема тут — саме рейс.
10. **D15:** екіпаж KLM (Veldhuyzen van Zanten тощо) не розмічено: «Its cockpit crew» відноситься до KLM Flight 4805, який не є темою документа (тема — Event), а назви рейсу в реченні немає.
11. **D26:** MAGSA та SGHA розмічено як `Regulation` («industry-standard agreement» / «Standard Ground Handling Agreement» трактовано як стандарт); ISSUED_BY — «published by / published in». Це найслабші твердження чернетки.
12. **D01:** `Lufthansa Group` і `Lufthansa Airlines`, `Deutsche Lufthansa AG` зведено до одного canonical `airline:lufthansa` (аліаси); у тексті вони розрізняються як група/авіакомпанія — може знадобитись рішення автора. `Swissair`, `Star Alliance` — `Organization` за схемою.
13. **D04 GPA:** `Guinness Peat Aviation` — лізингова (Organization), як акціонер-засновник розмічено OWNS_STAKE_IN; сам лізинг літаків поза схемою.
14. **Повторні мітки в evidence:** `fill` бере перше входження; для D03-001 (Wizz Air), D04 (Kyiv), D08 Ryanair (береться «talks with Ryanair», а не друге входження), D09 (Lufthansa), D20 (767-200) — це коректний або прийнятний варіант.
