from __future__ import annotations

import sys
import unittest
from pathlib import Path


EXAMPLE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EXAMPLE_DIR))

from controller import IndependentSafetyController, SafetyRejected  # noqa: E402


class MutableClock:
    def __init__(self, value: float = 1_781_179_200.0) -> None:
        self.value = value

    def __call__(self) -> float:
        return self.value


class IndependentSafetyControllerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.clock = MutableClock()
        self.controller = IndependentSafetyController(
            clock=self.clock,
            token_key=b"unit-test-only-controller-key",
        )

    def request(self, token: str, **overrides: object) -> dict[str, object]:
        request: dict[str, object] = {
            "motion_id": "move-0001",
            "target": "buffer-zone-1",
            "max_speed_mps": 0.2,
            "safety_state_token": token,
        }
        request.update(overrides)
        return request

    def test_safe_motion_is_accepted(self) -> None:
        snapshot = self.controller.read_safety_state()
        result = self.controller.request_motion(
            self.request(snapshot["state_token"])
        )
        self.assertEqual(result["controller_decision"], "accepted")
        self.assertEqual(result["execution_status"], "completed")

    def test_controller_rechecks_current_state(self) -> None:
        snapshot = self.controller.read_safety_state()
        self.controller.set_state(human_detected=True)
        with self.assertRaisesRegex(SafetyRejected, "human_detected"):
            self.controller.request_motion(
                self.request(snapshot["state_token"])
            )

    def test_stale_state_token_is_rejected(self) -> None:
        snapshot = self.controller.read_safety_state()
        self.clock.value += 5.001
        with self.assertRaisesRegex(SafetyRejected, "stale_safety_state"):
            self.controller.request_motion(
                self.request(snapshot["state_token"])
            )

    def test_modified_state_token_is_rejected(self) -> None:
        snapshot = self.controller.read_safety_state()
        token = snapshot["state_token"]
        replacement = "A" if token[-1] != "A" else "B"
        with self.assertRaisesRegex(
            SafetyRejected,
            "invalid_safety_state_token",
        ):
            self.controller.request_motion(
                self.request(token[:-1] + replacement)
            )

    def test_state_token_cannot_be_replayed(self) -> None:
        snapshot = self.controller.read_safety_state()
        request = self.request(snapshot["state_token"])
        self.controller.request_motion(request)
        with self.assertRaisesRegex(SafetyRejected, "replayed_safety_state"):
            self.controller.request_motion(
                {**request, "motion_id": "move-0002"}
            )

    def test_speed_limit_is_controller_authoritative(self) -> None:
        snapshot = self.controller.read_safety_state()
        with self.assertRaisesRegex(
            SafetyRejected,
            "speed_exceeds_controller_limit",
        ):
            self.controller.request_motion(
                self.request(snapshot["state_token"], max_speed_mps=0.8)
            )

    def test_target_must_be_in_approved_zone(self) -> None:
        snapshot = self.controller.read_safety_state()
        with self.assertRaisesRegex(
            SafetyRejected,
            "target_outside_approved_zone",
        ):
            self.controller.request_motion(
                self.request(snapshot["state_token"], target="loading-dock")
            )


if __name__ == "__main__":
    unittest.main()
