# Приклади пояснень (5 рекомендацій)

Джерело: Gemini (перефразування) + автоперевірка. Згенеровано `python -m reco.explain --llm`.

## Приклад 1: U001 → Air traffic control
- Компонента шляху: `role`
- Шлях: `User:U001 → Role:dispatcher → Topic:flight_safety → Doc:en_air_traffic_control`
- Пояснення (llm): Рекомендовано «Air traffic control»: ваша роль «диспетчер» пов'язана з темою «безпека польотів», якій присвячено цей документ.
- Автоперевірка: пройдена 
- Сирий вихід LLM: Рекомендовано «Air traffic control»: ваша роль «диспетчер» пов'язана з темою «безпека польотів», якій присвячено цей документ.

## Приклад 2: U001 → Convention on International Civil Aviation
- Компонента шляху: `history`
- Шлях: `User:U001 → Doc:en_air_passengers_rights_regulation → Topic:regulation_bodies → Doc:en_convention_on_international_civil_aviation`
- Пояснення (template_fallback): Рекомендовано «Convention on International Civil Aviation»: ви відкривали «Air Passengers Rights Regulation» на тему «регулювання та міжнародні організації», якій присвячено і цей документ.
- Автоперевірка: НЕ пройдена {"ok": false, "unknown_quoted": ["Air PassengersRights Regulation"], "foreign": [], "foreign_numbers": [], "missing": []}
- Сирий вихід LLM: Рекомендовано «Convention on International Civil Aviation», оскільки ви відкривали «Air PassengersRights Regulation» на тему «регулювання та міжнародні організації», якій присвячено і цей документ.

## Приклад 3: U003 → Aircraft maintenance
- Компонента шляху: `exposure`
- Шлях: `User:U003 → Airline:BC → Flight:BC101-20261103 → Risk:RK06 (Fog at Riga) → Topic:flight_safety → Doc:en_aircraft_maintenance`
- Пояснення (llm): Рекомендовано «Aircraft maintenance» через те, що рейси авіакомпанії «BaltiCair» (наприклад, «BC101-20261103») зазнали ризику «Fog at Riga», а тема «безпека польотів», якій присвячено документ, стосується таких ризиків.
- Автоперевірка: пройдена 
- Сирий вихід LLM: Рекомендовано «Aircraft maintenance» через те, що рейси авіакомпанії «BaltiCair» (наприклад, «BC101-20261103») зазнали ризику «Fog at Riga», а тема «безпека польотів», якій присвячено документ, стосується таких ризиків.

## Приклад 4: U001 → Air traffic control
- Компонента шляху: `embed`
- Шлях: `embed: en_international_civil_aviation_organization ~ en_air_traffic_control`
- Пояснення (llm): Рекомендовано «Air traffic control», оскільки цей документ має високу схожість із «International Civil Aviation Organization» з вашої історії.
- Автоперевірка: пройдена 
- Сирий вихід LLM: Рекомендовано «Air traffic control», оскільки цей документ має високу схожість із «International Civil Aviation Organization» з вашої історії.

## Приклад 5: U011 → Airliner
- Компонента шляху: `exposure`
- Шлях: `User:U011 → Airline:EN → Flight:EN102-20261102 → Risk:RK10 (Engine sensor warning) → Topic:maintenance_fleet → Doc:en_airliner`
- Пояснення (llm): Рекомендовано «Airliner»: рейси авіакомпанії «EuroNord» (наприклад, «EN102-20261102») зазнали ризику «Engine sensor warning», а тема «технічне обслуговування та парк літаків», якій присвячено документ, стосується таких ризиків.
- Автоперевірка: пройдена 
- Сирий вихід LLM: Рекомендовано «Airliner»: рейси авіакомпанії «EuroNord» (наприклад, «EN102-20261102») зазнали ризику «Engine sensor warning», а тема «технічне обслуговування та парк літаків», якій присвячено документ, стосується таких ризиків.
