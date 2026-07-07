import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../backend"))

from app.events.router import EVENT_CODE_ALPHABET, generate_event_code


def test_event_code_uses_expected_charset() -> None:
    code = generate_event_code()

    assert len(code) == 6
    assert all(char in EVENT_CODE_ALPHABET for char in code)


def test_event_code_generation_is_reasonably_unique() -> None:
    codes = {generate_event_code() for _ in range(1000)}

    assert len(codes) > 990
