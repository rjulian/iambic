from __future__ import annotations

import asyncio
import json
import os
import shutil
import tempfile
import uuid

import pytest
from filelock import FileLock

import iambic.core.utils
from iambic.config.dynamic_config import Config, load_config
from iambic.core.context import ctx
from iambic.core.iambic_enum import Command
from iambic.core.logger import log
from iambic.core.models import ExecutionMessage
from iambic.plugins.v0_1_0.aws.models import AWSAccount

if not os.environ.get("GITHUB_ACTIONS", None):
    # We will select a particular AWS_PROFILE to run on developer local machine
    # Github action runner will use temporary creds in the environment
    # If you are public developer, this probably won't work for you since
    # functional test requires particular cloud resources for testing.
    os.environ["AWS_PROFILE"] = "iambic_test_org_account/IambicHubRole"

os.environ["TESTING"] = "true"
FUNCTIONAL_TEST_TEMPLATE_DIR = os.getenv("FUNCTIONAL_TEST_TEMPLATE_DIR", None)

all_config = """
template_type: NOQ::Core::Config
version: '1'

extends:
  - key: AWS_SECRETS_MANAGER
    value: arn:aws:secretsmanager:us-west-2:442632209887:secret:dev/iambic_itest_secrets_v2-Ctmonc
    assume_role_arn: arn:aws:iam::442632209887:role/IambicSpokeRole

aws:
  organizations:
    - org_id: 'o-8t0mt0ybdd'
      hub_role_arn: 'arn:aws:iam::580605962305:role/IambicHubRole'
      org_name: 'iambic_test_org_account'
      org_account_id: '580605962305'
      identity_center:
        region: 'us-east-1'
      account_rules:
        - included_accounts:
            - '*'
          enabled: true
          iambic_managed: read_and_write
      default_rule:
        enabled: true
        iambic_managed: read_and_write
  accounts:
    - account_id: '192455039954'
      account_name: iambic_test_spoke_account_2
      iambic_managed: read_and_write
      org_id: o-8t0mt0ybdd
      spoke_role_arn: arn:aws:iam::192455039954:role/IambicSpokeRole
    - account_id: '333972133479'
      account_name: iambic_test_spoke_account_3
      iambic_managed: read_and_write
      org_id: o-8t0mt0ybdd
      spoke_role_arn: arn:aws:iam::333972133479:role/IambicSpokeRole
    - account_id: '580605962305'
      account_name: iambic_test_org_account
      iambic_managed: read_and_write
      org_id: o-8t0mt0ybdd
      spoke_role_arn: arn:aws:iam::580605962305:role/IambicSpokeRole
    - account_id: '442632209887'
      account_name: iambic_test_spoke_account_1
      iambic_managed: read_and_write
      org_id: o-8t0mt0ybdd
      spoke_role_arn: arn:aws:iam::442632209887:role/IambicSpokeRole
"""


class IambicTestDetails:
    config_path: str = None
    template_dir_path: str = None
    config: Config = None
    identity_center_account: AWSAccount = None

    def to_dict(self) -> dict:
        return {
            "config_path": self.config_path,
            "template_dir_path": self.template_dir_path,
        }


IAMBIC_TEST_DETAILS = IambicTestDetails()


@pytest.fixture(scope="session", autouse=True)
def session_data(request, tmp_path_factory, worker_id):
    if worker_id == "master":
        # not executing in with multiple workers, just produce the data and let
        # pytest's fixture caching do its job
        data = generate_templates_fixture(request)
        return data

    # get the temp directory shared by all workers
    root_tmp_dir = tmp_path_factory.getbasetemp().parent

    fn = root_tmp_dir / "data.json"
    with FileLock(str(fn) + ".lock"):
        if fn.is_file():
            data = json.loads(fn.read_text())
            setup_iambic_test_details(request, data)
        else:
            data = generate_templates_fixture(request)
            fn.write_text(json.dumps(data))
            setup_iambic_test_details(request, data)
    return data


