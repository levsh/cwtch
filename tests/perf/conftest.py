# import sys

# import pytest


# def pytest_collection_modifyitems(config, items):
#     if sys.version_info.minor > 13:
#         skip_marker = pytest.mark.skip(reason="Skip on Python > 3.13")
#         for item in items:
#             item.add_marker(skip_marker)
