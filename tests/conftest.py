import base64
import copy
import json
import os
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from unittest.mock import Mock, PropertyMock
from uuid import UUID, uuid4

import pytest
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from flask import Flask, url_for

from app import create_app
from app.enums import AuthType, ServicePermission
from notifications_python_client.errors import HTTPError
from notifications_utils.url_safe_token import generate_token

from . import (
    TestClient,
    api_key_json,
    assert_url_expected,
    generate_uuid,
    inbound_sms_json,
    invite_json,
    job_json,
    notification_json,
    org_invite_json,
    organization_json,
    sample_uuid,
    service_json,
    template_json,
    template_version_json,
    user_json,
)

load_dotenv()


class ElementNotFound(Exception):
    pass


@pytest.fixture(scope="session")
def notify_admin():
    app = Flask("app")
    create_app(app)

    ctx = app.app_context()
    ctx.push()

    app.test_client_class = TestClient
    return app


@pytest.fixture
def service_one(api_user_active):
    return service_json(SERVICE_ONE_ID, "service one", [api_user_active["id"]])


@pytest.fixture
def service_two(api_user_active):
    return service_json(SERVICE_TWO_ID, "service two", [api_user_active["id"]])


@pytest.fixture
def multiple_reply_to_email_addresses(mocker):
    def _get(service_id):
        return [
            {
                "id": "1234",
                "service_id": service_id,
                "email_address": "test@example.com",
                "is_default": True,
                "created_at": datetime.utcnow(),
                "updated_at": None,
            },
            {
                "id": "5678",
                "service_id": service_id,
                "email_address": "test2@example.com",
                "is_default": False,
                "created_at": datetime.utcnow(),
                "updated_at": None,
            },
            {
                "id": "9457",
                "service_id": service_id,
                "email_address": "test3@example.com",
                "is_default": False,
                "created_at": datetime.utcnow(),
                "updated_at": None,
            },
        ]

    return mocker.patch(
        "app.service_api_client.get_reply_to_email_addresses",
        side_effect=_get,
    )


@pytest.fixture
def no_reply_to_email_addresses(mocker):
    def _get(service_id):
        return []

    return mocker.patch(
        "app.service_api_client.get_reply_to_email_addresses", side_effect=_get
    )


@pytest.fixture
def single_reply_to_email_address(mocker):
    def _get(service_id):
        return [
            {
                "id": "1234",
                "service_id": service_id,
                "email_address": "test@example.com",
                "is_default": True,
                "created_at": datetime.utcnow(),
                "updated_at": None,
            }
        ]

    return mocker.patch(
        "app.service_api_client.get_reply_to_email_addresses", side_effect=_get
    )


@pytest.fixture
def get_default_reply_to_email_address(mocker):
    def _get(service_id, reply_to_email_id):
        return {
            "id": "1234",
            "service_id": service_id,
            "email_address": "test@example.com",
            "is_default": True,
            "created_at": datetime.utcnow(),
            "updated_at": None,
        }

    return mocker.patch(
        "app.service_api_client.get_reply_to_email_address", side_effect=_get
    )


@pytest.fixture
def get_non_default_reply_to_email_address(mocker):
    def _get(service_id, reply_to_email_id):
        return {
            "id": "1234",
            "service_id": service_id,
            "email_address": "test@example.com",
            "is_default": False,
            "created_at": datetime.utcnow(),
            "updated_at": None,
        }

    return mocker.patch(
        "app.service_api_client.get_reply_to_email_address", side_effect=_get
    )


@pytest.fixture
def mock_add_reply_to_email_address(mocker):
    def _add_reply_to(service_id, email_address, is_default=False):
        return

    return mocker.patch(
        "app.service_api_client.add_reply_to_email_address", side_effect=_add_reply_to
    )


@pytest.fixture
def mock_update_reply_to_email_address(mocker):
    def _update_reply_to(
        service_id, reply_to_email_id, email_address=None, active=None, is_default=False
    ):
        return

    return mocker.patch(
        "app.service_api_client.update_reply_to_email_address",
        side_effect=_update_reply_to,
    )


@pytest.fixture
def multiple_sms_senders(mocker):
    def _get(service_id):
        return [
            {
                "id": "1234",
                "service_id": service_id,
                "sms_sender": "Example",
                "is_default": True,
                "created_at": datetime.utcnow(),
                "inbound_number_id": "1234",
                "updated_at": None,
            },
            {
                "id": "5678",
                "service_id": service_id,
                "sms_sender": "Example 2",
                "is_default": False,
                "created_at": datetime.utcnow(),
                "inbound_number_id": None,
                "updated_at": None,
            },
            {
                "id": "9457",
                "service_id": service_id,
                "sms_sender": "Example 3",
                "is_default": False,
                "created_at": datetime.utcnow(),
                "inbound_number_id": None,
                "updated_at": None,
            },
        ]

    return mocker.patch("app.service_api_client.get_sms_senders", side_effect=_get)


@pytest.fixture
def multiple_sms_senders_with_diff_default(mocker):
    def _get(service_id):
        return [
            {
                "id": "1234",
                "service_id": service_id,
                "sms_sender": "Example",
                "is_default": True,
                "created_at": datetime.utcnow(),
                "inbound_number_id": None,
                "updated_at": None,
            },
            {
                "id": "5678",
                "service_id": service_id,
                "sms_sender": "Example 2",
                "is_default": False,
                "created_at": datetime.utcnow(),
                "inbound_number_id": None,
                "updated_at": None,
            },
            {
                "id": "9457",
                "service_id": service_id,
                "sms_sender": "Example 3",
                "is_default": False,
                "created_at": datetime.utcnow(),
                "inbound_number_id": "12354",
                "updated_at": None,
            },
        ]

    return mocker.patch("app.service_api_client.get_sms_senders", side_effect=_get)


@pytest.fixture
def multiple_sms_senders_no_inbound(mocker):
    def _get(service_id):
        return [
            {
                "id": "1234",
                "service_id": service_id,
                "sms_sender": "Example",
                "is_default": True,
                "created_at": datetime.utcnow(),
                "inbound_number_id": None,
                "updated_at": None,
            },
            {
                "id": "5678",
                "service_id": service_id,
                "sms_sender": "Example 2",
                "is_default": False,
                "created_at": datetime.utcnow(),
                "inbound_number_id": None,
                "updated_at": None,
            },
        ]

    return mocker.patch("app.service_api_client.get_sms_senders", side_effect=_get)


@pytest.fixture
def no_sms_senders(mocker):
    def _get(service_id):
        return []

    return mocker.patch("app.service_api_client.get_sms_senders", side_effect=_get)


@pytest.fixture
def single_sms_sender(mocker):
    def _get(service_id):
        return [
            {
                "id": "1234",
                "service_id": service_id,
                "sms_sender": "GOVUK",
                "is_default": True,
                "created_at": datetime.utcnow(),
                "inbound_number_id": None,
                "updated_at": None,
            }
        ]

    return mocker.patch("app.service_api_client.get_sms_senders", side_effect=_get)


@pytest.fixture
def get_default_sms_sender(mocker):
    def _get(service_id, sms_sender_id):
        return {
            "id": "1234",
            "service_id": service_id,
            "sms_sender": "GOVUK",
            "is_default": True,
            "created_at": datetime.utcnow(),
            "inbound_number_id": None,
            "updated_at": None,
        }

    return mocker.patch("app.service_api_client.get_sms_sender", side_effect=_get)


@pytest.fixture
def get_non_default_sms_sender(mocker):
    def _get(service_id, sms_sender_id):
        return {
            "id": "1234",
            "service_id": service_id,
            "sms_sender": "GOVUK",
            "is_default": False,
            "created_at": datetime.utcnow(),
            "inbound_number_id": None,
            "updated_at": None,
        }

    return mocker.patch("app.service_api_client.get_sms_sender", side_effect=_get)


@pytest.fixture
def mock_add_sms_sender(mocker):
    def _add_sms_sender(
        service_id, sms_sender, is_default=False, inbound_number_id=None
    ):
        return

    return mocker.patch(
        "app.service_api_client.add_sms_sender", side_effect=_add_sms_sender
    )


@pytest.fixture
def mock_update_sms_sender(mocker):
    def _update_sms_sender(
        service_id, sms_sender_id, sms_sender=None, active=None, is_default=False
    ):
        return

    return mocker.patch(
        "app.service_api_client.update_sms_sender", side_effect=_update_sms_sender
    )


@pytest.fixture
def multiple_available_inbound_numbers(mocker):
    def _get():
        return {
            "data": [
                {
                    "active": True,
                    "created_at": "2017-10-18T16:57:14.154185Z",
                    "id": "781d9c60-7a7e-46b7-9896-7b045b992fa7",
                    "number": "2021212124",
                    "provider": "sns",
                    "service": None,
                    "updated_at": None,
                },
                {
                    "active": True,
                    "created_at": "2017-10-18T16:57:22.585806Z",
                    "id": "781d9c60-7a7e-46b7-9896-7b045b992fa5",
                    "number": "2021212125",
                    "provider": "sns",
                    "service": None,
                    "updated_at": None,
                },
                {
                    "active": True,
                    "created_at": "2017-10-18T16:57:38.585806Z",
                    "id": "781d9c61-7a7e-46b7-9896-7b045b992fa5",
                    "number": "2021212126",
                    "provider": "sns",
                    "service": None,
                    "updated_at": None,
                },
            ]
        }

    return mocker.patch(
        "app.inbound_number_client.get_available_inbound_sms_numbers", side_effect=_get
    )


@pytest.fixture
def no_available_inbound_numbers(mocker):
    def _get():
        return {"data": []}

    return mocker.patch(
        "app.inbound_number_client.get_available_inbound_sms_numbers", side_effect=_get
    )


@pytest.fixture
def fake_uuid():
    return sample_uuid()


@pytest.fixture
def mock_get_service(mocker, api_user_active):
    def _get(service_id):
        service = service_json(
            service_id, users=[api_user_active["id"]], message_limit=50
        )
        return {"data": service}

    return mocker.patch("app.service_api_client.get_service", side_effect=_get)


@pytest.fixture
def mock_get_service_statistics(mocker, api_user_active):
    def _get(service_id, limit_days=None):
        return {
            "email": {"requested": 0, "delivered": 0, "failed": 0},
            "sms": {"requested": 0, "delivered": 0, "failed": 0},
        }

    return mocker.patch(
        "app.service_api_client.get_service_statistics", side_effect=_get
    )


@pytest.fixture
def mock_get_detailed_services(mocker, fake_uuid):
    service_one = service_json(
        id_=SERVICE_ONE_ID,
        name="service_one",
        users=[fake_uuid],
        message_limit=1000,
        active=True,
        restricted=False,
    )
    service_two = service_json(
        id_=fake_uuid,
        name="service_two",
        users=[fake_uuid],
        message_limit=1000,
        active=True,
        restricted=True,
    )
    service_one["statistics"] = {
        "email": {"requested": 0, "delivered": 0, "failed": 0},
        "sms": {"requested": 0, "delivered": 0, "failed": 0},
    }
    service_two["statistics"] = {
        "email": {"requested": 0, "delivered": 0, "failed": 0},
        "sms": {"requested": 0, "delivered": 0, "failed": 0},
    }
    services = {"data": [service_one, service_two]}

    return mocker.patch("app.service_api_client.get_services", return_value=services)


