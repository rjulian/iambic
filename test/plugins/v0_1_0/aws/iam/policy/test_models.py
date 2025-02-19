from __future__ import annotations

from iambic.core.template_generation import merge_model
from iambic.plugins.v0_1_0.aws.iam.policy.models import (
    ManagedPolicyProperties,
    PolicyDocument,
)


def test_merge_policy_document_with_sid(aws_accounts):
    existing_statement_list = [
        {
            "effect": "Allow",
            "sid": "ExpireStatement",
            "expires_at": "2023-01-24",
        }
    ]
    existing_document = PolicyDocument(
        policy_name="foo", version="bar", statement=existing_statement_list
    )
    new_statement_list = [{"effect": "Allow", "sid": "ExpireStatement"}]
    new_document = PolicyDocument(
        policy_name="foo", version="bar", statement=new_statement_list
    )
    merged_document: PolicyDocument = merge_model(
        new_document, existing_document, aws_accounts
    )

    assert (
        merged_document.statement[0].expires_at
        == existing_document.statement[0].expires_at
    )


def test_merge_policy_document_without_sid(aws_accounts):
    existing_statement_list = [
        {
            "effect": "Allow",
            "expires_at": "2023-01-24",
        }
    ]
    existing_document = PolicyDocument(
        policy_name="foo", version="bar", statement=existing_statement_list
    )
    new_statement_list = [{"effect": "Allow"}]
    new_document = PolicyDocument(
        policy_name="foo", version="bar", statement=new_statement_list
    )
    merged_document: PolicyDocument = merge_model(
        new_document, existing_document, aws_accounts
    )
    assert (
        merged_document.statement[0].expires_at
        == existing_document.statement[0].expires_at
    )


def test_policy_path_validation():
    path = [
        {"included_accounts": ["account_1", "account_2"], "file_path": "/engineering"},
        {"included_accounts": ["account_3"], "file_path": "/finance"},
    ]
    properties_1 = ManagedPolicyProperties(
        policy_name="foo", path=path, policy_document={}
    )
    path_1 = properties_1.path
    path_2 = list(reversed(properties_1.path))
    assert path_1 != path_2  # because we reverse the list
    properties_1.path = path_2
    assert (
        properties_1.path == path_2
    )  # double check the list is reversed because validation doesn't happen after creation
    properties_1.validate_model_afterward()
    assert properties_1.path == path_1


def test_description_validation():
    description = [
        {"included_accounts": ["account_1", "account_2"], "description": "foo"},
        {"included_accounts": ["account_3"], "description": "bar"},
    ]
    properties_1 = ManagedPolicyProperties(
        policy_name="foo", description=description, policy_document={}
    )
    description_1 = properties_1.description
    description_2 = list(reversed(properties_1.description))
    assert description_1 != description_2  # because we reverse the list
    properties_1.description = description_2
    assert (
        properties_1.description == description_2
    )  # double check the list is reversed because validation doesn't happen after creation
    properties_1.validate_model_afterward()
    assert properties_1.description == description_1


def test_policy_document_validation():
    policy_document = [
        {"included_accounts": ["account_1", "account_2"], "policy_document": {}},
        {"included_accounts": ["account_3"], "policy_document": {}},
    ]
    properties_1 = ManagedPolicyProperties(
        policy_name="foo", policy_document=policy_document
    )
    policy_document_1 = properties_1.policy_document
    policy_document_2 = list(reversed(properties_1.policy_document))
    assert policy_document_1 != policy_document_2  # because we reverse the list
    properties_1.policy_document = policy_document_2
    assert (
        properties_1.policy_document == policy_document_2
    )  # double check the list is reversed because validation doesn't happen after creation
    properties_1.validate_model_afterward()
    assert properties_1.policy_document == policy_document_1


def test_role_properties_validation():
    tags_1 = [
        {"key": "apple", "value": "red", "included_accounts": ["ses"]},
        {"key": "apple", "value": "yellow", "included_accounts": ["development"]},
    ]
    properties_1 = ManagedPolicyProperties(
        policy_name="foo", policy_document={}, tags=tags_1
    )
    tag_models_1 = properties_1.tags
    tag_models_2 = list(reversed(properties_1.tags))
    assert tag_models_1 != tag_models_2  # because we reverse the list
    properties_1.tags = tag_models_2
    assert (
        properties_1.tags == tag_models_2
    )  # double check the list is reversed because validation doesn't happen after creation
    properties_1.validate_model_afterward()
    assert properties_1.tags == tag_models_1
