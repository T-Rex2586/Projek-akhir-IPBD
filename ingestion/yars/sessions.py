"""
Custom requests Session with random User-Agent rotation.

Adapted from: https://github.com/datavorous/yars
"""
from requests import Session

from .agents import get_agent


class RandomUserAgentSession(Session):
    """
    Session class (inherited from requests.Session) which passes
    a random user agent with each request.
    """

    def request(self, *args, **kwargs):
        self.headers.update({"User-Agent": get_agent()})
        return super().request(*args, **kwargs)
