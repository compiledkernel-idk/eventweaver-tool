from __future__ import annotations

import unittest
from datetime import datetime

from eventweaver.dsl import ExpressionError, compile_expression
from eventweaver.models import Event


def make_event(**kwargs):
    defaults = dict(
        timestamp=datetime(2024, 3, 1, 12, 0, 0),
        source="api",
        severity=2.0,
        message="authentication warning",
        metadata={"user": "amy"},
        raw={},
    )
    defaults.update(kwargs)
    return Event(**defaults)


class DSLTests(unittest.TestCase):
    def test_expression_matches_event(self) -> None:
        predicate = compile_expression("severity >= 2 and 'warning' in message")
        self.assertTrue(predicate(make_event()))

    def test_expression_access_metadata(self) -> None:
        predicate = compile_expression("metadata['user'] == 'amy'")
        self.assertTrue(predicate(make_event()))

    def test_invalid_expression_call_is_blocked(self) -> None:
        with self.assertRaises(ExpressionError):
            compile_expression("len(message) > 0")


if __name__ == "__main__":
    unittest.main()
