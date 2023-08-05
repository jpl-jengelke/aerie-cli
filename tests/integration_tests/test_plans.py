# in case src_path is not from aeri-cli src and from site-packages
import os
import sys

import pytest

src_path = os.path.abspath(os.path.dirname(os.path.realpath(__file__)) + "/../src")
sys.path.insert(0, src_path)

from typer.testing import CliRunner
from pathlib import Path

from aerie_cli.aerie_client import AerieClient
from aerie_cli.aerie_host import AerieHostSession, AuthMethod
from aerie_cli.__main__ import app
from aerie_cli.commands.configurations import delete_all_persistent_files, upload_configurations, deactivate_session, activate_session
from aerie_cli.utils.sessions import get_active_session_client
from aerie_cli.commands import plans
from aerie_cli.commands import models

runner = CliRunner(mix_stderr = False)

GRAPHQL_URL = "http://localhost:8080/v1/graphql"
GATEWAY_URL = "http://localhost:9000"
AUTH_URL = "http://localhost:9000/auth/login"
AUTH_METHOD = AuthMethod.AERIE_NATIVE
USERNAME = ""
PASSWORD = ""
# This should only ever be set to the admin secret for a local instance of aerie
HASURA_ADMIN_SECRET = os.environ.get("HASURA_GRAPHQL_ADMIN_SECRET")

session = AerieHostSession.session_helper(
    AUTH_METHOD,
    GRAPHQL_URL,
    GATEWAY_URL,
    AUTH_URL,
    USERNAME,
    PASSWORD
)
session.session.headers["x-hasura-admin-secret"] = HASURA_ADMIN_SECRET
client = AerieClient(session)

test_dir = os.path.dirname(os.path.abspath(__file__))

files_path = os.path.join(test_dir, "files")

DOWNLOADED_FILE_NAME = "downloaded_file.test"

# Configuration Variables
configurations_path = os.path.join(files_path, "configuration")
config_json = os.path.join(configurations_path, "localhost_config.json")

# Model Variables
models_path = os.path.join(files_path, "models")
model_jar = os.path.join(models_path, "banananation-1.6.2.jar")
model_name = "banananation"
version = "0.0.1"
model_id = 0

# Plan Variables
plans_path = os.path.join(files_path, "plans")
plan_json = os.path.join(plans_path, "bake_bread_plan.json")
dup_plan_name = os.path.join(plans_path, "bake_bread_plan_2.json")
plan_id = 0
args_init = os.path.join(plans_path, "create_config.json")
args_update = os.path.join(plans_path, "update_config.json")

@pytest.fixture(scope="session", autouse=True)
def set_up_environment(request):
    # Resets the configurations and adds localhost
    deactivate_session()
    delete_all_persistent_files()
    upload_configurations(config_json)
    activate_session("localhost")
    persistent_client = None
    try:
        persistent_client = get_active_session_client()
    except:
        raise RuntimeError("Configuration is not active!")
    assert persistent_client.host_session.gateway_url == GATEWAY_URL,\
        "Aerie instances are mismatched. Ensure test URLs are the same."

    resp = client.get_mission_models()
    for api_mission_model in resp:
        client.delete_mission_model(api_mission_model.id)

    global model_id
    model_id = client.upload_mission_model(
        mission_model_path=model_jar,
        project_name=model_name, 
        mission="",
        version=version)

def cli_plan_simulate():
    return runner.invoke(
        app,
        ["-c", "localhost", "--hasura-admin-secret", HASURA_ADMIN_SECRET, "plans", "simulate", "--output", "temp.json"],
        input=str(plan_id) + "\n",
        catch_exceptions=False
    )

#######################
# TEST AND SETUP PLAN
# Uses model
#######################

def test_plan_upload():
    # Clean out plans first
    plans.clean()

    # Test plan upload
    result = runner.invoke(
        app,
        ["-c", "localhost", "--hasura-admin-secret", HASURA_ADMIN_SECRET, "plans", "upload", "--time-tag"],
        input=plan_json + "\n" + str(model_id) + "\n",
        catch_exceptions=False,
    )
    assert result.exit_code == 0,\
        f"{result.stdout}"\
        f"{result.stderr}"
    
    # Get uploaded plan id
    resp = client.get_all_activity_plans()
    latest_plan = resp[-1]
    global plan_id
    plan_id = latest_plan.id

    assert f"Created plan ID: {plan_id}" in result.stdout

def test_plan_duplicate():
    result = runner.invoke(
        app,
        ["-c", "localhost", "--hasura-admin-secret", HASURA_ADMIN_SECRET, "plans", "duplicate"],
        input=str(plan_id) + "\n" + dup_plan_name + "\n",
        catch_exceptions=False,
    )
    assert result.exit_code == 0,\
        f"{result.stdout}"\
        f"{result.stderr}"

    # Get duplicated plan id
    resp = client.get_all_activity_plans()
    latest_plan = resp[-1]
    duplicated_plan_id = latest_plan.id

    assert f"Duplicate activity plan created with ID: {duplicated_plan_id}" in result.stdout


def test_plan_list():
    result = runner.invoke(app, ["-c", "localhost", "--hasura-admin-secret", HASURA_ADMIN_SECRET, "plans", "list"],
                                   catch_exceptions=False,)
    assert result.exit_code == 0,\
        f"{result.stdout}"\
        f"{result.stderr}"
    assert "Current Activity Plans" in result.stdout


#######################
# SIMULATE PLAN
# Uses plan
#######################