@pytest.fixture
def mock_get_live_service(mocker, api_user_active):
    def _get(service_id):
        service = service_json(
            service_id, users=[api_user_active["id"]], restricted=False
        )
        return {"data": service}

    return mocker.patch("app.service_api_client.get_service", side_effect=_get)


@pytest.fixture
def mock_create_service(mocker):
    def _create(
        service_name,
        organization_type,
        message_limit,
        restricted,
        user_id,
        email_from,
    ):
        service = service_json(
            101,
            service_name,
            [user_id],
            message_limit=message_limit,
            restricted=restricted,
            email_from=email_from,
        )
        return service["id"]

    return mocker.patch("app.service_api_client.create_service", side_effect=_create)


@pytest.fixture
def mock_update_service(mocker):
    def _update(service_id, **kwargs):
        service = service_json(
            service_id,
            **{
                key: kwargs[key]
                for key in kwargs
                if key
                in [
                    "name",
                    "users",
                    "message_limit",
                    "active",
                    "restricted",
                    "email_from",
                    "sms_sender",
                    "permissions",
                ]
            },
        )
        return {"data": service}

    return mocker.patch(
        "app.service_api_client.update_service", side_effect=_update, autospec=True
    )


@pytest.fixture
def mock_update_service_raise_httperror_duplicate_name(mocker):
    def _update(service_id, **kwargs):
        json_mock = Mock(
            return_value={
                "message": {
                    "name": ["Duplicate service name '{}'".format(kwargs.get("name"))]
                }
            }
        )
        resp_mock = Mock(status_code=400, json=json_mock)
        http_error = HTTPError(response=resp_mock, message="Default message")
        raise http_error

    return mocker.patch("app.service_api_client.update_service", side_effect=_update)


SERVICE_ONE_ID = "596364a0-858e-42c8-9062-a8fe822260eb"
SERVICE_TWO_ID = "147ad62a-2951-4fa1-9ca0-093cd1a52c52"
ORGANISATION_ID = "c011fa40-4cbe-4524-b415-dde2f421bd9c"
ORGANISATION_TWO_ID = "d9b5be73-0b36-4210-9d89-8f1a5c2fef26"
TEMPLATE_ONE_ID = "b22d7d94-2197-4a7d-a8e7-fd5f9770bf48"
USER_ONE_ID = "7b395b52-c6c1-469c-9d61-54166461c1ab"


@pytest.fixture
def mock_get_services(mocker, active_user_with_permissions):
    def _get_services(params_dict=None):
        service_one = service_json(
            SERVICE_ONE_ID,
            "service_one",
            [active_user_with_permissions["id"]],
            1000,
            True,
            False,
        )
        service_two = service_json(
            SERVICE_TWO_ID,
            "service_two",
            [active_user_with_permissions["id"]],
            1000,
            True,
            False,
        )
        return {"data": [service_one, service_two]}

    return mocker.patch(
        "app.service_api_client.get_services", side_effect=_get_services
    )


@pytest.fixture
def mock_get_services_with_no_services(mocker):
    def _get_services(params_dict=None):
        return {"data": []}

    return mocker.patch(
        "app.service_api_client.get_services", side_effect=_get_services
    )


@pytest.fixture
def mock_get_services_with_one_service(mocker, api_user_active):
    def _get_services(params_dict=None):
        return {
            "data": [
                service_json(
                    SERVICE_ONE_ID,
                    "service_one",
                    [api_user_active["id"]],
                    1000,
                    True,
                    True,
                )
            ]
        }

    return mocker.patch(
        "app.service_api_client.get_services", side_effect=_get_services
    )


@pytest.fixture
def mock_get_service_template(mocker):
    def _get(service_id, template_id, version=None):
        template = template_json(
            service_id,
            template_id,
            "Two week reminder",
            "sms",
            "Template <em>content</em> with & entity",
        )
        if version:
            template.update({"version": version})
        return {"data": template}

    return mocker.patch("app.service_api_client.get_service_template", side_effect=_get)


@pytest.fixture
def mock_get_service_template_with_priority(mocker):
    def _get(service_id, template_id, version=None):
        template = template_json(
            service_id,
            template_id,
            "Two week reminder",
            "sms",
            "Template <em>content</em> with & entity",
            process_type="priority",
        )
        if version:
            template.update({"version": version})
        return {"data": template}

    return mocker.patch("app.service_api_client.get_service_template", side_effect=_get)


@pytest.fixture
def mock_get_deleted_template(mocker):
    def _get(service_id, template_id, version=None):
        template = template_json(
            service_id,
            template_id,
            "Two week reminder",
            "sms",
            "Template <em>content</em> with & entity",
            archived=True,
        )
        if version:
            template.update({"version": version})
        return {"data": template}

    return mocker.patch("app.service_api_client.get_service_template", side_effect=_get)


@pytest.fixture
def mock_get_template_version(mocker, api_user_active):
    def _get(service_id, template_id, version):
        template_version = template_version_json(
            service_id, template_id, api_user_active, version=version
        )
        return {"data": template_version}

    return mocker.patch("app.service_api_client.get_service_template", side_effect=_get)


@pytest.fixture
def mock_get_template_versions(mocker, api_user_active):
    def _get(service_id, template_id):
        template_version = template_version_json(
            service_id, template_id, api_user_active, version=1
        )
        return {"data": [template_version]}

    return mocker.patch(
        "app.service_api_client.get_service_template_versions", side_effect=_get
    )


@pytest.fixture
def mock_get_service_template_with_placeholders(mocker):
    def _get(service_id, template_id, version=None):
        template = template_json(
            service_id,
            template_id,
            "Two week reminder",
            "sms",
            "((name)), Template <em>content</em> with & entity",
        )
        return {"data": template}

    return mocker.patch("app.service_api_client.get_service_template", side_effect=_get)


@pytest.fixture
def mock_get_empty_service_template_with_optional_placeholder(mocker):
    def _get(service_id, template_id, version=None):
        template = template_json(
            service_id,
            template_id,
            name="Optional content",
            content="((show_placeholder??Some content))",
        )
        return {"data": template}

    return mocker.patch("app.service_api_client.get_service_template", side_effect=_get)


@pytest.fixture
def mock_get_service_template_with_multiple_placeholders(mocker):
    def _get(service_id, template_id, version=None):
        template = template_json(
            service_id,
            template_id,
            "Two week reminder",
            "sms",
            "((one)) ((two)) ((three))",
        )
        return {"data": template}

    return mocker.patch("app.service_api_client.get_service_template", side_effect=_get)


@pytest.fixture
def mock_get_service_template_with_placeholders_same_as_recipient(mocker):
    def _get(service_id, template_id, version=None):
        template = template_json(
            service_id,
            template_id,
            "Two week reminder",
            "sms",
            "((name)) ((date)) ((PHONENUMBER))",
        )
        return {"data": template}

    return mocker.patch("app.service_api_client.get_service_template", side_effect=_get)


@pytest.fixture
def mock_get_service_email_template(mocker):
    def _get(service_id, template_id, version=None):
        template = template_json(
            service_id,
            template_id,
            "Two week reminder",
            "email",
            "Your vehicle tax expires on ((date))",
            "Your ((thing)) is due soon",
            redact_personalisation=False,
        )
        return {"data": template}

    return mocker.patch("app.service_api_client.get_service_template", side_effect=_get)


@pytest.fixture
def mock_get_service_email_template_without_placeholders(mocker):
    def _get(service_id, template_id, version=None):
        template = template_json(
            service_id,
            template_id,
            name="Two week reminder",
            type_="email",
            content="Your vehicle tax expires soon",
            subject="Your thing is due soon",
            redact_personalisation=False,
        )
        return {"data": template}

    return mocker.patch("app.service_api_client.get_service_template", side_effect=_get)


@pytest.fixture
def mock_create_service_template(mocker, fake_uuid):
    def _create(
        name,
        type_,
        content,
        service,
        subject=None,
        process_type=None,
        parent_folder_id=None,
    ):
        template = template_json(
            fake_uuid, name, type_, content, service, process_type, parent_folder_id
        )
        return {"data": template}

    return mocker.patch(
        "app.service_api_client.create_service_template", side_effect=_create
    )


@pytest.fixture
def mock_update_service_template(mocker):
    def _update(id_, name, type_, content, service, subject=None, process_type=None):
        template = template_json(
            service, id_, name, type_, content, subject, process_type
        )
        return {"data": template}

    return mocker.patch(
        "app.service_api_client.update_service_template", side_effect=_update
    )


@pytest.fixture
def mock_create_service_template_content_too_big(mocker):
    def _create(
        name,
        type_,
        content,
        service,
        subject=None,
        process_type=None,
        parent_folder_id=None,
    ):
        json_mock = Mock(
            return_value={
                "message": {
                    "content": [
                        "Content has a character count greater than the limit of 459"
                    ]
                },
                "result": "error",
            }
        )
        resp_mock = Mock(status_code=400, json=json_mock)
        http_error = HTTPError(
            response=resp_mock,
            message={
                "content": [
                    "Content has a character count greater than the limit of 459"
                ]
            },
        )
        raise http_error

    return mocker.patch(
        "app.service_api_client.create_service_template", side_effect=_create
    )


@pytest.fixture
def mock_update_service_template_400_content_too_big(mocker):
    def _update(id_, name, type_, content, service, subject=None, process_type=None):
        json_mock = Mock(
            return_value={
                "message": {
                    "content": [
                        "Content has a character count greater than the limit of 459"
                    ]
                },
                "result": "error",
            }
        )
        resp_mock = Mock(status_code=400, json=json_mock)
        http_error = HTTPError(
            response=resp_mock,
            message={
                "content": [
                    "Content has a character count greater than the limit of 459"
                ]
            },
        )
        raise http_error

    return mocker.patch(
        "app.service_api_client.update_service_template", side_effect=_update
    )


def create_service_templates(service_id, number_of_templates=4):
    template_types = ["sms", "sms", "email", "email"]
    service_templates = []

    for _ in range(1, number_of_templates + 1):
        template_number = "two" if _ % 2 == 0 else "one"
        template_type = template_types[(_ % 4) - 1]

        service_templates.append(
            template_json(
                service_id,
                TEMPLATE_ONE_ID if _ == 1 else str(generate_uuid()),
                "{}_template_{}".format(template_type, template_number),
                template_type,
                "{} template {} content".format(template_type, template_number),
                subject=(
                    "{} template {} subject".format(template_type, template_number)
                    if template_type == "email"
                    else None
                ),
            )
        )

    return {"data": service_templates}


def _template(template_type, name, parent=None, template_id=None):
    return {
        "id": template_id or str(uuid4()),
        "name": name,
        "template_type": template_type,
        "folder": parent,
    }


