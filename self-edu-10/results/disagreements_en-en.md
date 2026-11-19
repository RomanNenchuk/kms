# Розбіжності моделей (сценарій `en->en`)

Відібрано 8 запитів: спершу ті, де одна модель має золотий фрагмент у top-5, а інша ні; далі за розкидом рангів. Ранг — позиція першого релевантного фрагмента серед 795.


## 1. q23 (keyword): legacy carriers US airline deregulation act

Доказ: _Legacy carriers, US carriers that predate the Airline Deregulation Act of 1978._ — en_airline


| модель | ранг золотого | top-5 | top-3 знайдено |
|---|---|---|---|
| e5-small-multi | 1 | ✓ | Airline › Types; Airline › Deregulation; Airline › Deregulation |
| minilm-multi | 97 | ✗ | International Air Transport Association › Illegal rebates; Airline › Deregulation; Airline › Deregulation |
| minilm-en | 2 | ✓ | Airline › Deregulation; Airline › Types; Airline › State support |
| hashing-baseline | 1 | ✓ | Airline › Types; Airline › Deregulation; Airline › National |


**Пояснення (заповни вручну):** _чому розійшлися? мова запиту / назви й абревіатури / синоніми / довгий фрагмент і обрізання / близький фрагмент з іншої статті / префікси…_


## 2. q17 (paraphrase): What is the typical passenger capacity for regional airliners?

Доказ: _Regional airliners typically seat fewer than 100 passengers and may be powered by turbofans or turboprops._ — en_airliner


| модель | ранг золотого | top-5 | top-3 знайдено |
|---|---|---|---|
| e5-small-multi | 5 | ✓ | Airliner › Regional aircraft; Airliner › Airliner; Airline › Economy |
| minilm-multi | 79 | ✗ | Airliner › Regional aircraft; Airline › Economy; Airliner › Fleet |
| minilm-en | 7 | ✗ | Airline › Economy; Airliner › Fleet; Airliner › Regional aircraft |
| hashing-baseline | 2 | ✓ | Airline › Types; Airliner › Airliner; Airliner › Airliner |


**Пояснення (заповни вручну):** _чому розійшлися? мова запиту / назви й абревіатури / синоніми / довгий фрагмент і обрізання / близький фрагмент з іншої статті / префікси…_


## 3. q02 (paraphrase): Why do Delta Air Lines and American Airlines use LaGuardia Airport as a hub in New York City?

Доказ: _Delta Air Lines' and American Airlines' uses of LaGuardia Airport as a domestic hub in New York City, due to capacity and slot restrictions at their hubs at John F. Kennedy International Airport._ — en_airline_hub


| модель | ранг золотого | top-5 | top-3 знайдено |
|---|---|---|---|
| e5-small-multi | 1 | ✓ | Airline hub › Reliever hub; Airline hub › Airline hub; Airline hub › Fortress hub |
| minilm-multi | 56 | ✗ | Airline › Assets and financing; Airline hub › Moonlight hub; Airline hub › Fortress hub |
| minilm-en | 1 | ✓ | Airline hub › Reliever hub; Airline hub › Fortress hub; Airline › Assets and financing |
| hashing-baseline | 1 | ✓ | Airline hub › Reliever hub; Flight cancellation and delay › Performances; Airline hub › Fortress hub |


**Пояснення (заповни вручну):** _чому розійшлися? мова запиту / назви й абревіатури / синоніми / довгий фрагмент і обрізання / близький фрагмент з іншої статті / префікси…_


## 4. q06 (paraphrase): How do budget airlines compensate for the revenue lost due to lower ticket prices?

Доказ: _To make up for revenue lost in decreased ticket prices, the airline may charge extra fees, such as for carry-on baggage._ — en_low_cost_carrier


| модель | ранг золотого | top-5 | top-3 знайдено |
|---|---|---|---|
| e5-small-multi | 8 | ✗ | Airline › Deregulation; Low-cost carrier › Simplicity; Low-cost carrier › Pricing policy |
| minilm-multi | 40 | ✗ | Low-cost carrier › Limit personnel costs; Low-cost carrier › Simplicity; Overselling › Airlines |
| minilm-en | 9 | ✗ | Low-cost carrier › Pricing policy; Airline › National; Airline › Revenue |
| hashing-baseline | 1 | ✓ | Low-cost carrier › Low-cost carrier; Air Passengers Rights Regulation › Intermediaries; Airline › Deregulation |


**Пояснення (заповни вручну):** _чому розійшлися? мова запиту / назви й абревіатури / синоніми / довгий фрагмент і обрізання / близький фрагмент з іншої статті / префікси…_


## 5. q16 (paraphrase): Are helicopter flights covered under the air passengers rights regulation?

Доказ: _It does not apply to helicopter flights, to any flight not operated by a fixed-wing aircraft, nor to flights from Gibraltar Airport._ — en_air_passengers_rights_regulation


