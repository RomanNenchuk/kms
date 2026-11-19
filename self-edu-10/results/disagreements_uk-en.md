# Розбіжності моделей (сценарій `uk->en`)

Відібрано 8 запитів: спершу ті, де одна модель має золотий фрагмент у top-5, а інша ні; далі за розкидом рангів. Ранг — позиція першого релевантного фрагмента серед 795.


## 1. q15 (paraphrase): Чи забороняє Чиказька конвенція оподаткування авіаційного палива, що використовується на внутрішніх рейсах?

Доказ: _The Chicago Convention does not preclude a kerosene tax on domestic flights and on refueling before international flights._ — en_convention_on_international_civil_aviation


| модель | ранг золотого | top-5 | top-3 знайдено |
|---|---|---|---|
| e5-small-multi | 1 | ✓ | Convention on International Civil Aviation › Kerosene tax; Convention on International Civil Aviation › Convention on International Civil Aviation; Air traffic control › Air navigation service providers (ANSPs) and air traffic service providers (ATSPs) |
| minilm-multi | 1 | ✓ | Convention on International Civil Aviation › Kerosene tax; International Civil Aviation Organization › Environment; Convention on International Civil Aviation › Convention on International Civil Aviation |
| minilm-en | 782 | ✗ | Aircraft ground handling › Russia; IATA airport code › Cities or airports changing names; IATA airport code › Cities or airports changing names |
| hashing-baseline | 290 | ✗ | Airline › Deregulation; Revenue management › History; Revenue management › History |


**Пояснення (заповни вручну):** _чому розійшлися? мова запиту / назви й абревіатури / синоніми / довгий фрагмент і обрізання / близький фрагмент з іншої статті / префікси…_


## 2. q04 (paraphrase): Які типи компаній зазвичай використовують бронювання без повернення коштів для обмеження овербукінгу?

Доказ: _This can be done by making reservations non-refundable, a common practice among low-cost carriers and railways_ — en_overselling


| модель | ранг золотого | top-5 | top-3 знайдено |
|---|---|---|---|
| e5-small-multi | 23 | ✗ | Overselling › Overselling; Overselling › Airlines; Overselling › Rail |
| minilm-multi | 1 | ✓ | Overselling › Overselling; Overselling › Tourism industry; Low-cost carrier › Limit personnel costs |
| minilm-en | 266 | ✗ | IATA airport code › Cities or airports changing names; Air cargo › World War II; IATA airport code › Cities or airports changing names |
| hashing-baseline | 748 | ✗ | Airline › Trends; Revenue management › History; IATA airport code › Cities or airports changing names |


**Пояснення (заповни вручну):** _чому розійшлися? мова запиту / назви й абревіатури / синоніми / довгий фрагмент і обрізання / близький фрагмент з іншої статті / префікси…_


## 3. q19 (paraphrase): Яка альтернативна назва дозволу на випуск в експлуатацію в повітряному транспорті?

Доказ: _A maintenance release is sometimes called a certificate of release to service (CRS)._ — en_aircraft_maintenance


| модель | ранг золотого | top-5 | top-3 знайдено |
|---|---|---|---|
| e5-small-multi | 4 | ✓ | Air traffic control › Air navigation service providers (ANSPs) and air traffic service providers (ATSPs); Air traffic control › Air navigation service providers (ANSPs) and air traffic service providers (ATSPs); Air traffic control › Air traffic control |
| minilm-multi | 178 | ✗ | Codeshare agreement › Terminology; Airline › International; Air traffic control › Proposed changes |
| minilm-en | 241 | ✗ | IATA airport code › Cities or airports changing names; Aircraft ground handling › Russia; IATA airport code › Cities or airports changing names |
| hashing-baseline | 593 | ✗ | Low-cost carrier › History; Revenue management › History; Airport › Terminology |


**Пояснення (заповни вручну):** _чому розійшлися? мова запиту / назви й абревіатури / синоніми / довгий фрагмент і обрізання / близький фрагмент з іншої статті / префікси…_


## 4. q08 (paraphrase): Яка середня тривалість польоту, що обслуговується Маастрихтським центром управління верхнім повітряним рухом?

Доказ: _The average flight duration is approximately 21 minutes_ — en_eurocontrol


| модель | ранг золотого | top-5 | top-3 знайдено |
|---|---|---|---|
| e5-small-multi | 2 | ✓ | Eurocontrol › Maastricht Upper Area Control Centre; Eurocontrol › Maastricht Upper Area Control Centre; Airline › Expansion |
| minilm-multi | 1 | ✓ | Eurocontrol › Maastricht Upper Area Control Centre; Air traffic flow management › Operation in Europe; Eurocontrol › Maastricht Upper Area Control Centre |
| minilm-en | 198 | ✗ | Aircraft ground handling › Russia; IATA airport code › Cities or airports changing names; Warsaw Convention › Content |
| hashing-baseline | 511 | ✗ | IATA airport code › Naming conventions in general; Revenue management › History; International Civil Aviation Organization › Investigations of air disasters |


