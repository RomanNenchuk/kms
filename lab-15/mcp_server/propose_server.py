"""Окремий MCP-сервер ЗАПИСУ з єдиним інструментом propose_fact (принцип найменших привілеїв).
Основний сервер (mcp_server.server) лишається суто читальним і не змінюється. Схвалити пропозицію цей сервер НЕ може:
схвалення робить людина окремо (python -m agent.propose_fact interactive)."""
from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from agent import propose_fact as pf

mcp = FastMCP("aviation-proposals")


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False))
def propose_fact(fact: dict) -> dict:
    """Запропонувати нове знання для сховища (не запис!). Обов'язкові поля: action (add_relation | add_risk | update_property),
    відповідні дані (relation | risk | update) і source {type: kb|graph|url|operator, ref, quote}. Пропозиція проходить політику,
    перевірку джерела, SHACL і оцінку ризику. Низький ризик із перевіреним джерелом записується автоматично; середній і високий
    чекають схвалення людини. Видалення й зміна обмежених даних заборонені. Результат: proposal_id, status, risk."""
    return pf.propose(fact, proposer="agent")


if __name__ == "__main__":
    mcp.run()