@pytest.fixture
def mock_get_service_templates(mocker):
    def _create(service_id):
        return create_service_templates(service_id)

    return mocker.patch(
        "app.service_api_client.get_service_templates", side_effect=_create
    )


@pytest.fixture
def mock_get_more_service_templates_than_can_fit_onscreen(mocker):
    def _create(service_id):
        return create_service_templates(service_id, number_of_templates=20)

    return mocker.patch(
        "app.service_api_client.get_service_templates", side_effect=_create
    )


@pytest.fixture
def mock_get_service_templates_when_no_templates_exist(mocker):
    def _create(service_id):
        return {"data": []}

    return mocker.patch(
        "app.service_api_client.get_service_templates", side_effect=_create
    )


@pytest.fixture
def mock_get_service_templates_with_only_one_template(mocker):
    def _get(service_id):
        return {
            "data": [
                template_json(
                    service_id,
                    generate_uuid(),
                    "sms_template_one",
                    "sms",
                    "sms template one content",
                )
            ]
        }

    return mocker.patch(
        "app.service_api_client.get_service_templates", side_effect=_get
    )


@pytest.fixture
def mock_delete_service_template(mocker):
    def _delete(service_id, template_id):
        template = template_json(
            service_id,
            template_id,
            "Template to delete",
            "sms",
            "content to be deleted",
        )
        return {"data": template}

    return mocker.patch(
        "app.service_api_client.delete_service_template", side_effect=_delete
    )


@pytest.fixture
def mock_redact_template(mocker):
    return mocker.patch("app.service_api_client.redact_service_template")


@pytest.fixture
def mock_update_service_template_sender(mocker):
    def _update(service_id, template_id, reply_to):
        return

    return mocker.patch(
        "app.service_api_client.update_service_template_sender", side_effect=_update
    )


@pytest.fixture
def api_user_pending(fake_uuid):
    return create_user(id=fake_uuid, state="pending")


@pytest.fixture
def platform_admin_user(fake_uuid):
    return create_platform_admin_user(
        permissions={
            SERVICE_ONE_ID: [
                ServicePermission.SEND_TEXTS,
                ServicePermission.SEND_EMAILS,
                ServicePermission.MANAGE_USERS,
                ServicePermission.MANAGE_TEMPLATES,
                ServicePermission.MANAGE_SETTINGS,
                "manage_api_keys",
                ServicePermission.VIEW_ACTIVITY,
            ]
        }
    )


@pytest.fixture
def platform_admin_user_no_service_permissions():
    """
    this fixture is for situations where we want to test that platform admin can access
    an endpoint even though they have no explicit permissions for that service.
    """
    return create_platform_admin_user()


@pytest.fixture
def api_user_active():
    return create_api_user_active()


@pytest.fixture
def api_user_active_email_auth(fake_uuid):
    return create_user(id=fake_uuid, auth_type=AuthType.EMAIL_AUTH)


@pytest.fixture
def active_user_with_permissions_no_mobile(fake_uuid):
    return create_service_one_admin(
        id=fake_uuid,
        mobile_number=None,
    )


@pytest.fixture
def api_nongov_user_active(fake_uuid):
    return create_service_one_admin(
        id=fake_uuid,
        email_address="someuser@example.com",
    )


@pytest.fixture
def active_user_with_permissions(fake_uuid):
    return create_active_user_with_permissions()


@pytest.fixture
def active_user_empty_permissions(fake_uuid):
    return create_active_user_empty_permissions()


@pytest.fixture
def active_user_with_permission_to_two_services(fake_uuid):
    permissions = [
        "send_texts",
        "send_emails",
        "manage_users",
        "manage_templates",
        ServicePermission.MANAGE_SETTINGS,
        "manage_api_keys",
        "view_activity",
    ]

    return create_user(
        id=fake_uuid,
        permissions={
            SERVICE_ONE_ID: permissions,
            SERVICE_TWO_ID: permissions,
        },
        organizations=[ORGANISATION_ID],
        services=[SERVICE_ONE_ID, SERVICE_TWO_ID],
    )


@pytest.fixture
def active_user_with_permission_to_other_service(
    active_user_with_permission_to_two_services,
):
    active_user_with_permission_to_two_services["permissions"].pop(SERVICE_ONE_ID)
    active_user_with_permission_to_two_services["services"].pop(0)
    active_user_with_permission_to_two_services["name"] = "Service Two User"
    active_user_with_permission_to_two_services["email_address"] = (
        "service-two-user@test.gsa.gov"
    )
    return active_user_with_permission_to_two_services


@pytest.fixture
def active_caseworking_user():
    return create_active_caseworking_user()


@pytest.fixture
def active_user_view_permissions():
    return create_active_user_view_permissions()


@pytest.fixture
def active_user_no_settings_permission():
    return create_active_user_no_settings_permission()


@pytest.fixture
def api_user_locked(fake_uuid):
    return create_user(
        id=fake_uuid,
        failed_login_count=10,
        password_changed_at=None,
    )


@pytest.fixture
def api_user_request_password_reset(fake_uuid):
    return create_user(
        id=fake_uuid,
        failed_login_count=5,
    )


@pytest.fixture
def api_user_changed_password(fake_uuid):
    return create_user(
        id=fake_uuid,
        failed_login_count=5,
        password_changed_at=str(datetime.utcnow() + timedelta(minutes=1)),
    )


@pytest.fixture
def mock_send_change_email_verification(mocker):
    return mocker.patch("app.user_api_client.send_change_email_verification")


@pytest.fixture
def mock_register_user(mocker, api_user_pending):
    def _register(name, email_address, mobile_number, password, auth_type):
        api_user_pending["name"] = name
        api_user_pending["email_address"] = email_address
        api_user_pending["mobile_number"] = mobile_number
        api_user_pending["password"] = password
        api_user_pending["auth_type"] = auth_type
        return api_user_pending

    return mocker.patch("app.user_api_client.register_user", side_effect=_register)


@pytest.fixture
def mock_get_non_govuser(mocker, api_user_active):
    api_user_active["email_address"] = "someuser@example.com"

    def _get_user(id_):
        api_user_active["id"] = id_
        return api_user_active

    return mocker.patch("app.user_api_client.get_user", side_effect=_get_user)


@pytest.fixture
def mock_get_user(mocker, api_user_active):
    def _get_user(id_):
        api_user_active["id"] = id_
        return api_user_active

    return mocker.patch("app.user_api_client.get_user", side_effect=_get_user)


@pytest.fixture
def mock_get_locked_user(mocker, api_user_locked):
    def _get_user(id_):
        api_user_locked["id"] = id_
        return api_user_locked

    return mocker.patch("app.user_api_client.get_user", side_effect=_get_user)


@pytest.fixture
def mock_get_user_pending(mocker, api_user_pending):
    return mocker.patch("app.user_api_client.get_user", return_value=api_user_pending)


@pytest.fixture
def mock_get_user_by_email(mocker, api_user_active):
    def _get_user(email_address):
        api_user_active["email_address"] = email_address
        return api_user_active

    return mocker.patch("app.user_api_client.get_user_by_email", side_effect=_get_user)


@pytest.fixture
def mock_dont_get_user_by_email(mocker):
    def _get_user(email_address):
        return None

    return mocker.patch(
        "app.user_api_client.get_user_by_email", side_effect=_get_user, autospec=True
    )


@pytest.fixture
def mock_get_user_by_email_request_password_reset(
    mocker, api_user_request_password_reset
):
    return mocker.patch(
        "app.user_api_client.get_user_by_email",
        return_value=api_user_request_password_reset,
    )


@pytest.fixture
def mock_get_user_by_email_user_changed_password(mocker, api_user_changed_password):
    return mocker.patch(
        "app.user_api_client.get_user_by_email", return_value=api_user_changed_password
    )


@pytest.fixture
def mock_get_user_by_email_locked(mocker, api_user_locked):
    return mocker.patch(
        "app.user_api_client.get_user_by_email", return_value=api_user_locked
    )


@pytest.fixture
def mock_get_user_by_email_pending(mocker, api_user_pending):
    return mocker.patch(
        "app.user_api_client.get_user_by_email", return_value=api_user_pending
    )


@pytest.fixture
def mock_get_user_by_email_not_found(mocker, api_user_active):
    def _get_user(email):
        json_mock = Mock(return_value={"message": "Not found", "result": "error"})
        resp_mock = Mock(status_code=404, json=json_mock)
        http_error = HTTPError(response=resp_mock, message="Default message")
        raise http_error

    return mocker.patch("app.user_api_client.get_user_by_email", side_effect=_get_user)


@pytest.fixture
def mock_verify_password(mocker):
    def _verify_password(user, password):
        return True

    return mocker.patch(
        "app.user_api_client.verify_password", side_effect=_verify_password
    )


@pytest.fixture
def mock_update_user_password(mocker, api_user_active):
    def _update(user_id, password):
        api_user_active["id"] = user_id
        return api_user_active

    return mocker.patch("app.user_api_client.update_password", side_effect=_update)


@pytest.fixture
def mock_update_user_attribute(mocker, api_user_active):
    def _update(user_id, **kwargs):
        api_user_active["id"] = user_id
        return api_user_active

    return mocker.patch(
        "app.user_api_client.update_user_attribute", side_effect=_update
    )


@pytest.fixture
def mock_activate_user(mocker, api_user_active):
    def _activate(user_id):
        api_user_active["id"] = user_id
        return {"data": api_user_active}

    return mocker.patch("app.user_api_client.activate_user", side_effect=_activate)


@pytest.fixture
def mock_email_is_not_already_in_use(mocker):
    return mocker.patch(
        "app.user_api_client.get_user_by_email_or_none", return_value=None
    )


@pytest.fixture
def mock_revoke_api_key(mocker):
    def _revoke(service_id, key_id):
        return {}

    return mocker.patch("app.api_key_api_client.revoke_api_key", side_effect=_revoke)


@pytest.fixture
def mock_get_api_keys(mocker, fake_uuid):
    def _get_keys(service_id, key_id=None):
        keys = {
            "apiKeys": [
                api_key_json(
                    id_=fake_uuid,
                    name="some key name",
                ),
                api_key_json(
                    id_="1234567",
                    name="another key name",
                    expiry_date=str(date.fromtimestamp(0)),
                ),
            ]
        }
        return keys

    return mocker.patch("app.api_key_api_client.get_api_keys", side_effect=_get_keys)


@pytest.fixture
def mock_get_no_api_keys(mocker):
    def _get_keys(service_id):
        keys = {"apiKeys": []}
        return keys

    return mocker.patch("app.api_key_api_client.get_api_keys", side_effect=_get_keys)


@pytest.fixture
def mock_login(mocker, mock_get_user, mock_update_user_attribute, mock_events):
    def _verify_code(user_id, code, code_type):
        return True, ""

    def _no_services(params_dict=None):
        return {"data": []}

    return (
        mocker.patch("app.user_api_client.check_verify_code", side_effect=_verify_code),
        mocker.patch("app.service_api_client.get_services", side_effect=_no_services),
    )


