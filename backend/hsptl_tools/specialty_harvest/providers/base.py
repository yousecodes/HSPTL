"""Provider adapter interface."""
from __future__ import annotations

class SourceAdapter:
    name = ""

    def search(self, key, args):
        raise NotImplementedError

    def count(self, key, args):
        raise NotImplementedError

