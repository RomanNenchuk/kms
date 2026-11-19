# Аналіз розбіжностей моделей


## 1. q23 (keyword), сценарій `en->en`

**Запит:** legacy carriers US airline deregulation act

**Золотий доказ:** _Legacy carriers, US carriers that predate the Airline Deregulation Act of 1978._ (Airline › Types)


| модель | ранг золотого | найкращий знайдений фрагмент |
|---|---|---|
| e5-small-multi | 1 | Airline › Types |
| minilm-multi | 97 | International Air Transport Association › Illegal rebates |
| minilm-en | 2 | Airline › Deregulation |

**Причини:** обрізання довгого фрагмента (доказ за межею max_seq_length); схожий фрагмент з іншої статті чи розділу «перебив» золотий

**Пояснення:** Моделі дали різні результати (e5-small-multi — ранг 1, minilm-multi — ранг 97, minilm-en — ранг 2). Імовірні причини: речення-доказ лежить у «хвості» фрагмента, який модель через ліміт max_seq_length не бачить; модель знайшла тематично близький фрагмент з іншої статті чи розділу. Доказ стоїть в кінці довгого фрагмента, за межею 128 токенів minilm-multi, тому вона його не бачить і обирає схожий фрагмент про IATA (ранг 97).


## 2. q17 (paraphrase), сценарій `en->en`

**Запит:** What is the typical passenger capacity for regional airliners?

**Золотий доказ:** _Regional airliners typically seat fewer than 100 passengers and may be powered by turbofans or turboprops._ (Airliner › Airliner)


| модель | ранг золотого | найкращий знайдений фрагмент |
|---|---|---|
| e5-small-multi | 5 | Airliner › Regional aircraft |
| minilm-multi | 79 | Airliner › Regional aircraft |
| minilm-en | 7 | Airline › Economy |

**Причини:** синоніми / перефразування (запит і доказ різними словами); обрізання довгого фрагмента (доказ за межею max_seq_length); схожий фрагмент з іншої статті чи розділу «перебив» золотий

**Пояснення:** Моделі дали різні результати (e5-small-multi — ранг 5, minilm-multi — ранг 79, minilm-en — ранг 7). Імовірні причини: запит і речення-доказ описують те саме різними словами, тож потрібне семантичне, а не лексичне зіставлення; речення-доказ лежить у «хвості» фрагмента, який модель через ліміт max_seq_length не бачить; модель знайшла тематично близький фрагмент з іншої статті чи розділу. Золотий фрагмент «Airliner › Airliner» програв сусідньому розділу «Regional aircraft», який майже дослівно повторює доказ (e5 ранг 5, minilm-en взяла стороннє з «Airline › Economy»). minilm-multi (ранг 79) до того ж обрізала доказ за межею 128 токенів, а запит про «capacity» лише перефразовує «seat fewer than 100».


## 3. q02 (paraphrase), сценарій `en->en`

**Запит:** Why do Delta Air Lines and American Airlines use LaGuardia Airport as a hub in New York City?

**Золотий доказ:** _Delta Air Lines' and American Airlines' uses of LaGuardia Airport as a domestic hub in New York City, due to capacity and slot restrictions at their hubs at John F. Kennedy International Airport._ (Airline hub › Reliever hub)


| модель | ранг золотого | найкращий знайдений фрагмент |
|---|---|---|
| e5-small-multi | 1 | Airline hub › Reliever hub |
| minilm-multi | 56 | Airline › Assets and financing |
| minilm-en | 1 | Airline hub › Reliever hub |

**Причини:** обрізання довгого фрагмента (доказ за межею max_seq_length); схожий фрагмент з іншої статті чи розділу «перебив» золотий

**Пояснення:** Моделі дали різні результати (e5-small-multi — ранг 1, minilm-multi — ранг 56, minilm-en — ранг 1). Імовірні причини: речення-доказ лежить у «хвості» фрагмента, який модель через ліміт max_seq_length не бачить; модель знайшла тематично близький фрагмент з іншої статті чи розділу. minilm-multi не побачила кінець доказу (причину «capacity and slot restrictions») і взяла схожий за темою фрагмент про перевантажені аеропорти з іншої статті, а e5 і minilm-en знайшли золотий одразу.


## 4. q16 (paraphrase), сценарій `en->en`

**Запит:** Are helicopter flights covered under the air passengers rights regulation?

**Золотий доказ:** _It does not apply to helicopter flights, to any flight not operated by a fixed-wing aircraft, nor to flights from Gibraltar Airport._ (Air Passengers Rights Regulation › Applicability)


| модель | ранг золотого | найкращий знайдений фрагмент |
|---|---|---|
| e5-small-multi | 1 | Air Passengers Rights Regulation › Applicability |
| minilm-multi | 31 | Airline › International |
| minilm-en | 1 | Air Passengers Rights Regulation › Applicability |

**Причини:** синоніми / перефразування (запит і доказ різними словами); обрізання довгого фрагмента (доказ за межею max_seq_length); схожий фрагмент з іншої статті чи розділу «перебив» золотий

