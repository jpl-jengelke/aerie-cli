from pathlib import Path
from typing import Dict, List
import json
import re

import pytest

from aerie_cli.aerie_client import AerieClient
from aerie_cli.aerie_host import AerieHostSession
from aerie_cli.schemas.client import Activity
from aerie_cli.schemas.api import ApiActivityPlanRead
from aerie_cli.schemas.client import ActivityPlanRead
from aerie_cli.schemas.client import ActivityPlanCreate
from aerie_cli.schemas.client import ResourceType
from aerie_cli.schemas.api import api_serialize
from attrs import asdict

BLANK_LINE_REGEX = r"^\s*$"
EXPECTED_RESULTS_DIRECTORY = Path(__file__).parent.joinpath("files", "expected_results")
INPUTS_DIRECTORY = Path(__file__).parent.joinpath("files", "inputs")


def _preprocess_query(q) -> str:
    lines: List[str] = q.split('\n')
    lines = [ln.strip() for ln in lines if not re.match(BLANK_LINE_REGEX, ln)]
    return ' '.join(lines)


class MockAerieHostSession(AerieHostSession):
    """
    Mock Aerie host listens for test queries and returns a mocked response.

    Responses are stored in ./files/mock_responses. Each JSON file should 
    contain a list of entries, each with two objects called "request" and 
    "response". The former should be the JSON data for a GraphQL query. The 
    response should be the JSON expected to be returned by 
    `AerieHostSession.post_to_graphql()`.

    [
        {
            "request": {
                "query": query, 
                "variables": variables
            },
            "response": {<populate>}
        },
        ...
    ]

    Pass the name of the mock query file to the constructor.
    """

    MOCK_QUERIES_DIRECTORY = Path(
        __file__).parent.joinpath('files', 'mock_responses')

    def __init__(self, mock_query_name: str) -> None:
        mock_query_fn = self.MOCK_QUERIES_DIRECTORY.joinpath(
            f"{mock_query_name}.json")
        with open(mock_query_fn, 'r') as fid:
            self.mock_data: List = json.load(fid)

    def post_to_graphql(self, query: str, **kwargs) -> Dict:

        # Get the next transaction being mocked
        mock_transaction = self.mock_data.pop(0)

        # Check that queries match, excepting whitespace mismatches
        assert _preprocess_query(query) == _preprocess_query(
            mock_transaction["request"]["query"])

        # Check that variables match
        assert kwargs == mock_transaction["request"]["variables"]

        return mock_transaction["response"]


def test_list_all_activity_plans():
    host_session = MockAerieHostSession('list_all_activity_plans')
    client = AerieClient(host_session)

    expected = json.loads("""
    [
        {
            "id": 1,
            "name": "plan--1",
            "model_id": 1,
            "start_time": "2025-01-01T00:00:00+00:00",
            "duration": "48:00:00",
            "simulations": [
                {
                    "id": 1
                }
            ]
        },
        {
            "id": 2,
            "name": "plan--2",
            "model_id": 2,
            "start_time": "2025-01-01T00:00:00+00:00",
            "duration": "48:00:00",
            "simulations": [
                {
                    "id": 2
                }
            ]
        }
    ]""")
    expected = [ActivityPlanRead.from_api_read(
        ApiActivityPlanRead(**e)
    ) for e in expected]
    assert client.list_all_activity_plans() == expected


def test_create_activity():
    host_session = MockAerieHostSession('create_activity')
    client = AerieClient(host_session)

    activity = Activity(**
        {
            "id": 1,
            "type": "NoOp",
            "start_offset": "00:00:00",
            "arguments": {"aParameter": "2030-001T00:00:00Z"},
            "name": "My Activity",
            "tags": [],
            "metadata": {},
            "anchor_id": None,
            "anchored_to_start": True,
        }
    )

    res = client.create_activity(activity, 1)

    assert res == 15