@pytest.fixture
def mock_send_verify_code(mocker):
    return mocker.patch("app.user_api_client.send_verify_code")


@pytest.fixture
def mock_send_verify_email(mocker):
    return mocker.patch("app.user_api_client.send_verify_email")


@pytest.fixture
def mock_check_verify_code(mocker):
    def _verify(user_id, code, code_type):
        return True, ""

    return mocker.patch("app.user_api_client.check_verify_code", side_effect=_verify)


@pytest.fixture
def mock_check_verify_code_code_not_found(mocker):
    def _verify(user_id, code, code_type):
        return False, "Code not found"

    return mocker.patch("app.user_api_client.check_verify_code", side_effect=_verify)


@pytest.fixture
def mock_check_verify_code_code_expired(mocker):
    def _verify(user_id, code, code_type):
        return False, "Code has expired"

    return mocker.patch("app.user_api_client.check_verify_code", side_effect=_verify)


@pytest.fixture
def mock_create_job(mocker, api_user_active):
    def _create(
        job_id,
        service_id,
        scheduled_for=None,
        template_id=None,
        original_file_name=None,
        notification_count=None,
        valid=None,
    ):
        return job_json(
            service_id,
            api_user_active,
            job_id=job_id,
        )

    return mocker.patch("app.job_api_client.create_job", side_effect=_create)


@pytest.fixture
def mock_get_job(mocker, api_user_active):
    def _get_job(service_id, job_id):
        return {"data": job_json(service_id, api_user_active, job_id=job_id)}

    return mocker.patch("app.job_api_client.get_job", side_effect=_get_job)


@pytest.fixture
def mock_get_job_doesnt_exist(mocker):
    def _get_job(service_id, job_id):
        raise HTTPError(response=Mock(status_code=404, json={}), message={})

    return mocker.patch("app.job_api_client.get_job", side_effect=_get_job)


@pytest.fixture
def mock_get_scheduled_job(mocker, api_user_active):
    def _get_job(service_id, job_id):
        return {
            "data": job_json(
                service_id,
                api_user_active,
                job_id=job_id,
                job_status="scheduled",
                scheduled_for="2016-01-02T05:00:00.061258",
            )
        }

    return mocker.patch("app.job_api_client.get_job", side_effect=_get_job)


@pytest.fixture
def mock_get_cancelled_job(mocker, api_user_active):
    def _get_job(service_id, job_id):
        return {
            "data": job_json(
                service_id,
                api_user_active,
                job_id=job_id,
                job_status="cancelled",
                scheduled_for="2016-01-01T00:00:00.061258",
            )
        }

    return mocker.patch("app.job_api_client.get_job", side_effect=_get_job)


@pytest.fixture
def mock_get_job_in_progress(mocker, api_user_active):
    def _get_job(service_id, job_id):
        return {
            "data": job_json(
                service_id,
                api_user_active,
                job_id=job_id,
                notification_count=10,
                notifications_requested=5,
                job_status="processing",
            )
        }

    return mocker.patch("app.job_api_client.get_job", side_effect=_get_job)


@pytest.fixture
def mock_get_job_with_sending_limits_exceeded(mocker, api_user_active):
    def _get_job(service_id, job_id):
        return {
            "data": job_json(
                service_id,
                api_user_active,
                job_id=job_id,
                notification_count=10,
                notifications_requested=5,
                job_status="sending limits exceeded",
            )
        }

    return mocker.patch("app.job_api_client.get_job", side_effect=_get_job)


@pytest.fixture
def mock_has_jobs(mocker):
    return mocker.patch("app.job_api_client.has_jobs", return_value=True)


@pytest.fixture
def mock_has_no_jobs(mocker):
    return mocker.patch("app.job_api_client.has_jobs", return_value=False)


@pytest.fixture
def mock_get_jobs(mocker, api_user_active, fake_uuid):
    def _get_jobs(service_id, limit_days=None, statuses=None, page=1):
        if statuses is None:
            statuses = ["", "scheduled", "pending", "cancelled", "finished"]

        jobs = [
            job_json(
                service_id,
                api_user_active,
                job_id=fake_uuid,
                original_file_name=filename,
                scheduled_for=scheduled_for,
                job_status=job_status,
                template_version=template_version,
                template_name=template_name,
            )
            for filename, scheduled_for, job_status, template_name, template_version in (
                (
                    "full_of_regret.csv",
                    "2016-01-01 23:09:00.061258",
                    "cancelled",
                    "Template X",
                    1,
                ),
                (
                    "even_later.csv",
                    "2016-01-01 23:09:00.061258",
                    "scheduled",
                    "Template Y",
                    1,
                ),
                (
                    "send_me_later.csv",
                    "2016-01-01 11:09:00.061258",
                    "scheduled",
                    "Template Z",
                    1,
                ),
                ("export 1/1/2016.xls", "", "finished", "Template A", 1),
                ("all email addresses.xlsx", "", "pending", "Template B", 1),
                ("applicants.ods", "", "finished", "Template C", 1),
                ("thisisatest.csv", "", "finished", "Template D", 2),
            )
        ]
        return {
            "data": [job for job in jobs if job["job_status"] in statuses],
            "links": {
                "prev": "services/{}/jobs?page={}".format(service_id, page - 1),
                "next": "services/{}/jobs?page={}".format(service_id, page + 1),
            },
        }

    return mocker.patch("app.job_api_client.get_jobs", side_effect=_get_jobs)


@pytest.fixture
def mock_get_scheduled_job_stats(mocker, api_user_active):
    return mocker.patch(
        "app.job_api_client.get_scheduled_job_stats",
        return_value={
            # These values match the return value of `mock_get_jobs`
            "count": 2,
            "soonest_scheduled_for": "2016-01-01 11:09:00",
        },
    )


@pytest.fixture
def mock_get_uploads(mocker, api_user_active):
    def _get_uploads(service_id, limit_days=None, statuses=None, page=1):
        uploads = [
            {
                "id": "job_id_1",
                "original_file_name": "some.csv",
                "notification_count": 10,
                "created_at": "2016-01-01 11:09:00.061258",
                "statistics": [
                    {"count": 8, "status": "delivered"},
                    {"count": 2, "status": "temporary-failure"},
                ],
                "upload_type": "job",
                "template_type": "sms",
                "recipient": None,
            },
        ]
        return {
            "data": uploads,
            "links": {
                "prev": "services/{}/uploads?page={}".format(service_id, page - 1),
                "next": "services/{}/uploads?page={}".format(service_id, page + 1),
            },
        }

    # Why is mocking on the model needed?
    return mocker.patch(
        "app.models.job.PaginatedUploads.client_method", side_effect=_get_uploads
    )


@pytest.fixture
def _mock_get_no_uploads(mocker, api_user_active):
    mocker.patch(
        "app.models.job.PaginatedUploads.client_method",
        return_value={
            "data": [],
        },
    )


@pytest.fixture
def mock_get_no_jobs(mocker, api_user_active):
    return mocker.patch(
        "app.models.job.PaginatedJobs.client_method",
        return_value={
            "data": [],
            "links": {},
        },
    )


@pytest.fixture
def mock_get_notifications(
    mocker,
    api_user_active,
):
    def _get_notifications(
        service_id,
        job_id=None,
        page=1,
        page_size=50,
        count_pages=None,
        template_type=None,
        status=None,
        limit_days=None,
        rows=5,
        include_jobs=None,
        include_from_test_key=None,
        to=None,
        include_one_off=None,
    ):
        job = None
        if job_id is not None:
            job = job_json(service_id, api_user_active, job_id=job_id)
        if template_type:
            template = template_json(
                service_id,
                id_=str(generate_uuid()),
                type_=template_type[0],
                redact_personalisation=False,
            )
        else:
            template = template_json(
                service_id,
                id_=str(generate_uuid()),
                redact_personalisation=False,
            )
        return notification_json(
            service_id,
            template=template,
            rows=rows,
            job=job,
            with_links=True if count_pages is None else count_pages,
            created_by_name="Firstname Lastname",
        )

    return mocker.patch(
        "app.notification_api_client.get_notifications_for_service",
        side_effect=_get_notifications,
    )


@pytest.fixture
def mock_get_notifications_with_previous_next(mocker):
    def _get_notifications(
        service_id,
        job_id=None,
        page=1,
        count_pages=None,
        template_type=None,
        status=None,
        limit_days=None,
        include_jobs=None,
        include_from_test_key=None,
        to=None,
        include_one_off=None,
    ):
        return notification_json(
            service_id, rows=50, with_links=True if count_pages is None else count_pages
        )

    return mocker.patch(
        "app.notification_api_client.get_notifications_for_service",
        side_effect=_get_notifications,
    )


@pytest.fixture
def mock_get_notifications_with_no_notifications(mocker):
    def _get_notifications(
        service_id,
        job_id=None,
        page=1,
        count_pages=None,
        template_type=None,
        status=None,
        limit_days=None,
        include_jobs=None,
        include_from_test_key=None,
        to=None,
        include_one_off=None,
    ):
        return notification_json(service_id, rows=0)

    return mocker.patch(
        "app.notification_api_client.get_notifications_for_service",
        side_effect=_get_notifications,
    )


@pytest.fixture
def mock_get_inbound_sms(mocker):
    def _get_inbound_sms(service_id, user_number=None, page=1):
        return inbound_sms_json()

    return mocker.patch(
        "app.service_api_client.get_inbound_sms",
        side_effect=_get_inbound_sms,
    )


@pytest.fixture
def mock_get_inbound_sms_by_id_with_no_messages(mocker):
    def _get_inbound_sms_by_id(service_id, notification_id):
        raise HTTPError(response=Mock(status_code=404))

    return mocker.patch(
        "app.service_api_client.get_inbound_sms_by_id",
        side_effect=_get_inbound_sms_by_id,
    )


@pytest.fixture
def mock_get_most_recent_inbound_sms(mocker):
    def _get_most_recent_inbound_sms(service_id, user_number=None, page=1):
        return inbound_sms_json()

    return mocker.patch(
        "app.service_api_client.get_most_recent_inbound_sms",
        side_effect=_get_most_recent_inbound_sms,
    )


@pytest.fixture
def mock_get_most_recent_inbound_sms_with_no_messages(mocker):
    def _get_most_recent_inbound_sms(service_id, user_number=None, page=1):
        return {"has_next": False, "data": []}

    return mocker.patch(
        "app.service_api_client.get_most_recent_inbound_sms",
        side_effect=_get_most_recent_inbound_sms,
    )


@pytest.fixture
def mock_get_inbound_sms_summary(mocker):
    def _get_inbound_sms_summary(
        service_id,
    ):
        return {"count": 9999, "most_recent": datetime.utcnow().isoformat()}

    return mocker.patch(
        "app.service_api_client.get_inbound_sms_summary",
        side_effect=_get_inbound_sms_summary,
    )