**Пояснення (заповни вручну):** _чому розійшлися? мова запиту / назви й абревіатури / синоніми / довгий фрагмент і обрізання / близький фрагмент з іншої статті / префікси…_


## 5. q26 (keyword): рейс 679 Thai Airways виїзд за межі злітно-посадкової смуги

Доказ: _Runway excursion – an incident involving only a single aircraft, where it makes an inappropriate exit from the runway (e.g. Thai Airways Flight 679)._ — en_runway


| модель | ранг золотого | top-5 | top-3 знайдено |
|---|---|---|---|
| e5-small-multi | 3 | ✓ | Air traffic control › Air navigation service providers (ANSPs) and air traffic service providers (ATSPs); Aviation safety › National investigation organizations; Runway › Safety |
| minilm-multi | 42 | ✗ | Low-cost carrier › History; Airliner › Airliner; Crew resource management › United Airlines Flight 173 |
| minilm-en | 505 | ✗ | Air traffic control › Air navigation service providers (ANSPs) and air traffic service providers (ATSPs); Airline hub › Fortress hub; Airline › Asia |
| hashing-baseline | 16 | ✗ | Airline hub › Middle East; Low-cost carrier › History; Airliner › Interwar period |


**Пояснення (заповни вручну):** _чому розійшлися? мова запиту / назви й абревіатури / синоніми / довгий фрагмент і обрізання / близький фрагмент з іншої статті / префікси…_


## 6. q10 (paraphrase): Які авіаційні інженери відповідають за сертифікацію повітряних суден для польотів та управління технічним обслуговуванням?

Доказ: _Groundcrew, responsible for operations at airports, include Aerospace and avionics engineers responsible for certifying the aircraft for flight and management of aircraft maintenance_ — en_airline


| модель | ранг золотого | top-5 | top-3 знайдено |
|---|---|---|---|
| e5-small-multi | 1 | ✓ | Airline › Personnel; Aircrew › Military; Aircraft maintenance › Maintenance personnel |
| minilm-multi | 6 | ✗ | Aircrew › Military; Flight dispatcher › Licensing and certification; Aircraft maintenance › Regulation |
| minilm-en | 449 | ✗ | Aircraft ground handling › Russia; Airliner › USSR; Airport security › India |
| hashing-baseline | 190 | ✗ | Airport security › Process and equipment; Airport › Safety management; Runway › Naming |


**Пояснення (заповни вручну):** _чому розійшлися? мова запиту / назви й абревіатури / синоніми / довгий фрагмент і обрізання / близький фрагмент з іншої статті / префікси…_


## 7. q14 (paraphrase): Коли європейське законодавство вперше зобов'язало проводити перевірки безпеки на внутрішніх пасажирських рейсах?

Доказ: _The regulation no 2320/2002 from 2002 introduced the requirement to have security checks for all passenger flights, also domestic._ — en_airport_security


| модель | ранг золотого | top-5 | top-3 знайдено |
|---|---|---|---|
| e5-small-multi | 1 | ✓ | Airport security › European Union; Air Passengers Rights Regulation › Air Passengers Rights Regulation; Eurocontrol › History |
| minilm-multi | 2 | ✓ | Airport security › United States; Airport security › European Union; Air Passengers Rights Regulation › 2013 Proposal |
| minilm-en | 384 | ✗ | IATA airport code › Cities or airports changing names; Aircraft ground handling › Russia; IATA airport code › Cities or airports changing names |
| hashing-baseline | 442 | ✗ | Airline › Deregulation; Revenue management › History; Crew resource management › Adoption of CRM |


**Пояснення (заповни вручну):** _чому розійшлися? мова запиту / назви й абревіатури / синоніми / довгий фрагмент і обрізання / близький фрагмент з іншої статті / префікси…_


## 8. q16 (paraphrase): Чи поширюються правила щодо прав авіапасажирів на польоти гелікоптерів?

Доказ: _It does not apply to helicopter flights, to any flight not operated by a fixed-wing aircraft, nor to flights from Gibraltar Airport._ — en_air_passengers_rights_regulation


| модель | ранг золотого | top-5 | top-3 знайдено |
|---|---|---|---|
| e5-small-multi | 4 | ✓ | Air Passengers Rights Regulation › 2013 Proposal; Air Passengers Rights Regulation › 2013 Proposal; Airport security › Description |
| minilm-multi | 18 | ✗ | Airline › International; Flight dispatcher › Licensing and certification; Convention on International Civil Aviation › Main articles |
| minilm-en | 430 | ✗ | IATA airport code › Cities or airports changing names; Aircraft ground handling › Russia; Airport security › Finland |
| hashing-baseline | 141 | ✗ | Airline › Revenue; IATA airport code › Cities with multiple commercial airports; Low-cost carrier › Criticism |


**Пояснення (заповни вручну):** _чому розійшлися? мова запиту / назви й абревіатури / синоніми / довгий фрагмент і обрізання / близький фрагмент з іншої статті / префікси…_
