"""
agent/ — LangGraph agent definition, state, and graph wiring.

Kept separate from app/ so the agent is testable without spinning up
a web server, and from tools/ so tool implementations can evolve
independently of graph topology.
"""