def test_update_activity():
    host_session = MockAerieHostSession("update_activity")
    client = AerieClient(host_session)

    activity = Activity(**
        {
            "type": "NoOp",
            "start_offset": "00:00:00",
            "arguments": {"aParameter": "2030-001T00:00:00Z"},
            "name": "My Activity",
        }
    )

    res = client.update_activity(15, activity, 1)

    assert res == 15


def test_get_resource_samples():

    # CASE 1: Get all states
    host_session = MockAerieHostSession('get_resource_samples_1')
    client = AerieClient(host_session)

    with open(EXPECTED_RESULTS_DIRECTORY.joinpath('get_resource_samples_1.json'), 'r') as fid:
        expected = json.load(fid)

    res = client.get_resource_samples(1)
    assert res == expected

    # CASE 2: Get only speicifc states
    host_session = MockAerieHostSession('get_resource_samples_2')
    client = AerieClient(host_session)

    with open(EXPECTED_RESULTS_DIRECTORY.joinpath('get_resource_samples_2.json'), 'r') as fid:
        expected = json.load(fid)

    res = client.get_resource_samples(1, ["hardwareState"])
    assert res == expected


def test_get_activity_plan_by_id():
    host_session = MockAerieHostSession("get_activity_plan_by_id")
    client = AerieClient(host_session)

    with open(
        EXPECTED_RESULTS_DIRECTORY.joinpath("get_activity_plan_by_id.json"), "r"
    ) as fid:
        expected = json.load(fid)

    res = asdict(
        client.get_activity_plan_by_id(1),
        value_serializer=api_serialize
    )
    assert res == expected


@pytest.mark.parametrize(["case_name"], [("create_activity_plan_1",), ("create_activity_plan_2",)])
def test_create_activity_plan(case_name: str):
    host_session = MockAerieHostSession(case_name)
    client = AerieClient(host_session)

    with open(INPUTS_DIRECTORY.joinpath(f"{case_name}.json"), "r") as fid:
        input_plan = ActivityPlanCreate.from_plan_read(ActivityPlanRead(**(json.loads(fid.read()))))

    res = client.create_activity_plan(7, input_plan)

    # Expected plan ID from mock response is 456
    assert res == 456


def test_get_resource_types():
    host_session = MockAerieHostSession("get_resource_types")
    client = AerieClient(host_session)

    expected = [
        ResourceType("/imager/dataRate", {"type": "real"}),
        ResourceType(
            "/imager/hardwareState",
            {
                "type": "variant",
                "variants": [
                    {"key": "OFF", "label": "OFF"},
                    {"key": "ON", "label": "ON"},
                ],
            },
        ),
        ResourceType(
            "/data/dataVolume",
            {
                "items": {"initial": {"type": "real"}, "rate": {"type": "real"}},
                "type": "struct",
            },
        ),
        ResourceType(
            "/data/arbitrarilyComplex",
            {
                "items": {
                    "items": {
                        "stringProperty": {"type": "string"},
                        "enumProperty": {
                            "type": "variant",
                            "variants": [
                                {"key": "A", "label": "A"},
                                {"key": "B", "label": "B"},
                            ],
                        },
                        "intProperty": {"type": "int"},
                        "booleanProperty": {"type": "boolean"},
                    },
                    "type": "struct",
                },
                "type": "series",
            },
        ),
    ]

    res = client.get_resource_types(1)
    assert res == expected

def test_get_sequence_json():
    host_session = MockAerieHostSession("get_sequence_json")
    client = AerieClient(host_session)
    
    expected = json.loads("""
    {
        "id": "2",
        "metadata": {
            "testKey": "testValue"
        },
        "steps": []
    }
    """)
    
    edsl_code = "export default () => Sequence.new({ seqId: '2', metadata: {\"testKey\": \"testValue\"}, steps: [] });"
    
    res = client.get_sequence_json(1, edsl_code)
    assert res == expected