@pytest.fixture
def mock_get_inbound_sms_summary_with_no_messages(mocker):
    def _get_inbound_sms_summary(
        service_id,
    ):
        return {"count": 0, "latest_message": None}

    return mocker.patch(
        "app.service_api_client.get_inbound_sms_summary",
        side_effect=_get_inbound_sms_summary,
    )


@pytest.fixture
def mock_get_inbound_number_for_service(mocker):
    return mocker.patch(
        "app.inbound_number_client.get_inbound_sms_number_for_service",
        return_value={"data": {"number": "2028675301"}},
    )


@pytest.fixture
def mock_no_inbound_number_for_service(mocker):
    return mocker.patch(
        "app.inbound_number_client.get_inbound_sms_number_for_service",
        return_value={"data": {}},
    )


@pytest.fixture
def mock_has_permissions(mocker):
    def _has_permission(*permissions, restrict_admin_usage=False, allow_org_user=False):
        return True

    return mocker.patch(
        "app.models.user.User.has_permissions", side_effect=_has_permission
    )


@pytest.fixture
def mock_get_users_by_service(mocker):
    def _get_users_for_service(service_id):
        return [
            create_service_one_admin(
                id=sample_uuid(),
                logged_in_at=None,
                mobile_number="+12028675109",
                email_address="notify@digital.cabinet-office.gov.uk",
            )
        ]

    # You shouldn’t be calling the user API client directly, so it’s the
    # instance on the model that’s mocked here
    return mocker.patch(
        "app.models.user.Users.client_method", side_effect=_get_users_for_service
    )


@pytest.fixture
def mock_s3_download(mocker):
    def _download(service_id, upload_id):
        return """
            phone number,name
            +12028675109,John
            +12028675109,Smith
        """

    return mocker.patch("app.main.views.send.s3download", side_effect=_download)


@pytest.fixture
def sample_invite(mocker, service_one):
    id_ = USER_ONE_ID
    from_user = service_one["users"][0]
    email_address = "invited_user@test.gsa.gov"
    service_id = service_one["id"]
    permissions = "view_activity,send_emails,send_texts,manage_settings,manage_users,manage_api_keys"
    created_at = str(datetime.utcnow())
    auth_type = "sms_auth"
    folder_permissions = []

    return invite_json(
        id_,
        from_user,
        service_id,
        email_address,
        permissions,
        created_at,
        "pending",
        auth_type,
        folder_permissions,
    )


@pytest.fixture
def encoded_invite_data():
    """
    This mimics what API does when it encodes invite data in
    service_invite/rest.py
    """
    invite_data = {
        "service_id": "service",
        "invited_user_id": "invited_user",
        "permissions": ["manage_everything"],
        "folder_permissions": [],
        "from_user_id": "xyz",
    }
    invite_data = json.dumps(invite_data)
    invite_data = invite_data.encode("utf8")
    invite_data = base64.b64encode(invite_data)
    return invite_data.decode("utf8")


@pytest.fixture
def expired_invite(service_one):
    id_ = USER_ONE_ID
    from_user = service_one["users"][0]
    email_address = "invited_user@test.gsa.gov"
    service_id = service_one["id"]
    permissions = "view_activity,send_emails,send_texts,manage_settings,manage_users,manage_api_keys"
    created_at = str(datetime.utcnow() - timedelta(days=3))
    auth_type = "sms_auth"
    folder_permissions = []

    return invite_json(
        id_,
        from_user,
        service_id,
        email_address,
        permissions,
        created_at,
        "expired",
        auth_type,
        folder_permissions,
    )


@pytest.fixture
def mock_create_invite(mocker, sample_invite):
    def _create_invite(
        from_user, service_id, email_address, permissions, folder_permissions
    ):
        sample_invite["from_user"] = from_user
        sample_invite["service"] = service_id
        sample_invite["email_address"] = email_address
        sample_invite["status"] = "pending"
        sample_invite["permissions"] = permissions
        sample_invite["folder_permissions"] = folder_permissions
        return sample_invite

    return mocker.patch(
        "app.invite_api_client.create_invite", side_effect=_create_invite
    )


@pytest.fixture
def mock_get_invites_for_service(mocker, service_one, sample_invite):
    def _get_invites(service_id):
        data = []
        for i in range(0, 5):
            invite = copy.copy(sample_invite)
            invite["email_address"] = "user_{}@testnotify.gsa.gov".format(i)
            data.append(invite)
        return data

    return mocker.patch(
        "app.models.user.InvitedUsers.client_method", side_effect=_get_invites
    )


@pytest.fixture
def mock_get_invites_without_manage_permission(mocker, service_one, sample_invite):
    def _get_invites(service_id):
        return [
            invite_json(
                id_=str(sample_uuid()),
                from_user=service_one["users"][0],
                email_address="invited_user@test.gsa.gov",
                service_id=service_one["id"],
                permissions="view_activity,send_messages,manage_api_keys",
                created_at=str(datetime.utcnow()),
                auth_type="sms_auth",
                folder_permissions=[],
                status="pending",
            )
        ]

    return mocker.patch(
        "app.models.user.InvitedUsers.client_method", side_effect=_get_invites
    )


@pytest.fixture
def mock_accept_invite(mocker, sample_invite):
    def _accept(service_id, invite_id):
        return sample_invite

    return mocker.patch("app.invite_api_client.accept_invite", side_effect=_accept)


@pytest.fixture
def mock_add_user_to_service(mocker, service_one, api_user_active):
    def _add_user(service_id, user_id, permissions, folder_permissions):
        return

    return mocker.patch(
        "app.user_api_client.add_user_to_service", side_effect=_add_user
    )


@pytest.fixture
def mock_set_user_permissions(mocker):
    return mocker.patch("app.user_api_client.set_user_permissions", return_value=None)


@pytest.fixture
def mock_remove_user_from_service(mocker):
    return mocker.patch(
        "app.service_api_client.remove_user_from_service", return_value=None
    )


@pytest.fixture
def mock_get_template_statistics(mocker, service_one, fake_uuid):
    template = template_json(
        service_one["id"],
        fake_uuid,
        "Test template",
        "sms",
        "Something very interesting",
    )
    data = {
        "count": 1,
        "template_name": template["name"],
        "template_type": template["template_type"],
        "template_id": template["id"],
        "status": "delivered",
    }

    def _get_stats(service_id, limit_days=None):
        return [data]

    return mocker.patch(
        "app.template_statistics_client.get_template_statistics_for_service",
        side_effect=_get_stats,
    )


@pytest.fixture
def mock_get_monthly_template_usage(mocker, service_one, fake_uuid):
    def _stats(service_id, year):
        return [
            {
                "template_id": fake_uuid,
                "month": 10,
                "year": year,
                "count": 2,
                "name": "My first template",
                "type": "sms",
            }
        ]

    return mocker.patch(
        "app.template_statistics_client.get_monthly_template_usage_for_service",
        side_effect=_stats,
    )


@pytest.fixture
def mock_get_monthly_notification_stats(mocker, service_one, fake_uuid):
    def _stats(service_id, year):
        return {
            "data": {
                datetime.utcnow().strftime("%Y-%m"): {
                    "email": {
                        "sending": 1,
                        "delivered": 1,
                    },
                    "sms": {
                        "sending": 1,
                        "delivered": 1,
                    },
                }
            }
        }

    return mocker.patch(
        "app.service_api_client.get_monthly_notification_stats", side_effect=_stats
    )


@pytest.fixture
def mock_get_annual_usage_for_service(mocker, service_one, fake_uuid):
    def _get_usage(service_id, year=None):
        return [
            {
                "notification_type": "email",
                "chargeable_units": 1000,
                "notifications_sent": 1000,
                "charged_units": 1000,
                "rate": 0.00,
                "cost": 0,
            },
            {
                "notification_type": "sms",
                "chargeable_units": 251500,
                "notifications_sent": 105000,
                "charged_units": 1500,
                "rate": 0.0165,
                "cost": 24.75,  # 250K free allowance
            },
            {
                "notification_type": "sms",
                "chargeable_units": 300,
                "notifications_sent": 300,
                "charged_units": 300,
                "rate": 0.017,
                "cost": 5.1,
            },
        ]

    return mocker.patch(
        "app.billing_api_client.get_annual_usage_for_service", side_effect=_get_usage
    )


@pytest.fixture
def mock_get_monthly_usage_for_service(mocker):
    def _get_usage(service_id, year):
        return [
            {
                "month": "March",
                "notification_type": "sms",
                "rate": 0.017,
                "chargeable_units": 1230,
                "notifications_sent": 1234,
                "charged_units": 1230,
                "free_allowance_used": 0,
                "cost": 20.91,
            },
            {
                "month": "February",
                "notification_type": "sms",
                "rate": 0.017,
                "chargeable_units": 33,
                "notifications_sent": 1234,
                "charged_units": 33,
                "free_allowance_used": 0,
                "cost": 0.561,
            },
            {
                "month": "February",
                "notification_type": "sms",
                "rate": 0.0165,
                "chargeable_units": 1100,
                "notifications_sent": 1234,
                "charged_units": 960,
                "free_allowance_used": 140,
                "cost": 15.84,
            },
            {
                "month": "October",
                "notification_type": "sms",
                "rate": 0.017,
                "chargeable_units": 249860,
                "notifications_sent": 1234,
                "charged_units": 0,
                "free_allowance_used": 249860,
                "cost": 0,
            },
        ]

    return mocker.patch(
        "app.billing_api_client.get_monthly_usage_for_service", side_effect=_get_usage
    )


@pytest.fixture
def mock_get_annual_usage_for_service_in_future(mocker, service_one, fake_uuid):
    def _get_usage(service_id, year=None):
        return [
            {
                "notification_type": "sms",
                "chargeable_units": 0,
                "notifications_sent": 0,
                "charged_units": 0,
                "rate": 0.0158,
                "cost": 0,
            },
            {
                "notification_type": "email",
                "chargeable_units": 0,
                "notifications_sent": 0,
                "charged_units": 0,
                "rate": 0.0,
                "cost": 0,
            },
        ]

    return mocker.patch(
        "app.billing_api_client.get_annual_usage_for_service", side_effect=_get_usage
    )


@pytest.fixture
def mock_get_monthly_usage_for_service_in_future(mocker):
    def _get_usage(service_id, year):
        return []

    return mocker.patch(
        "app.billing_api_client.get_monthly_usage_for_service", side_effect=_get_usage
    )


@pytest.fixture
def mock_events(mocker):
    def _create_event(event_type, event_data):
        return {"some": "data"}

    return mocker.patch("app.events_api_client.create_event", side_effect=_create_event)


@pytest.fixture
def mock_send_already_registered_email(mocker):
    return mocker.patch("app.user_api_client.send_already_registered_email")


@pytest.fixture
def mock_get_guest_list(mocker):
    def _get_guest_list(service_id):
        return {
            "email_addresses": ["test@example.com"],
            "phone_numbers": ["2028675300"],
        }

    return mocker.patch(
        "app.service_api_client.get_guest_list", side_effect=_get_guest_list
    )


@pytest.fixture
def mock_update_guest_list(mocker):
    return mocker.patch("app.service_api_client.update_guest_list")