def test_plan_simulate():
    result = cli_plan_simulate()
    sim_ids = client.get_simulation_dataset_ids_by_plan_id(plan_id)
    global sim_id
    sim_id = sim_ids[-1]
    assert result.exit_code == 0,\
        f"{result.stdout}"\
        f"{result.stderr}"
    assert f"Simulation completed" in result.stdout

def test_plan_download():
    result = runner.invoke(
        app,
        ["-c", "localhost", "--hasura-admin-secret", HASURA_ADMIN_SECRET, "plans", "download"],
        input=str(plan_id) + "\n" + DOWNLOADED_FILE_NAME + "\n",
        catch_exceptions=False,
    )
    path_to_plan = Path(DOWNLOADED_FILE_NAME)
    assert path_to_plan.exists()
    path_to_plan.unlink()
    assert result.exit_code == 0,\
        f"{result.stdout}"\
        f"{result.stderr}"
    assert f"Wrote activity plan" in result.stdout

def test_plan_download_resources():
    result = runner.invoke(
        app,
        ["-c", "localhost", "--hasura-admin-secret", HASURA_ADMIN_SECRET, "plans", "download-resources"],
        input=str(sim_id) + "\n" + DOWNLOADED_FILE_NAME + "\n",
        catch_exceptions=False,
    )
    path_to_resources = Path(DOWNLOADED_FILE_NAME)
    assert path_to_resources.exists()
    path_to_resources.unlink()
    assert result.exit_code == 0,\
        f"{result.stdout}"\
        f"{result.stderr}"
    assert f"Wrote resource timelines" in result.stdout

def test_plan_download_simulation():
    result = runner.invoke(
        app,
        ["-c", "localhost", "--hasura-admin-secret", HASURA_ADMIN_SECRET, "plans", "download-simulation"],
        input=str(sim_id) + "\n" + DOWNLOADED_FILE_NAME + "\n",
        catch_exceptions=False,
    )
    path_to_resources = Path(DOWNLOADED_FILE_NAME)
    assert path_to_resources.exists()
    path_to_resources.unlink()
    assert result.exit_code == 0,\
        f"{result.stdout}"\
        f"{result.stderr}"
    assert f"Wrote activity plan" in result.stdout

def test_plan_create_config():
    result = runner.invoke(
        app,
        ["-c", "localhost", "--hasura-admin-secret", HASURA_ADMIN_SECRET, "plans", "create-config"],
        input=str(plan_id) + "\n" + args_init + "\n",
        catch_exceptions=False,
    )
    assert result.exit_code == 0,\
        f"{result.stdout}"\
        f"{result.stderr}"
    assert f"Configuration Arguments for Plan ID: {plan_id}" in result.stdout
    assert "initialPlantCount: 2" in result.stdout
    assert "initialProducer: nobody" in result.stdout

def test_simulate_after_create_config():
    result = cli_plan_simulate()
    assert result.exit_code == 0,\
        f"{result.stdout}"\
        f"{result.stderr}"
    assert f"Simulation completed" in result.stdout

def test_plan_update_config():
    result = runner.invoke(
        app,
        ["-c", "localhost", "--hasura-admin-secret", HASURA_ADMIN_SECRET, "plans", "update-config"],
        input=str(plan_id) + "\n" + args_update + "\n",
        catch_exceptions=False,
    )
    assert result.exit_code == 0,\
        f"{result.stdout}"\
        f"{result.stderr}"
    assert f"Configuration Arguments for Plan ID: {plan_id}" in result.stdout
    assert "initialPlantCount: 3" in result.stdout
    assert "initialProducer: somebody" in result.stdout

def test_simulate_after_update_config():
    result = cli_plan_simulate()
    assert result.exit_code == 0,\
        f"{result.stdout}"\
        f"{result.stderr}"
    assert f"Simulation completed" in result.stdout

def test_plans_duplicate():
    result = runner.invoke(
        app,
        ["-c", "localhost", "--hasura-admin-secret", HASURA_ADMIN_SECRET, "plans", "duplicate"],
        input=str(plan_id) + "\n" + "duplicated_plan" + "\n",
        catch_exceptions=False,)
    assert result.exit_code == 0,\
        f"{result.stdout}"\
        f"{result.stderr}"
    assert "Duplicate activity plan created" in result.stdout

#######################
# DELETE PLANS
#######################

def test_plan_delete():
    result = runner.invoke(
        app,
        ["-c", "localhost", "--hasura-admin-secret", HASURA_ADMIN_SECRET, "plans", "delete"],
        input=str(plan_id) + "\n",
        catch_exceptions=False,)
    assert result.exit_code == 0,\
        f"{result.stdout}"\
        f"{result.stderr}"
    assert f"ID: {plan_id} has been removed." in result.stdout


def test_plan_clean():
    result = runner.invoke(
        app,
        ["-c", "localhost", "--hasura-admin-secret", HASURA_ADMIN_SECRET, "plans", "clean"],
        catch_exceptions=False,)
    assert result.exit_code == 0,\
        f"{result.stdout}"\
        f"{result.stderr}"
    assert (
        f"All activity plans have been deleted"
        in result.stdout
    )

#######################
# DELETE MODELS
#######################

def test_model_delete():
    result = runner.invoke(
        app,
        ["-c", "localhost", "--hasura-admin-secret", HASURA_ADMIN_SECRET, "models", "delete"],
        input=str(model_id),
        catch_exceptions=False,)
    assert result.exit_code == 0,\
        f"{result.stdout}"\
        f"{result.stderr}"
    assert f"ID: {model_id} has been removed" in result.stdout