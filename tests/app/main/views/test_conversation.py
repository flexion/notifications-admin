import json
import re
from datetime import datetime
from unittest.mock import Mock

import pytest
from flask import url_for
from freezegun import freeze_time

from app.main.views.conversation import get_user_number
from notifications_python_client.errors import HTTPError
from tests.conftest import (
    SERVICE_ONE_ID,
    _template,
    create_notifications,
    normalize_spaces,
)

INV_PARENT_FOLDER_ID = "7e979e79-d970-43a5-ac69-b625a8d147b0"
VIS_PARENT_FOLDER_ID = "bbbb222b-2b22-2b22-222b-b222b22b2222"


def test_get_user_phone_number_when_only_inbound_exists(mocker):
    mock_get_inbound_sms = mocker.patch(
        "app.main.views.conversation.service_api_client.get_inbound_sms_by_id",
        return_value={"user_number": "2028675305", "notify_number": "2028675309"},
    )
    mock_get_notification = mocker.patch(
        "app.main.views.conversation.notification_api_client.get_notification",
        side_effect=HTTPError(response=Mock(status_code=404)),
    )
    assert get_user_number("service", "notification") == "(202) 867-5305"
    mock_get_inbound_sms.assert_called_once_with("service", "notification")
    assert mock_get_notification.called is False


def test_get_user_phone_number_when_only_outbound_exists(mocker):
    mock_get_inbound_sms = mocker.patch(
        "app.main.views.conversation.service_api_client.get_inbound_sms_by_id",
        side_effect=HTTPError(response=Mock(status_code=404)),
    )
    mock_get_notification = mocker.patch(
        "app.main.views.conversation.notification_api_client.get_notification",
        return_value={"to": "2028675309"},
    )
    assert get_user_number("service", "notification") == "(202) 867-5309"
    mock_get_inbound_sms.assert_called_once_with("service", "notification")
    mock_get_notification.assert_called_once_with("service", "notification")


def test_get_user_phone_number_raises_if_both_api_requests_fail(mocker):
    mock_get_inbound_sms = mocker.patch(
        "app.main.views.conversation.service_api_client.get_inbound_sms_by_id",
        side_effect=HTTPError(response=Mock(status_code=404)),
    )
    mock_get_notification = mocker.patch(
        "app.main.views.conversation.notification_api_client.get_notification",
        side_effect=HTTPError(response=Mock(status_code=404)),
    )
    with pytest.raises(HTTPError):
        get_user_number("service", "notification")
    mock_get_inbound_sms.assert_called_once_with("service", "notification")
    mock_get_notification.assert_called_once_with("service", "notification")


@pytest.mark.parametrize(
    ("outbound_redacted", "expected_outbound_content"),
    [
        (True, "Hello hidden"),
        (False, "Hello Jo"),
    ],
)
@freeze_time("2012-01-01 05:00:00")
def test_view_conversation(
    client_request,
    mocker,
    mock_get_inbound_sms_by_id_with_no_messages,
    mock_get_notification,
    fake_uuid,
    outbound_redacted,
    expected_outbound_content,
    mock_get_inbound_sms,
):
    notifications = create_notifications(
        content="Hello ((name))",
        personalisation={"name": "Jo"},
        redact_personalisation=outbound_redacted,
    )
    mock = mocker.patch(
        "app.notification_api_client.get_notifications_for_service",
        return_value=notifications,
    )

    page = client_request.get(
        "main.conversation",
        service_id=SERVICE_ONE_ID,
        notification_id=fake_uuid,
        _test_page_title=False,
    )

    assert normalize_spaces(page.select_one("title").text) == (
        "Received text message – service one – Notify.gov"
    )
    assert normalize_spaces(page.select_one("h1").text) == ("2021234567")

    messages = page.select(".sms-message-wrapper")
    statuses = page.select(".sms-message-status")

    assert len(messages) == 13
    assert len(statuses) == 13

    for index, expected in enumerate(
        [
            (
                "message-8",
                "yesterday at 14:59 America/New_York",
            ),
            (
                "message-7",
                "yesterday at 14:59 America/New_York",
            ),
            (
                "message-6",
                "yesterday at 16:59 America/New_York",
            ),
            (
                "message-5",
                "yesterday at 18:59 America/New_York",
            ),
            (
                "message-4",
                "yesterday at 20:59 America/New_York",
            ),
            (
                "message-3",
                "yesterday at 22:59 America/New_York",
            ),
            (
                "message-2",
                "yesterday at 22:59 America/New_York",
            ),
            (
                "message-1",
                "yesterday at 23:00 America/New_York",
            ),
            (
                expected_outbound_content,
                "yesterday at 00:00 America/New_York",
            ),
            (
                expected_outbound_content,
                "yesterday at 00:00 America/New_York",
            ),
            (
                expected_outbound_content,
                "yesterday at 00:00 America/New_York",
            ),
            (
                expected_outbound_content,
                "yesterday at 00:00 America/New_York",
            ),
            (
                expected_outbound_content,
                "yesterday at 00:00 America/New_York",
            ),
        ]
    ):
        assert (
            normalize_spaces(messages[index].text),
            normalize_spaces(statuses[index].text),
        ) == expected

    mock_get_inbound_sms.assert_called_once_with(
        SERVICE_ONE_ID, user_number="2021234567"
    )
    mock.assert_called_once_with(SERVICE_ONE_ID, to="2021234567", template_type="sms")


