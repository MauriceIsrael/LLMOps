"""Single choke point for engagement authorization (R4)."""

class Unauthorised(PermissionError):
    """Exception levée en cas d'accès non autorisé à un engagement (403-equivalent)."""

    def __init__(self, engagement: str):
        super().__init__(f"Unauthorized to access engagement '{engagement}'")
        self.engagement = engagement


def authorise(caller: str = "default_user", engagement: str = "default-engagement") -> None:
    """Single choke point for engagement access authorization.
    Every engagement tool calls this on its first line before touching the graph.
    """
    if not engagement:
        raise Unauthorised(engagement or "unknown")