@pytest.fixture
def mock_reset_failed_login_count(mocker):
    return mocker.patch("app.user_api_client.reset_failed_login_count")


@pytest.fixture
def mock_get_notification(mocker):
    def _get_notification(
        service_id,
        notification_id,
    ):
        noti = notification_json(service_id, rows=1, personalisation={"name": "Jo"})[
            "notifications"
        ][0]

        noti["id"] = notification_id
        noti["created_by"] = {
            "id": fake_uuid,
            "name": "Test User",
            "email_address": "test@user.gsa.gov",
        }
        noti["template"] = template_json(
            service_id,
            "5407f4db-51c7-4150-8758-35412d42186a",
            content="hello ((name))",
            subject="blah",
            redact_personalisation=False,
            name="sample template",
        )
        return noti

    return mocker.patch(
        "app.notification_api_client.get_notification", side_effect=_get_notification
    )


@pytest.fixture
def mock_send_notification(mocker, fake_uuid):
    def _send_notification(
        service_id, *, template_id, recipient, personalisation, sender_id
    ):
        return {"id": fake_uuid}

    return mocker.patch(
        "app.notification_api_client.send_notification", side_effect=_send_notification
    )


@pytest.fixture
def client(notify_admin):
    """
    Do not use this fixture directly – use `client_request` instead
    """
    with notify_admin.test_request_context(), notify_admin.test_client() as client:
        client.allow_subdomain_redirects = True
        yield client


@pytest.fixture
def logged_in_client(
    client, active_user_with_permissions, mocker, service_one, mock_login
):
    """
    Do not use this fixture directly – use `client_request` instead
    """
    client.login(active_user_with_permissions, mocker, service_one)
    return client


@pytest.fixture
def _os_environ():
    """
    clear os.environ, and restore it after the test runs
    """
    # for use whenever you expect code to edit environment variables
    old_env = os.environ.copy()
    os.environ.clear()
    yield
    for k, v in old_env.items():
        os.environ[k] = v


@pytest.fixture  # noqa (C901 too complex)
def client_request(logged_in_client, mocker, service_one):  # noqa (C901 too complex)
    def _get(mocker):
        return {"count": 0}

    mocker.patch("app.service_api_client.get_service_statistics")

    mocker.patch(
        "app.service_api_client.get_global_notification_count", side_effect=_get
    )

    mocker.patch(
        "app.billing_api_client.create_or_update_free_sms_fragment_limit", autospec=True
    )

    mocker.patch("app.billing_api_client.get_monthly_usage_for_service", autospec=True)

    class ClientRequest:
        @staticmethod
        @contextmanager
        def session_transaction():
            with logged_in_client.session_transaction() as session:
                yield session

        @staticmethod
        def login(user, service=service_one):
            logged_in_client.login(user, mocker, service)

        @staticmethod
        def logout():
            logged_in_client.logout(None)

        @staticmethod
        def get(
            endpoint,
            _expected_status=200,
            _follow_redirects=False,
            _expected_redirect=None,
            _test_page_title=True,
            _test_for_elements_without_class=True,
            _optional_args="",
            **endpoint_kwargs,
        ):
            return ClientRequest.get_url(
                url_for(endpoint, **(endpoint_kwargs or {})) + _optional_args,
                _expected_status=_expected_status,
                _follow_redirects=_follow_redirects,
                _expected_redirect=_expected_redirect,
                _test_page_title=_test_page_title,
                _test_for_elements_without_class=_test_for_elements_without_class,
            )

        @staticmethod
        def get_url(
            url,
            _expected_status=200,
            _follow_redirects=False,
            _expected_redirect=None,
            _test_page_title=True,
            _test_for_elements_without_class=True,
            **endpoint_kwargs,
        ):
            resp = logged_in_client.get(
                url,
                follow_redirects=_follow_redirects,
            )

            if _expected_redirect and _expected_status == 200:
                _expected_status = 302

            assert resp.status_code == _expected_status, resp.location

            if _expected_redirect:
                assert resp.location == _expected_redirect

            page = BeautifulSoup(resp.data.decode("utf-8"), "html.parser")
            if _test_page_title:
                count_of_h1s = len(page.select("h1"))
                if count_of_h1s != 1:
                    raise AssertionError(
                        "Page should have one H1 ({} found)".format(count_of_h1s)
                    )
                page_title, h1 = (
                    normalize_spaces(page.find(selector).text)
                    for selector in ("title", "h1")
                )
                if not normalize_spaces(page_title).startswith(h1):
                    raise AssertionError(
                        "Page title ‘{}’ does not start with H1 ‘{}’".format(
                            page_title, h1
                        )
                    )
            return page

        @staticmethod
        def post(
            endpoint,
            _data=None,
            _expected_status=None,
            _follow_redirects=False,
            _expected_redirect=None,
            _content_type=None,
            **endpoint_kwargs,
        ):
            return ClientRequest.post_url(
                url_for(endpoint, **(endpoint_kwargs or {})),
                _data=_data,
                _expected_status=_expected_status,
                _follow_redirects=_follow_redirects,
                _expected_redirect=_expected_redirect,
                _content_type=_content_type,
            )

        @staticmethod
        def post_url(
            url,
            _data=None,
            _expected_status=None,
            _follow_redirects=False,
            _expected_redirect=None,
            _content_type=None,
        ):
            if _expected_status is None:
                _expected_status = 200 if _follow_redirects else 302
            post_kwargs = {}
            if _content_type:
                post_kwargs.update(content_type=_content_type)
            resp = logged_in_client.post(
                url, data=_data, follow_redirects=_follow_redirects, **post_kwargs
            )
            assert resp.status_code == _expected_status
            if _expected_redirect:
                assert_url_expected(resp.location, _expected_redirect)

            return BeautifulSoup(resp.data.decode("utf-8"), "html.parser")

        @staticmethod
        def get_response(
            endpoint, _expected_status=200, _optional_args="", **endpoint_kwargs
        ):
            return ClientRequest.get_response_from_url(
                url_for(endpoint, **(endpoint_kwargs or {})) + _optional_args,
                _expected_status=_expected_status,
            )

        @staticmethod
        def get_response_from_url(
            url,
            _expected_status=200,
        ):
            resp = logged_in_client.get(url)
            assert resp.status_code == _expected_status
            return resp

        @staticmethod
        def post_response(
            endpoint,
            _data=None,
            _expected_status=302,
            _optional_args="",
            _content_type=None,
            **endpoint_kwargs,
        ):
            return ClientRequest.post_response_from_url(
                url_for(endpoint, **(endpoint_kwargs or {})) + _optional_args,
                _data=_data,
                _content_type=_content_type,
                _expected_status=_expected_status,
            )

        @staticmethod
        def post_response_from_url(
            url,
            _data=None,
            _expected_status=302,
            _content_type=None,
        ):
            post_kwargs = {}
            if _content_type:
                post_kwargs.update(content_type=_content_type)
            resp = logged_in_client.post(url, data=_data, **post_kwargs)
            assert resp.status_code == _expected_status
            return resp

    return ClientRequest


def normalize_spaces(input):
    if isinstance(input, str):
        return " ".join(input.split())
    return normalize_spaces(" ".join(item.text for item in input))


@pytest.fixture
def mock_get_service_data_retention(mocker):
    data = {
        "id": str(sample_uuid()),
        "service_id": str(sample_uuid()),
        "service_name": "service name",
        "notification_type": "email",
        "days_of_retention": 7,
        "created_at": datetime.now(),
        "updated_at": None,
    }
    return mocker.patch(
        "app.service_api_client.get_service_data_retention", return_value=[data]
    )


@pytest.fixture
def mock_create_service_data_retention(mocker):
    return mocker.patch("app.service_api_client.create_service_data_retention")


@pytest.fixture
def mock_update_service_data_retention(mocker):
    return mocker.patch("app.service_api_client.update_service_data_retention")


@pytest.fixture
def mock_get_free_sms_fragment_limit(mocker):
    sample_limit = 250000
    return mocker.patch(
        "app.billing_api_client.get_free_sms_fragment_limit_for_year",
        return_value=sample_limit,
    )


@pytest.fixture
def mock_create_or_update_free_sms_fragment_limit(mocker):
    sample_limit = 250000
    return mocker.patch(
        "app.billing_api_client.create_or_update_free_sms_fragment_limit",
        return_value=sample_limit,
    )


@contextmanager
def set_config(app, name, value):
    old_val = app.config.get(name)
    app.config[name] = value
    yield
    app.config[name] = old_val


@contextmanager
def set_config_values(app, dict):
    old_values = {}

    for key in dict:
        old_values[key] = app.config.get(key)
        app.config[key] = dict[key]

    yield

    for key in dict:
        app.config[key] = old_values[key]


@pytest.fixture
def valid_token(notify_admin, fake_uuid):
    return generate_token(
        json.dumps({"user_id": fake_uuid, "secret_code": "my secret"}),
        notify_admin.config["SECRET_KEY"],
        notify_admin.config["DANGEROUS_SALT"],
    )


@pytest.fixture
def mock_get_valid_service_inbound_api(mocker):
    def _get(service_id, inbound_api_id):
        return {
            "created_at": "2017-12-04T10:52:55.289026Z",
            "updated_by_id": fake_uuid,
            "id": inbound_api_id,
            "url": "https://hello3.gsa.gov",
            "service_id": service_id,
            "updated_at": "2017-12-04T11:28:42.575153Z",
        }

    return mocker.patch(
        "app.service_api_client.get_service_inbound_api", side_effect=_get
    )


@pytest.fixture
def mock_get_valid_service_callback_api(mocker):
    def _get(service_id, callback_api_id):
        return {
            "created_at": "2017-12-04T10:52:55.289026Z",
            "updated_by_id": fake_uuid,
            "id": callback_api_id,
            "url": "https://hello2.gsa.gov",
            "service_id": service_id,
            "updated_at": "2017-12-04T11:28:42.575153Z",
        }

    return mocker.patch(
        "app.service_api_client.get_service_callback_api", side_effect=_get
    )


@pytest.fixture
def mock_get_empty_service_inbound_api(mocker):
    return mocker.patch(
        "app.service_api_client.get_service_inbound_api",
        side_effect=lambda service_id, callback_api_id: None,
    )


@pytest.fixture
def mock_get_empty_service_callback_api(mocker):
    return mocker.patch(
        "app.service_api_client.get_service_callback_api",
        side_effect=lambda service_id, callback_api_id: None,
    )


@pytest.fixture
def mock_create_service_inbound_api(mocker):
    def _create_service_inbound_api(service_id, url, bearer_token, user_id):
        return

    return mocker.patch(
        "app.service_api_client.create_service_inbound_api",
        side_effect=_create_service_inbound_api,
    )


@pytest.fixture
def mock_update_service_inbound_api(mocker):
    def _update_service_inbound_api(
        service_id, url, bearer_token, user_id, inbound_api_id
    ):
        return

    return mocker.patch(
        "app.service_api_client.update_service_inbound_api",
        side_effect=_update_service_inbound_api,
    )