def test_view_conversation_updates(
    client_request,
    mocker,
    fake_uuid,
    mock_get_inbound_sms_by_id_with_no_messages,
    mock_get_notification,
):
    mocker.patch(
        "app.main.views.conversation.service_api_client.get_inbound_sms_by_id",
        side_effect=HTTPError(response=Mock(status_code=404)),
    )
    mock_get_partials = mocker.patch(
        "app.main.views.conversation.get_conversation_partials",
        return_value={"messages": "foo"},
    )

    response = client_request.get_response(
        "main.conversation_updates",
        service_id=SERVICE_ONE_ID,
        notification_id=fake_uuid,
    )

    assert json.loads(response.get_data(as_text=True)) == {"messages": "foo"}

    mock_get_partials.assert_called_once_with(SERVICE_ONE_ID, "2021234567")


@freeze_time("2012-01-01 00:00:00")
def test_view_conversation_with_empty_inbound(
    client_request,
    mocker,
    api_user_active,
    mock_get_inbound_sms_by_id_with_no_messages,
    mock_get_notification,
    mock_get_notifications_with_no_notifications,
    fake_uuid,
):
    mock_get_inbound_sms = mocker.patch(
        "app.main.views.conversation.service_api_client.get_inbound_sms",
        return_value={
            "has_next": False,
            "data": [
                {
                    "user_number": "2028675301",
                    "notify_number": "2028675309",
                    "content": "",
                    "created_at": datetime.utcnow().isoformat(),
                    "id": fake_uuid,
                }
            ],
        },
    )

    page = client_request.get(
        "main.conversation",
        service_id=SERVICE_ONE_ID,
        notification_id=fake_uuid,
        _test_page_title=False,
    )

    messages = page.select(".sms-message-wrapper")
    assert len(messages) == 1
    assert mock_get_inbound_sms.called is True


def test_conversation_links_to_reply(
    client_request,
    fake_uuid,
    mock_get_inbound_sms_by_id_with_no_messages,
    mock_get_notification,
    mock_get_notifications,
    mock_get_inbound_sms,
):
    page = client_request.get(
        "main.conversation",
        service_id=SERVICE_ONE_ID,
        notification_id=fake_uuid,
        _test_page_title=False,
    )

    assert page.select("main p")[-1].select_one("a")["href"] == (
        url_for(
            ".conversation_reply",
            service_id=SERVICE_ONE_ID,
            notification_id=fake_uuid,
        )
    )


