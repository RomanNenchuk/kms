"""Спільна таксономія ЛР 16: теми знань, зв'язок «документ — тема», «роль — тема», «сутність графа — тема».
УВАГА: ці відображення складено вручну (рівень верифікації V1, див. claims/claims.csv) і вони є частиною
синтетичної моделі даних, а не фактом про реальних користувачів."""

TOPICS = [
    "air_traffic_mgmt", "flight_safety", "airport_infrastructure", "ground_ops", "crew_ops",
    "maintenance_fleet", "passenger_rights", "commercial_strategy", "distribution_systems",
    "regulation_bodies", "disruption_mgmt",
]

# doc_id -> теми (1–3) для документів корпусу data/kb/corpus.jsonl
DOC_TOPICS = {
    "en_air_cargo": ["commercial_strategy", "ground_ops"],
    "en_air_operator_s_certificate": ["regulation_bodies", "flight_safety"],
    "en_air_passengers_rights_regulation": ["passenger_rights", "regulation_bodies", "disruption_mgmt"],
    "en_air_traffic_control": ["air_traffic_mgmt", "flight_safety"],
    "en_air_traffic_flow_management": ["air_traffic_mgmt", "disruption_mgmt"],
    "en_air_traffic_management": ["air_traffic_mgmt"],
    "en_aircraft_ground_handling": ["ground_ops", "airport_infrastructure"],
    "en_aircraft_lease": ["maintenance_fleet", "commercial_strategy"],
    "en_aircraft_maintenance": ["maintenance_fleet", "flight_safety"],
    "en_aircrew": ["crew_ops"],
    "en_airline": ["commercial_strategy"],
    "en_airline_alliance": ["commercial_strategy"],
    "en_airline_hub": ["commercial_strategy", "airport_infrastructure"],
    "en_airliner": ["maintenance_fleet"],
    "en_airport": ["airport_infrastructure", "ground_ops"],
    "en_airport_security": ["ground_ops", "regulation_bodies"],
    "en_airport_slot": ["airport_infrastructure", "disruption_mgmt"],
    "en_aviation_safety": ["flight_safety", "regulation_bodies"],
    "en_codeshare_agreement": ["commercial_strategy", "distribution_systems"],
    "en_computer_reservation_system": ["distribution_systems"],
    "en_convention_on_international_civil_aviation": ["regulation_bodies"],
    "en_crew_resource_management": ["crew_ops", "flight_safety"],
    "en_eurocontrol": ["air_traffic_mgmt", "regulation_bodies"],
    "en_flight_cancellation_and_delay": ["disruption_mgmt", "passenger_rights"],
    "en_flight_dispatcher": ["crew_ops", "disruption_mgmt", "flight_safety"],
    "en_global_distribution_system": ["distribution_systems", "commercial_strategy"],
    "en_iata_airport_code": ["distribution_systems", "airport_infrastructure"],
    "en_icao_airport_code": ["airport_infrastructure", "regulation_bodies"],
    "en_international_air_transport_association": ["regulation_bodies", "commercial_strategy"],
    "en_international_civil_aviation_organization": ["regulation_bodies", "flight_safety"],
    "en_low_cost_carrier": ["commercial_strategy"],
    "en_montreal_convention": ["passenger_rights", "regulation_bodies"],
    "en_overselling": ["passenger_rights", "commercial_strategy"],
    "en_revenue_management": ["commercial_strategy", "distribution_systems"],
    "en_runway": ["airport_infrastructure", "flight_safety"],
    "en_warsaw_convention": ["passenger_rights", "regulation_bodies"],
}

ROLES = ["dispatcher", "analyst", "ops_manager", "maintenance_planner", "revenue_manager"]
ROLE_TOPICS = {
    "dispatcher": ["crew_ops", "flight_safety", "disruption_mgmt", "air_traffic_mgmt"],
    "analyst": ["disruption_mgmt", "regulation_bodies", "commercial_strategy", "passenger_rights"],
    "ops_manager": ["ground_ops", "airport_infrastructure", "disruption_mgmt", "crew_ops"],
    "maintenance_planner": ["maintenance_fleet", "flight_safety", "regulation_bodies"],
    "revenue_manager": ["commercial_strategy", "distribution_systems", "passenger_rights"],
}

# тип ризику з графа (risks.csv: kind) -> теми
RISK_KIND_TOPICS = {
    "weather": ["flight_safety", "disruption_mgmt", "air_traffic_mgmt"],
    "technical": ["maintenance_fleet", "flight_safety"],
}
# мітка вузла графа -> теми (для пояснень шляхом)
LABEL_TOPICS = {
    "Airport": ["airport_infrastructure", "ground_ops"],
    "Airline": ["commercial_strategy"],
    "Aircraft": ["maintenance_fleet"],
    "Pilot": ["crew_ops"],
    "Passenger": ["passenger_rights"],
    "Delay": ["disruption_mgmt"],
}
