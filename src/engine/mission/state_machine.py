"""Mission state machine for phased flight execution.

Defines a finite-state machine whose modes correspond to the distinct
phases of a terrain-masked reconnaissance flight: transit, safe-hold,
observation pop-up, egress, return, and divert.
"""
from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .schema import Mission


class MissionMode(Enum):
    """Discrete phases of the mission lifecycle."""

    TRANSIT = "TRANSIT"
    SAFE_HOLD = "SAFE_HOLD"
    OBSERVE_SETUP = "OBSERVE_SETUP"
    POPUP_OBSERVE = "POPUP_OBSERVE"
    DROP_DOWN = "DROP_DOWN"
    EGRESS = "EGRESS"
    RETURN_HOME = "RETURN_HOME"
    DIVERT = "DIVERT"
    SUCCESS = "SUCCESS"
    FAIL = "FAIL"


# --------------------------------------------------------------------------- #
# Transition table                                                             #
# --------------------------------------------------------------------------- #
# Mapping from (current_mode, trigger_string) -> next_mode.
# Only explicitly listed pairs are legal transitions.

_TRANSITIONS: dict[tuple[MissionMode, str], MissionMode] = {
    # -- TRANSIT --
    (MissionMode.TRANSIT, "near_safe_hold"): MissionMode.SAFE_HOLD,
    (MissionMode.TRANSIT, "near_observe_box"): MissionMode.OBSERVE_SETUP,
    (MissionMode.TRANSIT, "risk_too_high"): MissionMode.DIVERT,
    (MissionMode.TRANSIT, "at_goal"): MissionMode.SUCCESS,
    (MissionMode.TRANSIT, "timeout"): MissionMode.FAIL,
    (MissionMode.TRANSIT, "critical_failure"): MissionMode.FAIL,
    # -- SAFE_HOLD --
    (MissionMode.SAFE_HOLD, "ready"): MissionMode.TRANSIT,
    (MissionMode.SAFE_HOLD, "danger"): MissionMode.DIVERT,
    (MissionMode.SAFE_HOLD, "timeout"): MissionMode.FAIL,
    (MissionMode.SAFE_HOLD, "critical_failure"): MissionMode.FAIL,
    # -- OBSERVE_SETUP --
    (MissionMode.OBSERVE_SETUP, "ready"): MissionMode.POPUP_OBSERVE,
    (MissionMode.OBSERVE_SETUP, "risk_too_high"): MissionMode.DIVERT,
    (MissionMode.OBSERVE_SETUP, "timeout"): MissionMode.FAIL,
    (MissionMode.OBSERVE_SETUP, "critical_failure"): MissionMode.FAIL,
    # -- POPUP_OBSERVE --
    (MissionMode.POPUP_OBSERVE, "observation_done"): MissionMode.DROP_DOWN,
    (MissionMode.POPUP_OBSERVE, "risk_too_high"): MissionMode.DROP_DOWN,
    (MissionMode.POPUP_OBSERVE, "timeout"): MissionMode.FAIL,
    (MissionMode.POPUP_OBSERVE, "critical_failure"): MissionMode.FAIL,
    # -- DROP_DOWN --
    (MissionMode.DROP_DOWN, "safely_descended"): MissionMode.EGRESS,
    (MissionMode.DROP_DOWN, "risk_too_high"): MissionMode.DIVERT,
    (MissionMode.DROP_DOWN, "timeout"): MissionMode.FAIL,
    (MissionMode.DROP_DOWN, "critical_failure"): MissionMode.FAIL,
    # -- EGRESS --
    (MissionMode.EGRESS, "back_to_transit"): MissionMode.TRANSIT,
    (MissionMode.EGRESS, "mission_done"): MissionMode.RETURN_HOME,
    (MissionMode.EGRESS, "risk_too_high"): MissionMode.DIVERT,
    (MissionMode.EGRESS, "timeout"): MissionMode.FAIL,
    (MissionMode.EGRESS, "critical_failure"): MissionMode.FAIL,
    # -- RETURN_HOME --
    (MissionMode.RETURN_HOME, "at_home"): MissionMode.SUCCESS,
    (MissionMode.RETURN_HOME, "at_goal"): MissionMode.SUCCESS,
    (MissionMode.RETURN_HOME, "risk_too_high"): MissionMode.DIVERT,
    (MissionMode.RETURN_HOME, "timeout"): MissionMode.FAIL,
    (MissionMode.RETURN_HOME, "critical_failure"): MissionMode.FAIL,
    # -- DIVERT --
    (MissionMode.DIVERT, "at_alt_lz"): MissionMode.SUCCESS,
    (MissionMode.DIVERT, "safe_landing"): MissionMode.SUCCESS,
    (MissionMode.DIVERT, "divert_failed"): MissionMode.FAIL,
    (MissionMode.DIVERT, "timeout"): MissionMode.FAIL,
    (MissionMode.DIVERT, "critical_failure"): MissionMode.FAIL,
}

# Pre-compute the set of terminal modes.
_TERMINAL_MODES = frozenset({MissionMode.SUCCESS, MissionMode.FAIL})


class MissionStateMachine:
    """Finite-state machine that tracks the current mission phase.

    Parameters
    ----------
    mission : Mission
        The mission specification (retained for future rule evaluation).
    """

    def __init__(self, mission: "Mission") -> None:
        self._mission = mission
        self._mode: MissionMode = MissionMode.TRANSIT
        self._history: list[tuple[MissionMode, str, MissionMode]] = []

    # -- public properties -------------------------------------------------- #

    @property
    def current_mode(self) -> MissionMode:
        """The active mission mode."""
        return self._mode

    @property
    def history(self) -> list[tuple[MissionMode, str, MissionMode]]:
        """Chronological list of ``(from_mode, trigger, to_mode)`` tuples."""
        return list(self._history)

    # -- transitions -------------------------------------------------------- #

    def transition(self, trigger: str) -> MissionMode:
        """Attempt a state transition driven by *trigger*.

        Parameters
        ----------
        trigger : str
            A short string describing the event (must match a key in
            the transition table).

        Returns
        -------
        MissionMode
            The resulting mode **after** the transition.

        Raises
        ------
        ValueError
            If the transition is not permitted from the current mode.
        """
        if self.is_terminal():
            raise ValueError(
                f"Cannot transition from terminal mode {self._mode.value}"
            )

        key = (self._mode, trigger)
        if key not in _TRANSITIONS:
            valid = self.get_valid_transitions()
            raise ValueError(
                f"Invalid trigger '{trigger}' for mode {self._mode.value}. "
                f"Valid triggers: {valid}"
            )

        prev = self._mode
        self._mode = _TRANSITIONS[key]
        self._history.append((prev, trigger, self._mode))
        return self._mode

    # -- queries ------------------------------------------------------------ #

    def is_terminal(self) -> bool:
        """Return *True* if the mission has reached a final state."""
        return self._mode in _TERMINAL_MODES

    def get_valid_transitions(self) -> list[str]:
        """Return the list of trigger strings valid from the current mode."""
        if self.is_terminal():
            return []
        return sorted(
            trigger
            for (mode, trigger) in _TRANSITIONS
            if mode == self._mode
        )

    # -- reset -------------------------------------------------------------- #

    def reset(self) -> None:
        """Reset the machine to its initial state (``TRANSIT``)."""
        self._mode = MissionMode.TRANSIT
        self._history.clear()