| модель | ранг золотого | top-5 | top-3 знайдено |
|---|---|---|---|
| e5-small-multi | 1 | ✓ | Air Passengers Rights Regulation › Applicability; Air Passengers Rights Regulation › Relevant court cases; Air Passengers Rights Regulation › Air Passengers Rights Regulation |
| minilm-multi | 31 | ✗ | Airline › International; Aircraft maintenance › Regulation; Airport slot › Airport slot |
| minilm-en | 1 | ✓ | Air Passengers Rights Regulation › Applicability; Air Passengers Rights Regulation › Brexit and British consumers; Air Passengers Rights Regulation › Air Passengers Rights Regulation |
| hashing-baseline | 9 | ✗ | Flight cancellation and delay › Compensation; Flight cancellation and delay › European Union; Air Passengers Rights Regulation › Brexit and British consumers |


**Пояснення (заповни вручну):** _чому розійшлися? мова запиту / назви й абревіатури / синоніми / довгий фрагмент і обрізання / близький фрагмент з іншої статті / префікси…_


## 6. q32 (multistep): Where is the IATA headquarters that administers airport code assignments, and in what city was the 2013 annual general meeting held where members endorsed the Aviation Carbon-Neutral Growth strategy?

Доказ: _At the 2013 IATA annual general meeting in Cape Town, South Africa, members overwhelmingly endorsed a resolution on "Implementation of the Aviation Carbon-Neutral Growth (CNG2020) Strategy."_ — en_international_air_transport_association


| модель | ранг золотого | top-5 | top-3 знайдено |
|---|---|---|---|
| e5-small-multi | 1 | ✓ | IATA airport code › IATA airport code; International Air Transport Association › International Air Transport Association; Airport slot › Airport slot |
| minilm-multi | 19 | ✗ | International Air Transport Association › History; Convention on International Civil Aviation › Convention on International Civil Aviation; Air traffic control › History |
| minilm-en | 1 | ✓ | International Air Transport Association › Environment; International Air Transport Association › History; IATA airport code › IATA airport code |
| hashing-baseline | 1 | ✓ | International Air Transport Association › Environment; IATA airport code › IATA airport code; Airport slot › Airport slot |


**Пояснення (заповни вручну):** _чому розійшлися? мова запиту / назви й абревіатури / синоніми / довгий фрагмент і обрізання / близький фрагмент з іншої статті / префікси…_


## 7. q30 (multistep): How is the flight distance used for compensation determined under the Air Passengers Rights Regulation, and which kind of seismic events are given as examples of causes of flight disruption?

Доказ: _The requirements for an entitlement to compensation and the specific amount owed depend on the length of a flight, whereas the relevant distance is determined according to the great circle method._ — en_air_passengers_rights_regulation


| модель | ранг золотого | top-5 | top-3 знайдено |
|---|---|---|---|
| e5-small-multi | 1 | ✓ | Air Passengers Rights Regulation › Flight types; Air Passengers Rights Regulation › Relevant court cases; Air Passengers Rights Regulation › Air Passengers Rights Regulation |
| minilm-multi | 2 | ✓ | Air Passengers Rights Regulation › Relevant court cases; Air Passengers Rights Regulation › Flight types; Flight cancellation and delay › United States |
| minilm-en | 1 | ✓ | Air Passengers Rights Regulation › Flight types; Air Passengers Rights Regulation › Recent Developments; Air Passengers Rights Regulation › Relevant court cases |
| hashing-baseline | 19 | ✗ | Air Passengers Rights Regulation › Air Passengers Rights Regulation; Air Passengers Rights Regulation › Relevant court cases; Air Passengers Rights Regulation › Recent Developments |


**Пояснення (заповни вручну):** _чому розійшлися? мова запиту / назви й абревіатури / синоніми / довгий фрагмент і обрізання / близький фрагмент з іншої статті / префікси…_


## 8. q21 (keyword): IATA Resolution 763 airport codes

Доказ: _The assignment of these codes is governed by IATA Resolution 763, and it is administered by the IATA's headquarters in Montreal, Canada._ — en_iata_airport_code


| модель | ранг золотого | top-5 | top-3 знайдено |
|---|---|---|---|
| e5-small-multi | 1 | ✓ | IATA airport code › IATA airport code; International Civil Aviation Organization › Aircraft type designators; ICAO airport code › ICAO airport code |
| minilm-multi | 13 | ✗ | IATA airport code › Airports without codes; International Civil Aviation Organization › Airport codes; IATA airport code › Scarcity of codes |
| minilm-en | 1 | ✓ | IATA airport code › IATA airport code; ICAO airport code › Structure; IATA airport code › Cities with multiple commercial airports |
| hashing-baseline | 1 | ✓ | IATA airport code › IATA airport code; ICAO airport code › Structure; International Civil Aviation Organization › Airport codes |


**Пояснення (заповни вручну):** _чому розійшлися? мова запиту / назви й абревіатури / синоніми / довгий фрагмент і обрізання / близький фрагмент з іншої статті / префікси…_
