def add_to_history(state, role, content):
    state["messages"].append({"role": role, "content": content})
    return state 