"""StateGraph topology and invocation service."""

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph

from .nodes import fail_workflow, generate_output, load_context, persist_output, repair_output, route_after_validation, validate_output
from .state import GenerationState, WorkflowContext


def build_generation_graph(checkpointer: BaseCheckpointSaver):
    graph = StateGraph(GenerationState, context_schema=WorkflowContext)
    graph.add_node("load_context", load_context)
    graph.add_node("generate", generate_output)
    graph.add_node("validate", validate_output)
    graph.add_node("repair", repair_output)
    graph.add_node("persist", persist_output)
    graph.add_node("failed", fail_workflow)
    graph.add_edge(START, "load_context")
    graph.add_edge("load_context", "generate")
    graph.add_edge("generate", "validate")
    graph.add_conditional_edges("validate", route_after_validation, {"persist": "persist", "repair": "repair", "fail": "failed"})
    graph.add_edge("repair", "validate")
    graph.add_edge("persist", END)
    graph.add_edge("failed", END)
    return graph.compile(checkpointer=checkpointer, name="ecommerce_generation_workflow")


def run_generation_workflow(initial_state: GenerationState, context: WorkflowContext, checkpointer: BaseCheckpointSaver) -> GenerationState:
    graph = build_generation_graph(checkpointer)
    config = {"configurable": {"thread_id": f"task:{initial_state['task_id']}:attempt:{initial_state['attempt_id']}"}}
    return graph.invoke(initial_state, config=config, context=context)
