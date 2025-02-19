from __future__ import annotations

import uuid
from unittest import IsolatedAsyncioTestCase

from functional_tests.conftest import IAMBIC_TEST_DETAILS

from iambic.config.dynamic_config import load_config
from iambic.core.iambic_enum import Command
from iambic.core.models import ExecutionMessage


class ConfigDiscoveryTestCase(IsolatedAsyncioTestCase):
    # this test suite cannot tolerate parallel modification of cloud resources
    # for example, in the middle of getting ready, if a collect_aws_permission_sets
    # interleaves with permission set removal, it will fail.

    async def test_aws_account_name_updated(self):
        exe_message = ExecutionMessage(
            execution_id=str(uuid.uuid4()),
            command=Command.CONFIG_DISCOVERY,
            provider_type="aws",
        )
        config = await load_config(IAMBIC_TEST_DETAILS.config_path)
        original_name = config.aws.accounts[0].account_name
        new_name = "new_name"
        config.aws.accounts[0].account_name = new_name

        await config.run_discover_upstream_config_changes(
            exe_message, IAMBIC_TEST_DETAILS.template_dir_path
        )

        account_names = [account.account_name for account in config.aws.accounts]
        self.assertIn(original_name, account_names)
        self.assertNotIn(new_name, account_names)

    async def test_aws_account_discovered(self):
        config = await load_config(IAMBIC_TEST_DETAILS.config_path)
        original_aws_count = len(config.aws.accounts)
        removed_account = config.aws.accounts[-1]
        config.aws.accounts.pop(-1)
        exe_message = ExecutionMessage(
            execution_id=str(uuid.uuid4()),
            command=Command.CONFIG_DISCOVERY,
            provider_type="aws",
        )

        await config.run_discover_upstream_config_changes(
            exe_message, IAMBIC_TEST_DETAILS.template_dir_path
        )

        self.assertEqual(len(config.aws.accounts), original_aws_count)
        self.assertIn(
            removed_account.account_id,
            [account.account_id for account in config.aws.accounts],
        )
