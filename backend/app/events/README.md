# Events Module

The Events module owns organizer event management and public event-code lookup.

## Contents

- `router.py`: Event detail, deletion, reindex queueing, join-by-code lookup, and event-code generation helpers.
- `models.py`: Pydantic response schemas for event management endpoints.

## Running Tests

```bash
python -m pytest tests/unit/test_events.py -q
```

Event codes use six non-ambiguous uppercase characters, excluding symbols such as `O`, `0`, `I`, and `1`.