@pytest.fixture
def mock_create_service_callback_api(mocker):
    def _create_service_callback_api(service_id, url, bearer_token, user_id):
        return

    return mocker.patch(
        "app.service_api_client.create_service_callback_api",
        side_effect=_create_service_callback_api,
    )


@pytest.fixture
def mock_update_service_callback_api(mocker):
    def _update_service_callback_api(
        service_id, url, bearer_token, user_id, callback_api_id
    ):
        return

    return mocker.patch(
        "app.service_api_client.update_service_callback_api",
        side_effect=_update_service_callback_api,
    )


@pytest.fixture
def organization_one(api_user_active):
    return organization_json(
        ORGANISATION_ID, "organization one", [api_user_active["id"]]
    )


@pytest.fixture
def mock_get_organizations(mocker):
    def _get_organizations():
        return [
            organization_json("7aa5d4e9-4385-4488-a489-07812ba13383", "Org 1"),
            organization_json("7aa5d4e9-4385-4488-a489-07812ba13384", "Org 2"),
            organization_json("7aa5d4e9-4385-4488-a489-07812ba13385", "Org 3"),
        ]

    mocker.patch(
        "app.models.organization.AllOrganizations.client_method",
        side_effect=_get_organizations,
    )

    return mocker.patch(
        "app.notify_client.organizations_api_client.organizations_client.get_organizations",
        side_effect=_get_organizations,
    )


@pytest.fixture
def mock_get_organizations_with_unusual_domains(mocker):
    def _get_organizations():
        return [
            organization_json(
                "7aa5d4e9-4385-4488-a489-07812ba13383",
                "Org 1",
                domains=[
                    "ldquo.net",
                    "rdquo.net",
                    "lsquo.net",
                    "rsquo.net",
                ],
            ),
        ]

    return mocker.patch(
        "app.organizations_client.get_organizations", side_effect=_get_organizations
    )


@pytest.fixture
def mock_get_organization(mocker):
    def _get_organization(org_id):
        return organization_json(
            org_id,
            {
                "o1": "Org 1",
                "o2": "Org 2",
                "o3": "Org 3",
            }.get(org_id, "Test organization"),
        )

    return mocker.patch(
        "app.organizations_client.get_organization", side_effect=_get_organization
    )


@pytest.fixture
def mock_get_organization_by_domain(mocker):
    def _get_organization_by_domain(domain):
        return organization_json(ORGANISATION_ID)

    return mocker.patch(
        "app.organizations_client.get_organization_by_domain",
        side_effect=_get_organization_by_domain,
    )


@pytest.fixture
def mock_get_no_organization_by_domain(mocker):
    return mocker.patch(
        "app.organizations_client.get_organization_by_domain",
        return_value=None,
    )


@pytest.fixture
def mock_get_service_organization(
    mocker,
    mock_get_organization,
):
    return mocker.patch(
        "app.models.service.Service.organization_id",
        new_callable=PropertyMock,
        return_value=ORGANISATION_ID,
    )


@pytest.fixture
def mock_update_service_organization(mocker):
    def _update_service_organization(service_id, org_id):
        return

    return mocker.patch(
        "app.organizations_client.update_service_organization",
        side_effect=_update_service_organization,
    )


def _get_organization_services(organization_id):
    if organization_id == "o1":
        return [
            service_json("12345", "service one", restricted=False),
            service_json("67890", "service two"),
            service_json("abcde", "service three"),
        ]
    if organization_id == "o2":
        return [
            service_json("12345", "service one (org 2)", restricted=False),
            service_json("67890", "service two (org 2)", restricted=False),
            service_json("abcde", "service three"),
        ]
    return [
        service_json("12345", "service one"),
        service_json("67890", "service two"),
        service_json(SERVICE_ONE_ID, "service one", [sample_uuid()]),
    ]


@pytest.fixture
def mock_get_organization_services(mocker, api_user_active):
    return mocker.patch(
        "app.organizations_client.get_organization_services",
        side_effect=_get_organization_services,
    )


@pytest.fixture
def mock_get_users_for_organization(mocker):
    def _get_users_for_organization(org_id):
        return [
            user_json(id_="1234", name="Test User 1"),
            user_json(id_="5678", name="Test User 2", email_address="testt@gsa.gov"),
        ]

    return mocker.patch(
        "app.models.user.OrganizationUsers.client_method",
        side_effect=_get_users_for_organization,
    )


@pytest.fixture
def mock_get_invited_users_for_organization(mocker, sample_org_invite):
    def _get_invited_invited_users_for_organization(org_id):
        return [sample_org_invite]

    return mocker.patch(
        "app.models.user.OrganizationInvitedUsers.client_method",
        side_effect=_get_invited_invited_users_for_organization,
    )


@pytest.fixture
def sample_org_invite(mocker, organization_one):
    id_ = str(UUID(bytes=b"sample_org_invit", version=4))
    invited_by = organization_one["users"][0]
    email_address = "invited_user@test.gsa.gov"
    organization = organization_one["id"]
    created_at = str(datetime.utcnow())
    status = "pending"

    return org_invite_json(
        id_, invited_by, organization, email_address, created_at, status
    )


@pytest.fixture
def mock_get_invites_for_organization(mocker, sample_org_invite):
    def _get_org_invites(org_id):
        data = []
        for i in range(0, 5):
            invite = copy.copy(sample_org_invite)
            invite["email_address"] = "user_{}@testnotify.gsa.gov".format(i)
            data.append(invite)
        return data

    return mocker.patch(
        "app.models.user.OrganizationInvitedUsers.client_method",
        side_effect=_get_org_invites,
    )


@pytest.fixture
def mock_check_org_invite_token(mocker, sample_org_invite):
    def _check_org_token(token):
        return sample_org_invite

    return mocker.patch(
        "app.org_invite_api_client.check_token", side_effect=_check_org_token
    )


@pytest.fixture
def mock_check_org_cancelled_invite_token(mocker, sample_org_invite):
    def _check_org_token(token):
        sample_org_invite["status"] = "cancelled"
        return sample_org_invite

    return mocker.patch(
        "app.org_invite_api_client.check_token", side_effect=_check_org_token
    )


@pytest.fixture
def mock_check_org_accepted_invite_token(mocker, sample_org_invite):
    sample_org_invite["status"] = "accepted"

    def _check_org_token(token):
        return sample_org_invite

    return mocker.patch(
        "app.org_invite_api_client.check_token", return_value=sample_org_invite
    )


@pytest.fixture
def mock_accept_org_invite(mocker, sample_org_invite):
    def _accept(organization_id, invite_id):
        return sample_org_invite

    return mocker.patch("app.org_invite_api_client.accept_invite", side_effect=_accept)


@pytest.fixture
def mock_add_user_to_organization(mocker, organization_one, api_user_active):
    def _add_user(organization_id, user_id):
        return api_user_active

    return mocker.patch(
        "app.user_api_client.add_user_to_organization", side_effect=_add_user
    )


@pytest.fixture
def mock_update_organization(mocker):
    def _update_org(org, **kwargs):
        return

    return mocker.patch(
        "app.organizations_client.update_organization", side_effect=_update_org
    )


@pytest.fixture
def mock_get_organizations_and_services_for_user(
    mocker, organization_one, api_user_active
):
    def _get_orgs_and_services(user_id):
        return {"organizations": [], "services": []}

    return mocker.patch(
        "app.user_api_client.get_organizations_and_services_for_user",
        side_effect=_get_orgs_and_services,
    )


@pytest.fixture
def mock_get_non_empty_organizations_and_services_for_user(
    mocker, organization_one, api_user_active
):
    def _make_services(name, trial_mode=False):
        return [
            {
                "name": "{} {}".format(name, i),
                "id": SERVICE_TWO_ID,
                "restricted": trial_mode,
                "organization": None,
            }
            for i in range(1, 3)
        ]

    def _get_orgs_and_services(user_id):
        return {
            "organizations": [
                {
                    "name": "Org 1",
                    "id": "o1",
                    "count_of_live_services": 1,
                },
                {
                    "name": "Org 2",
                    "id": "o2",
                    "count_of_live_services": 2,
                },
                {
                    "name": "Org 3",
                    "id": "o3",
                    "count_of_live_services": 0,
                },
            ],
            "services": (
                _get_organization_services("o1")
                + _get_organization_services("o2")
                + _make_services("Service")
            ),
        }

    return mocker.patch(
        "app.user_api_client.get_organizations_and_services_for_user",
        side_effect=_get_orgs_and_services,
    )


@pytest.fixture
def mock_get_just_services_for_user(mocker, organization_one, api_user_active):
    def _make_services(name, trial_mode=False):
        return [
            {
                "name": "{} {}".format(name, i + 1),
                "id": id,
                "restricted": trial_mode,
                "organization": None,
            }
            for i, id in enumerate([SERVICE_TWO_ID, SERVICE_ONE_ID])
        ]

    def _get_orgs_and_services(user_id):
        return {
            "organizations": [],
            "services": _make_services("Service"),
        }

    return mocker.patch(
        "app.user_api_client.get_organizations_and_services_for_user",
        side_effect=_get_orgs_and_services,
    )


@pytest.fixture
def mock_get_empty_organizations_and_one_service_for_user(
    mocker, organization_one, api_user_active
):
    def _get_orgs_and_services(user_id):
        return {
            "organizations": [],
            "services": [
                {
                    "name": "Only service",
                    "id": SERVICE_TWO_ID,
                    "restricted": True,
                }
            ],
        }

    return mocker.patch(
        "app.user_api_client.get_organizations_and_services_for_user",
        side_effect=_get_orgs_and_services,
    )


@pytest.fixture
def mock_create_event(mocker):
    """
    This should be used whenever your code is calling `flask_login.login_user`
    """

    def _add_event(event_type, event_data):
        return

    return mocker.patch("app.events_api_client.create_event", side_effect=_add_event)


def url_for_endpoint_with_token(endpoint, token, next=None):
    token = token.replace("%2E", ".")
    return url_for(endpoint, token=token, next=next)


@pytest.fixture
def mock_get_template_folders(mocker):
    return mocker.patch(
        "app.template_folder_api_client.get_template_folders", return_value=[]
    )


@pytest.fixture
def mock_move_to_template_folder(mocker):
    return mocker.patch("app.template_folder_api_client.move_to_folder")


@pytest.fixture
def mock_create_template_folder(mocker):
    return mocker.patch(
        "app.template_folder_api_client.create_template_folder",
        return_value=sample_uuid(),
    )


@pytest.fixture
def mock_get_service_and_organization_counts(mocker):
    return mocker.patch(
        "app.status_api_client.get_count_of_live_services_and_organizations",
        return_value={
            "organizations": 111,
            "services": 9999,
        },
    )


