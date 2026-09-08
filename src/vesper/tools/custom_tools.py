from typing import List

from langchain_core.tools import tool
import os
import subprocess

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

@tool
def execute_shell_command(command_args: List[str]) -> str:
    """Executes a system command securely using a list of arguments and returns the output.

    This function spawns a child process to run external commands without invoking 
    a shell, mitigating command injection vulnerabilities. It captures both standard 
    output and standard error streams.

    Args:
        command_args: A list of strings representing the command and its arguments.
            For example: ["git", "status"] or ["ls", "-la"].

    Returns:
        A string containing the standard output (stdout) if the command succeeds, 
        or an error message detailing the exit code and standard error (stderr) 
        if the command fails.

    Raises:
        TypeError: If command_args is not a list of strings.
    """
    # 1. Input validation for safety and stability
    if not isinstance(command_args, list) or not all(isinstance(arg, str) for arg in command_args):
        raise TypeError("command_args must be a list of strings")

    if not command_args:
        return "Error: No command provided"

    try:
        # 2. Secure execution with DEVNULL to prevent hanging
        result = subprocess.run(
            command_args, 
            check=True, 
            capture_output=True, 
            text=True, 
            stdin=subprocess.DEVNULL
        )
        return result.stdout
    
    except subprocess.CalledProcessError as e:
        # 3. Clean multiline string formatting using inspect.cleandoc or standard strip
        return (
            f"Command failed with exit code {e.returncode}\n"
            f"Error Message: {e.stderr.strip() if e.stderr else 'No stderr captured.'}"
        )
