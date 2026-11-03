from ..http import HttpClient


class Endpoints:
    """Base of every tab. Subclasses hold one method per backend endpoint."""

    def __init__(self, http: HttpClient):
        self._h = http
