# Alias for backward compatibility
try:
    from backend.sandbox.executor import SandboxExecutor, BLOCKED_IMPORTS
except ImportError:
    from sandbox.executor import SandboxExecutor, BLOCKED_IMPORTS

__all__ = ["SandboxExecutor", "BLOCKED_IMPORTS"]