def test_conversation_reply_shows_link_to_add_templates_if_service_has_no_templates(
    client_request,
    fake_uuid,
    mock_get_service_templates_when_no_templates_exist,
    mock_get_template_folders,
    active_user_with_permissions,
):
    page = client_request.get(
        "main.conversation_reply",
        service_id=SERVICE_ONE_ID,
        notification_id=fake_uuid,
    )
    page_text = page.find("p", class_="bottom-gutter").text
    link = page.find("a", text=re.compile("Add a new template"))["href"]

    assert (
        normalize_spaces(page_text)
        == "You need a template before you can send text messages."
    )
    assert link == url_for(
        "main.choose_template",
        service_id=SERVICE_ONE_ID,
        initial_state="add-new-template",
    )


def test_conversation_reply_shows_templates(
    client_request,
    fake_uuid,
    mocker,
    mock_get_template_folders,
    active_user_with_permissions,
    service_one,
):
    all_templates = {
        "data": [
            _template("sms", "sms_template_one", parent=INV_PARENT_FOLDER_ID),
            _template("sms", "sms_template_two"),
            _template("sms", "sms_template_three", parent=VIS_PARENT_FOLDER_ID),
        ]
    }
    mocker.patch(
        "app.service_api_client.get_service_templates", return_value=all_templates
    )
    mock_get_template_folders.return_value = [
        {
            "name": "Parent 1 - invisible",
            "id": INV_PARENT_FOLDER_ID,
            "parent_id": None,
            "users_with_permission": [],
        },
        {
            "name": "Parent 2 - visible",
            "id": VIS_PARENT_FOLDER_ID,
            "parent_id": None,
            "users_with_permission": [active_user_with_permissions["id"]],
        },
    ]
    page = client_request.get(
        "main.conversation_reply",
        service_id=SERVICE_ONE_ID,
        notification_id=fake_uuid,
    )

    link = page.select(".template-list-item-without-ancestors")
    assert normalize_spaces(link[0].text) == "Parent 2 - visible 1 template"
    assert normalize_spaces(link[1].text) == "sms_template_two Text message template"

    assert (
        link[0]
        .select_one("a")["href"]
        .startswith(
            url_for(
                "main.conversation_reply",
                service_id=SERVICE_ONE_ID,
                notification_id=fake_uuid,
                from_folder=VIS_PARENT_FOLDER_ID,
            )
        )
    )

    assert (
        link[1]
        .select_one("a")["href"]
        .startswith(
            url_for(
                "main.conversation_reply_with_template",
                service_id=SERVICE_ONE_ID,
                notification_id=fake_uuid,
                template_id="",
            )
        )
    )


def test_conversation_reply_shows_live_search(
    client_request,
    fake_uuid,
    mock_get_service_templates,
    mock_get_template_folders,
):
    page = client_request.get(
        "main.conversation_reply",
        service_id=SERVICE_ONE_ID,
        notification_id=fake_uuid,
    )

    assert page.select(".live-search")


def test_conversation_reply_redirects_with_phone_number_from_notification(
    client_request,
    fake_uuid,
    mock_get_inbound_sms_by_id_with_no_messages,
    mock_get_notification,
    mock_get_service_template,
):
    page = client_request.get(
        "main.conversation_reply_with_template",
        service_id=SERVICE_ONE_ID,
        notification_id=fake_uuid,
        template_id=fake_uuid,
        _follow_redirects=True,
    )

    for element, expected_text in [
        ("h1", "Select delivery time"),
        (".sms-message-recipient", "To: 2021234567"),
        (
            ".sms-message-wrapper",
            "service one: Template <em>content</em> with & entity",
        ),
    ]:
        assert normalize_spaces(page.select_one(element).text) == expected_text


def test_get_user_phone_number_when_not_a_standard_phone_number(mocker):
    mocker.patch(
        "app.main.views.conversation.service_api_client.get_inbound_sms_by_id",
        return_value={"user_number": "ALPHANUM3R1C", "notify_number": "2028675309"},
    )
    mocker.patch(
        "app.main.views.conversation.notification_api_client.get_notification",
        side_effect=HTTPError,
    )
    assert get_user_number("service", "notification") == "ALPHANUM3R1C"
