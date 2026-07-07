import os

import pytest


pytestmark = pytest.mark.skipif(
    os.getenv("INTEGRATION_TEST") != "true",
    reason="Set INTEGRATION_TEST=true to run mocked end-to-end integration tests.",
)


def test_full_flow_placeholder() -> None:
    """Integration flow scaffold.

    The unit suite covers the implemented modules. The full mocked OAuth ->
    Drive -> indexing -> scan -> search route test is intentionally gated until
    the async test database fixture is shared across routers.
    """
    assert True
