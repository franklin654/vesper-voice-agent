from langchain_core.tools import tool


@tool
def ask_user(question: str) -> str:
    """Ask the user one short, specific question, but only when a required
    detail is missing and cannot be reasonably inferred or defaulted.
    Do not use this to confirm things you can reasonably assume, and do not
    use it as a first response before attempting the request."""
    # This body never actually runs. HumanInTheLoopMiddleware intercepts
    # the call before this executes and substitues the human's reply
    # instead - it's here only so the tool has a valid signature.
    raise NotImplementedError("handled by HumanInTheLoopMiddleware's 'respond' descision")
