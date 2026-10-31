// Крок 4. Демонстрація порушення обмеження. Очікується помилка
// Neo.ClientError.Schema.ConstraintValidationFailed: Node(...) already exists with label `Airport` and property `iata` = 'LWO'
// Виконувати ОКРЕМО (cypher-shell зупиняється на помилці) — зробіть скріншот повідомлення.
CREATE (:Airport {iata: 'LWO', name: 'Duplicate Lviv'});
