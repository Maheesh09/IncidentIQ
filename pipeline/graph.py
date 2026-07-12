# pipeline/graph.py
from __future__ import annotations

import logging

from langgraph.graph import StateGraph, END

from agents.triage import triage_node
from agents.log_analysis import analyze_logs_node
from agents.deploy_correlation import correlate_deploys_node
from agents.synthesis import synthesize_node
from agents.report import generate_report_node
from pipeline.state import IncidentState

logger = logging.getLogger(__name__)


def build_graph() -> StateGraph:
    """Build and compile the IncidentIQ LangGraph pipeline.

    Wires all five agents into a graph with parallel fan-out
    from triage to log analysis and deploy correlation, then
    fan-in to synthesis before the final report.

    Returns:
        A compiled LangGraph StateGraph ready for invocation.
    """
    graph = StateGraph(IncidentState)

    # Register all agent nodes
    graph.add_node("triage", triage_node)
    graph.add_node("analyze_logs", analyze_logs_node)
    graph.add_node("correlate_deploys", correlate_deploys_node)
    graph.add_node("synthesize", synthesize_node)
    graph.add_node("generate_report", generate_report_node)

    # Set the entry point — triage always runs first
    graph.set_entry_point("triage")

    # Fan-out — triage finishes, then both agents run in parallel
    graph.add_edge("triage", "analyze_logs")
    graph.add_edge("triage", "correlate_deploys")

    # Fan-in — both parallel agents must finish before synthesis runs
    graph.add_edge(["analyze_logs", "correlate_deploys"], "synthesize")

    # Linear — synthesis finishes, then report generates
    graph.add_edge("synthesize", "generate_report")

    # Terminal edge — report is the last node
    graph.add_edge("generate_report", END)

    # Compile the graph — validates all edges and nodes are connected
    compiled = graph.compile()

    logger.info("LangGraph pipeline compiled successfully")
    return compiled

    return graph

    