def setup_iambic_test_details(request, data: dict):
    IAMBIC_TEST_DETAILS.template_dir_path = tempfile.mkdtemp(
        prefix="iambic_test_temp_templates_directory"
    )
    shutil.copytree(
        data["template_dir_path"],
        IAMBIC_TEST_DETAILS.template_dir_path,
        dirs_exist_ok=True,
    )
    setattr(
        iambic.core.utils,
        "__WRITABLE_DIRECTORY__",
        IAMBIC_TEST_DETAILS.template_dir_path,
    )
    fd, IAMBIC_TEST_DETAILS.config_path = tempfile.mkstemp(
        prefix="iambic_test_temp_config_filename", suffix=".yaml"
    )
    with open(IAMBIC_TEST_DETAILS.config_path, "w") as temp_file:
        temp_file.write(all_config)
    log.info("Setting up config for testing")
    IAMBIC_TEST_DETAILS.config = asyncio.run(
        load_config(IAMBIC_TEST_DETAILS.config_path)
    )
    for aws_account in IAMBIC_TEST_DETAILS.config.aws.accounts:
        if aws_account.identity_center_details:
            IAMBIC_TEST_DETAILS.identity_center_account = aws_account
            asyncio.run(aws_account.set_identity_center_details(batch_size=5))
            break

    def teardown():
        log_params = {
            "config_path": IAMBIC_TEST_DETAILS.config_path,
        }
        if not FUNCTIONAL_TEST_TEMPLATE_DIR:
            log_params["template_dir_path"] = IAMBIC_TEST_DETAILS.template_dir_path
        log.info("Removing temp files", **log_params)
        os.close(fd)
        os.unlink(IAMBIC_TEST_DETAILS.config_path)

        if not FUNCTIONAL_TEST_TEMPLATE_DIR:
            shutil.rmtree(IAMBIC_TEST_DETAILS.template_dir_path)

    request.addfinalizer(teardown)


def generate_templates_fixture(request) -> str:
    log.info("Generating templates for testing")
    ctx.eval_only = False

    fd, IAMBIC_TEST_DETAILS.config_path = tempfile.mkstemp(
        prefix="iambic_test_temp_config_filename", suffix=".yaml"
    )

    if FUNCTIONAL_TEST_TEMPLATE_DIR:
        IAMBIC_TEST_DETAILS.template_dir_path = FUNCTIONAL_TEST_TEMPLATE_DIR
    else:
        IAMBIC_TEST_DETAILS.template_dir_path = tempfile.mkdtemp(
            prefix="iambic_test_temp_templates_directory"
        )

    with open(IAMBIC_TEST_DETAILS.config_path, "w") as temp_file:
        temp_file.write(all_config)

    log.info("Setting up config for testing")
    IAMBIC_TEST_DETAILS.config = asyncio.run(
        load_config(IAMBIC_TEST_DETAILS.config_path)
    )

    session = request.node
    # this is magic snippet to introspect tests collected to see if they require import.
    # much of the aws functional tests expect to have existing import templates.
    # other recent functional tests does not have this dependency.
    aws_node_ids = [
        item.nodeid
        for item in session.items
        if "aws" in item.nodeid or "test_import" in item.nodeid
    ]

    if not FUNCTIONAL_TEST_TEMPLATE_DIR and len(aws_node_ids) > 0:
        exe_message = ExecutionMessage(
            execution_id=str(uuid.uuid4()), command=Command.IMPORT
        )
        asyncio.run(
            IAMBIC_TEST_DETAILS.config.run_import(
                exe_message, IAMBIC_TEST_DETAILS.template_dir_path
            )
        )
        log.info("Finished generating templates for testing")

    for aws_account in IAMBIC_TEST_DETAILS.config.aws.accounts:
        if aws_account.identity_center_details:
            IAMBIC_TEST_DETAILS.identity_center_account = aws_account
            asyncio.run(aws_account.set_identity_center_details())
            break

    log.info("Config setup complete")
    os.close(fd)
    return IAMBIC_TEST_DETAILS.to_dict()