@pytest.fixture
def mock_get_service_history(mocker):
    return mocker.patch(
        "app.service_api_client.get_service_history",
        return_value={
            "service_history": [
                {
                    "name": "Example service",
                    "created_at": "2010-10-10T06:01:01.000000Z",
                    "updated_at": None,
                    "created_by_id": uuid4(),
                },
                {
                    "name": "Before lunch",
                    "created_at": "2010-10-10T06:01:01.000000Z",
                    "updated_at": "2012-12-12T17:12:12.000000Z",
                    "created_by_id": sample_uuid(),
                },
                {
                    "name": "After lunch",
                    "created_at": "2010-10-10T06:01:01.000000Z",
                    "updated_at": "2012-12-12T18:13:13.000000Z",
                    "created_by_id": sample_uuid(),
                },
            ],
            "api_key_history": [
                {
                    "name": "Good key",
                    "updated_at": None,
                    "created_at": "2010-10-10T15:10:10.000000Z",
                    "created_by_id": sample_uuid(),
                },
                {
                    "name": "Bad key",
                    "updated_at": "2012-11-11T17:12:12.000000Z",
                    "created_at": "2011-11-11T16:11:11.000000Z",
                    "created_by_id": sample_uuid(),
                },
                {
                    "name": "Bad key",
                    "updated_at": None,
                    "created_at": "2011-11-11T16:11:11.000000Z",
                    "created_by_id": sample_uuid(),
                },
                {
                    "name": "Key event returned in non-chronological order",
                    "updated_at": None,
                    "created_at": "2010-10-10T14:09:09.000000Z",
                    "created_by_id": sample_uuid(),
                },
            ],
            "events": [],
        },
    )


def create_api_user_active(with_unique_id=False):
    return create_user(
        id=str(uuid4()) if with_unique_id else sample_uuid(),
    )


def create_active_user_empty_permissions(with_unique_id=False):
    return create_service_one_user(
        id=str(uuid4()) if with_unique_id else sample_uuid(),
        name="Test User With Empty Permissions",
    )


def create_active_user_with_permissions(with_unique_id=False):
    return create_service_one_admin(
        id=str(uuid4()) if with_unique_id else sample_uuid(),
    )


def create_active_user_view_permissions(with_unique_id=False):
    return create_service_one_user(
        id=str(uuid4()) if with_unique_id else sample_uuid(),
        name="Test User With Permissions",
        permissions={SERVICE_ONE_ID: [ServicePermission.VIEW_ACTIVITY]},
    )


def create_active_caseworking_user(with_unique_id=False):
    return create_user(
        id=str(uuid4()) if with_unique_id else sample_uuid(),
        email_address="caseworker@example.gsa.gov",
        permissions={
            SERVICE_ONE_ID: [
                ServicePermission.SEND_TEXTS,
                ServicePermission.SEND_EMAILS,
            ]
        },
        services=[SERVICE_ONE_ID],
    )


def create_active_user_no_api_key_permission(with_unique_id=False):
    return create_service_one_user(
        id=str(uuid4()) if with_unique_id else sample_uuid(),
        name="Test User With Permissions",
        permissions={
            SERVICE_ONE_ID: [
                ServicePermission.MANAGE_TEMPLATES,
                ServicePermission.MANAGE_SETTINGS,
                ServicePermission.MANAGE_USERS,
                ServicePermission.VIEW_ACTIVITY,
            ]
        },
    )


def create_active_user_no_settings_permission(with_unique_id=False):
    return create_service_one_user(
        id=str(uuid4()) if with_unique_id else sample_uuid(),
        name="Test User With Permissions",
        permissions={
            SERVICE_ONE_ID: [
                ServicePermission.MANAGE_TEMPLATES,
                "manage_api_keys",
                ServicePermission.VIEW_ACTIVITY,
            ]
        },
    )


def create_active_user_manage_template_permissions(with_unique_id=False):
    return create_service_one_user(
        id=str(uuid4()) if with_unique_id else sample_uuid(),
        name="Test User With Permissions",
        permissions={
            SERVICE_ONE_ID: [
                ServicePermission.MANAGE_TEMPLATES,
                ServicePermission.VIEW_ACTIVITY,
            ]
        },
    )


def create_platform_admin_user(with_unique_id=False, permissions=None):
    return create_user(
        id=str(uuid4()) if with_unique_id else sample_uuid(),
        name="Platform admin user",
        email_address="platform@admin.gsa.gov",
        permissions=permissions or {},
        platform_admin=True,
    )


def create_service_one_admin(**overrides):
    user_data = {
        "permissions": {
            SERVICE_ONE_ID: [
                ServicePermission.SEND_TEXTS,
                ServicePermission.SEND_EMAILS,
                ServicePermission.MANAGE_USERS,
                ServicePermission.MANAGE_TEMPLATES,
                ServicePermission.MANAGE_SETTINGS,
                "manage_api_keys",
                ServicePermission.VIEW_ACTIVITY,
            ]
        },
    }
    user_data.update(overrides)
    return create_service_one_user(**user_data)


def create_service_one_user(**overrides):
    user_data = {
        "organizations": [ORGANISATION_ID],
        "services": [SERVICE_ONE_ID],
    }
    user_data.update(overrides)
    return create_user(**user_data)


def create_user(**overrides):
    user_data = {
        "name": "Test User",
        "password": "somepassword",
        "email_address": "test@user.gsa.gov",
        "mobile_number": "202-867-5303",
        "state": "active",
        "failed_login_count": 0,
        "permissions": {},
        "platform_admin": False,
        "auth_type": "sms_auth",
        "password_changed_at": str(datetime.utcnow()),
        "services": [],
        "organizations": [],
        "current_session_id": None,
        "logged_in_at": None,
        "email_access_validated_at": None,
    }
    user_data.update(overrides)
    return user_data


def create_reply_to_email_address(
    id_="1234",
    service_id="abcd",
    email_address="test@example.com",
    is_default=True,
    created_at=None,
    updated_at=None,
):
    return {
        "id": id_,
        "service_id": service_id,
        "email_address": email_address,
        "is_default": is_default,
        "created_at": created_at,
        "updated_at": updated_at,
    }


def create_multiple_email_reply_to_addresses(service_id="abcd"):
    return [
        {
            "id": "1234",
            "service_id": service_id,
            "email_address": "test@example.com",
            "is_default": True,
            "created_at": datetime.utcnow(),
            "updated_at": None,
        },
        {
            "id": "5678",
            "service_id": service_id,
            "email_address": "test2@example.com",
            "is_default": False,
            "created_at": datetime.utcnow(),
            "updated_at": None,
        },
        {
            "id": "9457",
            "service_id": service_id,
            "email_address": "test3@example.com",
            "is_default": False,
            "created_at": datetime.utcnow(),
            "updated_at": None,
        },
    ]


def create_sms_sender(
    id_="1234",
    service_id="abcd",
    sms_sender="GOVUK",
    is_default=True,
    created_at=None,
    inbound_number_id=None,
    updated_at=None,
):
    return {
        "id": id_,
        "service_id": service_id,
        "sms_sender": sms_sender,
        "is_default": is_default,
        "created_at": created_at,
        "inbound_number_id": inbound_number_id,
        "updated_at": updated_at,
    }


def create_multiple_sms_senders(
    service_id="abcd",
    isdefault1=True,
    isdefault2=False,
    isdefault3=False,
    isdefault4=False,
):
    return [
        {
            "id": "1234",
            "service_id": service_id,
            "sms_sender": "Example",
            "is_default": isdefault1,
            "created_at": datetime.utcnow(),
            "inbound_number_id": "1234",
            "updated_at": None,
        },
        {
            "id": "5678",
            "service_id": service_id,
            "sms_sender": "Example 2",
            "is_default": isdefault2,
            "created_at": datetime.utcnow(),
            "inbound_number_id": None,
            "updated_at": None,
        },
        {
            "id": "9457",
            "service_id": service_id,
            "sms_sender": "US Notify",
            "is_default": isdefault3,
            "created_at": datetime.utcnow(),
            "inbound_number_id": None,
            "updated_at": None,
        },
        {
            "id": "9897",
            "service_id": service_id,
            "sms_sender": "Notify.gov",
            "is_default": isdefault4,
            "created_at": datetime.utcnow(),
            "inbound_number_id": None,
            "updated_at": None,
        },
    ]


def create_notification(
    notifification_id=None,
    service_id="abcd",
    notification_status="delivered",
    redact_personalisation=False,
    template_type=None,
    template_name="sample template",
    key_type=None,
    sent_one_off=True,
    reply_to_text=None,
):
    noti = notification_json(
        service_id,
        rows=1,
        status=notification_status,
        template_type=template_type,
        reply_to_text=reply_to_text,
    )["notifications"][0]

    noti["id"] = notifification_id or sample_uuid()
    if sent_one_off:
        noti["created_by"] = {
            "id": sample_uuid(),
            "name": "Test User",
            "email_address": "test@user.gsa.gov",
        }
    noti["personalisation"] = {"name": "Jo"}
    noti["template"] = template_json(
        service_id,
        "5407f4db-51c7-4150-8758-35412d42186a",
        content="hello ((name))",
        subject="blah",
        redact_personalisation=redact_personalisation,
        type_=template_type,
        name=template_name,
    )
    if key_type:
        noti["key_type"] = key_type
    return noti


def create_notifications(
    service_id=SERVICE_ONE_ID,
    template_type="sms",
    rows=5,
    status=None,
    subject="subject",
    content="content",
    client_reference=None,
    personalisation=None,
    redact_personalisation=False,
    to=None,
):
    template = template_json(
        service_id,
        id_=str(generate_uuid()),
        type_=template_type,
        subject=subject,
        content=content,
        redact_personalisation=redact_personalisation,
    )

    return notification_json(
        service_id,
        template=template,
        rows=rows,
        personalisation=personalisation,
        template_type=template_type,
        client_reference=client_reference,
        status=status,
        created_by_name="Firstname Lastname",
        to=to,
    )


def create_folder(id):
    return {"id": id, "parent_id": None, "name": "My folder"}


def create_template(
    service_id=SERVICE_ONE_ID,
    template_id=None,
    template_type="sms",
    name="sample template",
    content="Template content",
    subject="Template subject",
    redact_personalisation=False,
    folder=None,
):
    return template_json(
        service_id=service_id,
        id_=template_id or str(generate_uuid()),
        name=name,
        type_=template_type,
        content=content,
        subject=subject,
        redact_personalisation=redact_personalisation,
        folder=folder,
    )


@pytest.fixture
def mock_get_invited_user_by_id(mocker, sample_invite):
    def _get(invited_user_id):
        return sample_invite

    return mocker.patch(
        "app.invite_api_client.get_invited_user",
        side_effect=_get,
    )


@pytest.fixture
def mock_get_invited_org_user_by_id(mocker, sample_org_invite):
    def _get(invited_org_user_id):
        return sample_org_invite

    return mocker.patch(
        "app.org_invite_api_client.get_invited_user",
        side_effect=_get,
    )


@pytest.fixture
def fake_markdown_file():
    input = "#Test"
    return input


@pytest.fixture
def fake_jinja_template():
    input = "{% if True %}True{% endif %}"
    return input


@pytest.fixture
def fake_soup_template():
    input = "<h1>Test</h1>"
    return input
