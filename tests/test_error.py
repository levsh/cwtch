import re

from typing import Annotated

import pytest

from cwtch import ValidationError, dataclass
from cwtch.metadata import MaxLen


def test_error():

    @dataclass
    class M:
        data: Annotated[dict, MaxLen(1)]

    data = {
        "nodeNumber": 1,
        "frontendIpAddresses": {"ipAddress": ["10.1.1.1"]},
        "backendIpAddress": "10.1.1.1",
        "openHttpConnections": 0,
        "openHttpsConnections": 83,
        "maxHttpConnections": 255,
        "maxHttpsConnections": 255,
        "cpuUser": 1.05,
        "cpuSystem": 0.3,
        "cpuMax": 400,
        "ioWait": 0.0,
        "swapOut": 0.0,
        "maxFrontEndBandwidth": 10240000,
        "frontEndBytesRead": 17.8,
        "frontEndBytesWritten": 25.25,
        "maxBackEndBandwidth": 10240000,
        "backEndBytesRead": 22.99,
        "backEndBytesWritten": 9.87,
        "collectionTimestamp": 1637570003000,
        "volumes": {
            "volume": [
                {
                    "id": "archive001",
                    "blocksRead": 0.0,
                    "blocksWritten": 0.0,
                    "diskUtilization": 0.0,
                    "transferSpeed": 0.0,
                    "totalBytes": 514283986944,
                    "freeBytes": 492370341888,
                    "totalInodes": 134217728,
                    "freeInodes": 134180824,
                },
                {
                    "id": "archive002",
                    "blocksRead": 0.0,
                    "blocksWritten": 4.66,
                    "diskUtilization": 0.0,
                    "transferSpeed": 0.33,
                    "totalBytes": 514283986944,
                    "freeBytes": 490299199488,
                    "totalInodes": 134217728,
                    "freeInodes": 134182910,
                },
            ]
        },
    }

    with pytest.raises(
        ValidationError,
        match=re.escape(
            (
                "\n"
                "  Type: --> <class 'test_error.M'>\n"
                "  Path: ['data']\n"
                "  ValidationError:\n"
                "    Type: <class 'dict'> --> Annotated[dict, MaxLen(value=1)]\n"
                "    Input: {\n"
                "        'nodeNumber': 1,\n"
                "        'frontendIpAddresses': {'ipAddress': ['10.1.1.1']},\n"
                "        'backendIpAddress': '10.1.1.1',\n"
                "        'openHttpConnections': 0,\n"
                "        'openHttpsConnections': 83,\n"
                "        'maxHttpConnections': 255,\n"
                "        'maxHttpsConnections': 255,\n"
                "        'cpuUser': 1.05,\n"
                "        'cpuSystem': 0.3,\n"
                "        'cpuMax': 400,\n"
                "        ... +10\n"
                "    }\n"
                "    ValueError: value length should be <= 1"
            )
        ),
    ):
        M(data=data)
