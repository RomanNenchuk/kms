# Джерела даних

Корпус — фрагменти (до ~4000 символів) статей **англійської Вікіпедії** за темою «управління авіаційними перевезеннями».
Завантажується скриптом `src/fetch_corpus.py` через MediaWiki API; кожен документ закріплений за номером версії (`revid`),
permalink із `oldid` записано в `data/sources.csv`. Відтворення: `python src/fetch_corpus.py --pinned`.

| Тип | Приклади |
|---|---|
| airline | Lufthansa, Ryanair, Wizz Air, Ukraine International Airlines |
| airport | Warsaw Chopin, Vienna, Lviv, Frankfurt |
| regulator | EASA, ICAO, NTSB |
| accident | Gimli Glider, US Airways Flight 1549, Tenerife, Germanwings 9525 |
| aircraft | A320neo family, E-Jet E2 family, Boeing 767 |
| concept | Airport slot, Codeshare, Air traffic control, Bird strike, Airworthiness directive… |

**Ліцензія:** CC BY-SA 4.0 — у звіті вкажіть Вікіпедію як джерело з посиланнями з `sources.csv`.
Персональних даних немає (статті про організації та події).

**Відомі упередження (для `gold_card.md`):** єдиний вебресурс і енциклопедичний стиль (немає NOTAM, звітів ТО чи новин);
перекіс до великих європейських гравців і відомих інцидентів; фрагмент — лише початок статті; Вікіпедія могла потрапити в
навчальні дані LLM, тому метод Б може «пригадувати» факти без опори на текст — саме тому важлива вимога evidence/цитати.
Для більшої різноманітності можна додати 3–5 документів з інших джерел (прес-релізи, звіти розслідувань) вручну в `data/raw/`
і внести їх у `sources.csv`.
