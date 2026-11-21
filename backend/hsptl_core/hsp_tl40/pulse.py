"""Thin Pulse bridge contract; never fabricates physiological observations."""
from __future__ import annotations

from typing import Any, Protocol

from .kernel import EventKernel


class PulseProvider(Protocol):
    def step(self) -> dict[str, Any]: ...
    def get_state(self) -> dict[str, Any]: ...
    def apply_action(self, action: dict[str, Any]) -> dict[str, Any]: ...


class UnavailablePulseProvider:
    """Safe default until a real Pulse runtime/provider is configured."""
    def step(self) -> dict[str, Any]:
        return self.get_state()

    def get_state(self) -> dict[str, Any]:
        return {"connected": False, "source": None, "sequence": None,
                "observations": {}, "status": "unavailable",
                "message": "No Pulse provider is connected; physiological values are unknown."}

    def apply_action(self, action: dict[str, Any]) -> dict[str, Any]:
        return {"applied": False, "state": self.get_state(),
                "reason": "No Pulse provider is connected."}


class PulseBridge:
    def __init__(self, kernel: EventKernel, provider: PulseProvider | None = None):
        self.kernel = kernel
        self.provider = provider or UnavailablePulseProvider()

    def step(self) -> dict[str, Any]:
        state = self.provider.step()
        result = {"state": state, "source": "pulse_bridge"}
        if isinstance(state, dict) and state.get("connected"):
            observations = state.get("observations", {})
            if not isinstance(observations, dict):
                return {**result, "recorded": False,
                        "reason": "Pulse provider observations were not a structured object."}
            event = self.kernel.append("platform.pulse.observation_recorded", {
                "source": str(state.get("source") or "unspecified_pulse_provider"),
                "sequence": state.get("sequence"),
                "observations": observations,
                "clinical_state_evidence": state.get("clinical_state_evidence", []),
            })
            result.update({"recorded": True, "event": event})
        else:
            result.update({"recorded": False, "reason": "Pulse provider unavailable; no observation was recorded."})
        return result

    def getState(self) -> dict[str, Any]:
        return self.provider.get_state()

    def get_state(self) -> dict[str, Any]:
        return self.getState()

    def applyAction(self, action: dict[str, Any]) -> dict[str, Any]:
        if not self.provider.get_state().get("connected"):
            event = self.kernel.append("platform.pulse.action_requested", {
                "action": action, "decision": "abstain", "reason": "Pulse provider unavailable"})
            return {"applied": False, "state": self.getState(), "event": event,
                    "reason": "Pulse provider unavailable; action was not applied."}
        result = self.provider.apply_action(action)
        provider_event = result.get("event")
        event = self.kernel.append("platform.pulse.action_requested", {
            "action": action, "decision": "pass" if result.get("applied") else "fail",
            "result": result})
        # Preserve both event layers: the provider's domain event (e.g. a
        # simulation.action.rejected) and the bridge-level action audit event.
        return {**result, "provider_event": provider_event, "event": event}

    def apply_action(self, action: dict[str, Any]) -> dict[str, Any]:
        return self.applyAction(action)
