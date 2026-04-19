from __future__ import annotations


class StubReadonlyAssistBackend:
    def generate(self, payload: dict[str, object]) -> dict[str, object]:
        return {
            "operator_assessment": "shadow-mode stub",
            "next_steps": [],
            "confidence": "low",
        }