**Пояснення:** Моделі дали різні результати (e5-small-multi — ранг 1, minilm-multi — ранг 31, minilm-en — ранг 1). Імовірні причини: запит і речення-доказ описують те саме різними словами, тож потрібне семантичне, а не лексичне зіставлення; речення-доказ лежить у «хвості» фрагмента, який модель через ліміт max_seq_length не бачить; модель знайшла тематично близький фрагмент з іншої статті чи розділу. minilm-multi не побачила кінець фрагмента, де згадано гелікоптери, і взяла схожий за темою фрагмент про авіаційні правила з іншої статті, а e5 і minilm-en знайшли золотий одразу.


## 5. q15 (paraphrase), сценарій `uk->en`

**Запит:** Чи забороняє Чиказька конвенція оподаткування авіаційного палива, що використовується на внутрішніх рейсах?

**Золотий доказ:** _The Chicago Convention does not preclude a kerosene tax on domestic flights and on refueling before international flights._ (Convention on International Civil Aviation › Kerosene tax)


| модель | ранг золотого | найкращий знайдений фрагмент |
|---|---|---|
| e5-small-multi | 1 | Convention on International Civil Aviation › Kerosene tax |
| minilm-multi | 1 | Convention on International Civil Aviation › Kerosene tax |
| minilm-en | 782 | Aircraft ground handling › Russia |

**Причини:** мова запиту: англомовна модель не розуміє українських слів; схожий фрагмент з іншої статті чи розділу «перебив» золотий

**Пояснення:** Моделі дали різні результати (e5-small-multi — ранг 1, minilm-multi — ранг 1, minilm-en — ранг 782). Імовірні причини: запит українською, а модель навчена лише на англійській; модель знайшла тематично близький фрагмент з іншої статті чи розділу. minilm-en не розуміє українського запиту й видає випадковий фрагмент з іншої статті (ранг 782), а обидві багатомовні моделі знайшли золотий одразу. Доказ закінчується на позиції 544, лише трохи за межею, тож обрізання (4) тут не завадило.


## 6. q26 (keyword), сценарій `uk->en`

**Запит:** рейс 679 Thai Airways виїзд за межі злітно-посадкової смуги

**Золотий доказ:** _Runway excursion – an incident involving only a single aircraft, where it makes an inappropriate exit from the runway (e.g. Thai Airways Flight 679)._ (Runway › Safety)


| модель | ранг золотого | найкращий знайдений фрагмент |
|---|---|---|
| e5-small-multi | 3 | Air traffic control › Air navigation service providers (ANSPs) and air traffic service providers (ATSPs) |
| minilm-multi | 42 | Low-cost carrier › History |
| minilm-en | 505 | Air traffic control › Air navigation service providers (ANSPs) and air traffic service providers (ATSPs) |

**Причини:** мова запиту: англомовна модель не розуміє українських слів; абревіатури й власні назви (ICAO, IATA, CRS, Thai Airways…); схожий фрагмент з іншої статті чи розділу «перебив» золотий; точні числа, дати, назви (21 minutes, 2002…)

**Пояснення:** Моделі дали різні результати (e5-small-multi — ранг 3, minilm-multi — ранг 42, minilm-en — ранг 505). Імовірні причини: запит українською, а модель навчена лише на англійській; у запиті є абревіатури або власні назви, які модель по-різному обробляє; модель знайшла тематично близький фрагмент з іншої статті чи розділу; відповідь — точний факт (число, дата), який слабо відображається в загальному змісті фрагмента. українська частина запиту («виїзд за межі смуги») не зіставляється з «runway excursion», тому моделі чіпляються за «Thai Airways» і підсовують переліки авіакомпаній з інших статей (e5 лише ранг 3, minilm-en ранг 505).


## 7. q10 (paraphrase), сценарій `uk->en`

**Запит:** Які авіаційні інженери відповідають за сертифікацію повітряних суден для польотів та управління технічним обслуговуванням?

**Золотий доказ:** _Groundcrew, responsible for operations at airports, include Aerospace and avionics engineers responsible for certifying the aircraft for flight and management of aircraft maintenance_ (Airline › Personnel)


| модель | ранг золотого | найкращий знайдений фрагмент |
|---|---|---|
| e5-small-multi | 1 | Airline › Personnel |
| minilm-multi | 6 | Aircrew › Military |
| minilm-en | 449 | Aircraft ground handling › Russia |

**Причини:** мова запиту: англомовна модель не розуміє українських слів; синоніми / перефразування (запит і доказ різними словами); обрізання довгого фрагмента (доказ за межею max_seq_length); схожий фрагмент з іншої статті чи розділу «перебив» золотий

**Пояснення:** Моделі дали різні результати (e5-small-multi — ранг 1, minilm-multi — ранг 6, minilm-en — ранг 449). Імовірні причини: запит українською, а модель навчена лише на англійській; запит і речення-доказ описують те саме різними словами, тож потрібне семантичне, а не лексичне зіставлення; речення-доказ лежить у «хвості» фрагмента, який модель через ліміт max_seq_length не бачить; модель знайшла тематично близький фрагмент з іншої статті чи розділу. minilm-en не розуміє українського запиту (ранг 449), а minilm-multi бачить лише початок фрагмента й бере схожий за темою фрагмент про обслуговування літаків з іншої статті (ранг 6). e5 знайшла золотий одразу.
