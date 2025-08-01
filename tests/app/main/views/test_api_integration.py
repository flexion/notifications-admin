import uuid
from collections import OrderedDict
from datetime import date
from unittest.mock import call

import pytest
from flask import url_for

from app.enums import ServicePermission
from app.formatters import format_datetime_table
from tests import sample_uuid, validate_route_permission
from tests.conftest import SERVICE_ONE_ID, normalize_spaces


def test_should_show_api_page(
    client_request,
    mock_login,
    api_user_active,
    mock_get_service,
    mock_has_permissions,
    mock_get_notifications,
):
    page = client_request.get(
        "main.api_integration",
        service_id=SERVICE_ONE_ID,
    )
    assert page.h1.string.strip() == "API integration"
    rows = page.find_all("details")
    assert len(rows) == 5
    for row in rows:
        assert (
            row.select("h3 .govuk-details__summary-text")[0].string.strip()
            == "2021234567"
        )


def test_should_show_api_page_with_lots_of_notifications(
    client_request,
    mock_login,
    api_user_active,
    mock_get_service,
    mock_has_permissions,
    mock_get_notifications_with_previous_next,
):
    page = client_request.get(
        "main.api_integration",
        service_id=SERVICE_ONE_ID,
    )
    rows = page.find_all("div", {"class": "api-notifications-item"})
    assert " ".join(rows[len(rows) - 1].text.split()) == (
        "Only showing the first 50 messages. Notify deletes messages after 7 days."
    )


def test_should_show_api_page_with_no_notifications(
    client_request,
    mock_login,
    api_user_active,
    mock_get_service,
    mock_has_permissions,
    mock_get_notifications_with_no_notifications,
):
    page = client_request.get(
        "main.api_integration",
        service_id=SERVICE_ONE_ID,
    )
    rows = page.find_all("div", {"class": "api-notifications-item"})
    assert (
        "When you send messages via the API they’ll appear here."
        in rows[len(rows) - 1].text.strip()
    )


def test_should_show_api_page_for_live_service(
    client_request,
    mock_login,
    api_user_active,
    mock_get_notifications,
    mock_get_live_service,
    mock_has_permissions,
):
    page = client_request.get("main.api_integration", service_id=uuid.uuid4())
    assert "Your service is in trial mode" not in page.find("main").text


def test_api_documentation_page_should_redirect(
    client_request, mock_login, api_user_active, mock_get_service, mock_has_permissions
):
    client_request.get(
        "main.api_documentation",
        service_id=SERVICE_ONE_ID,
        _expected_status=301,
        _expected_redirect=url_for(
            "main.documentation",
        ),
    )


def test_should_show_empty_api_keys_page(
    client_request,
    api_user_active,
    mock_login,
    mock_get_no_api_keys,
    mock_get_service,
    mock_has_permissions,
):
    client_request.login(api_user_active)
    page = client_request.get("main.api_keys", service_id=SERVICE_ONE_ID)

    assert "You have not created any API keys yet" in page.text
    assert "Create an API key" in page.text
    mock_get_no_api_keys.assert_called_once_with(SERVICE_ONE_ID)


def test_should_show_api_keys_page(
    client_request,
    mock_get_api_keys,
    fake_uuid,
):
    page = client_request.get("main.api_keys", service_id=SERVICE_ONE_ID)
    rows = [normalize_spaces(row.text) for row in page.select("main tr")]
    revoke_link = page.select_one("main tr a.usa-link.usa-link--destructive")

    assert rows[0] == "API keys Action"
    assert (
        rows[1]
        == f"another key name Revoked {format_datetime_table(date.fromtimestamp(0).isoformat())}"
    )
    assert rows[2] == "some key name Revoke some key name"

    assert normalize_spaces(revoke_link.text) == "Revoke some key name"
    assert revoke_link["href"] == url_for(
        "main.revoke_api_key",
        service_id=SERVICE_ONE_ID,
        key_id=fake_uuid,
    )

    mock_get_api_keys.assert_called_once_with(SERVICE_ONE_ID)


@pytest.mark.parametrize(
    ("restricted", "expected_options"),
    [
        (
            True,
            [
                (
                    "Live – sends to anyone",
                    "Not available because your service is in trial mode",
                ),
                "Team and guest list – limits who you can send to",
                "Test – pretends to send messages",
            ],
        ),
        (
            False,
            [
                "Live – sends to anyone",
                "Team and guest list – limits who you can send to",
                "Test – pretends to send messages",
            ],
        ),
    ],
)
def test_should_show_create_api_key_page(
    client_request,
    mocker,
    api_user_active,
    mock_get_api_keys,
    restricted,
    expected_options,
    service_one,
):
    service_one["restricted"] = restricted

    mocker.patch(
        "app.service_api_client.get_service", return_value={"data": service_one}
    )

    page = client_request.get("main.create_api_key", service_id=SERVICE_ONE_ID)

    for index, option in enumerate(expected_options):
        item = page.select(".usa-radio")[index]
        if type(option) is tuple:
            label = item.select_one(".usa-radio__label")
            hint = label.select_one(".usa-hint")
            # Get the label text without the hint text
            label_text = (
                label.text.replace(hint.text, "").strip() if hint else label.text
            )
            assert normalize_spaces(label_text) == option[0]
            assert normalize_spaces(hint.text) == option[1]
        else:
            assert normalize_spaces(item.select_one(".usa-radio__label").text) == option


def test_should_create_api_key_with_type_normal(
    client_request,
    api_user_active,
    mock_login,
    mock_get_api_keys,
    mock_get_live_service,
    mock_has_permissions,
    fake_uuid,
    mocker,
):
    post = mocker.patch(
        "app.notify_client.api_key_api_client.ApiKeyApiClient.post",
        return_value={"data": fake_uuid},
    )

    page = client_request.post(
        "main.create_api_key",
        service_id=SERVICE_ONE_ID,
        _data={"key_name": "Some default key name 1/2", "key_type": "normal"},
        _expected_status=200,
    )

    assert page.select_one("span.copy-to-clipboard__value").text == (
        # The text should be exactly this, with no leading or trailing whitespace
        f"some_default_key_name_12-{SERVICE_ONE_ID}-{fake_uuid}"
    )

    post.assert_called_once_with(
        url="/service/{}/api-key".format(SERVICE_ONE_ID),
        data={
            "name": "Some default key name 1/2",
            "key_type": "normal",
            "created_by": api_user_active["id"],
        },
    )


def test_cant_create_normal_api_key_in_trial_mode(
    client_request,
    api_user_active,
    mock_login,
    mock_get_api_keys,
    mock_get_service,
    mock_has_permissions,
    fake_uuid,
    mocker,
):
    mock_post = mocker.patch(
        "app.notify_client.api_key_api_client.ApiKeyApiClient.post"
    )

    client_request.post(
        "main.create_api_key",
        service_id=SERVICE_ONE_ID,
        _data={"key_name": "some default key name", "key_type": "normal"},
        _expected_status=400,
    )
    assert mock_post.called is False


def test_should_show_confirm_revoke_api_key(
    client_request,
    mock_get_api_keys,
    fake_uuid,
):
    page = client_request.get(
        "main.revoke_api_key",
        service_id=SERVICE_ONE_ID,
        key_id=fake_uuid,
        _test_page_title=False,
    )
    assert normalize_spaces(page.select(".banner-dangerous")[0].text) == (
        "Are you sure you want to revoke ‘some key name’? "
        "You will not be able to use this API key to connect to Notify.gov. "
        "Yes, revoke this API key"
    )
    assert mock_get_api_keys.call_args_list == [
        call("596364a0-858e-42c8-9062-a8fe822260eb"),
    ]


def test_should_404_for_api_key_that_doesnt_exist(
    client_request,
    mock_get_api_keys,
):
    client_request.get(
        "main.revoke_api_key",
        service_id=SERVICE_ONE_ID,
        key_id="key-doesn’t-exist",
        _expected_status=404,
    )


def test_should_redirect_after_revoking_api_key(
    client_request,
    api_user_active,
    mock_login,
    mock_revoke_api_key,
    mock_get_api_keys,
    mock_get_service,
    mock_has_permissions,
    fake_uuid,
):
    client_request.post(
        "main.revoke_api_key",
        service_id=SERVICE_ONE_ID,
        key_id=fake_uuid,
        _expected_status=302,
        _expected_redirect=url_for(
            ".api_keys",
            service_id=SERVICE_ONE_ID,
        ),
    )
    mock_revoke_api_key.assert_called_once_with(
        service_id=SERVICE_ONE_ID, key_id=fake_uuid
    )
    mock_get_api_keys.assert_called_once_with(
        SERVICE_ONE_ID,
    )


@pytest.mark.parametrize(
    "route", ["main.api_keys", "main.create_api_key", "main.revoke_api_key"]
)
def test_route_permissions(
    mocker,
    notify_admin,
    fake_uuid,
    api_user_active,
    service_one,
    mock_get_api_keys,
    route,
):
    with notify_admin.test_request_context():

        def _get(mocker):
            return {"count": 0}

        mocker.patch("app.service_api_client.get_service_statistics")
        mocker.patch(
            "app.service_api_client.get_global_notification_count", side_effect=_get
        )

        validate_route_permission(
            mocker,
            notify_admin,
            "GET",
            200,
            url_for(route, service_id=service_one["id"], key_id=fake_uuid),
            ["manage_api_keys"],
            api_user_active,
            service_one,
        )


@pytest.mark.parametrize(
    "route", ["main.api_keys", "main.create_api_key", "main.revoke_api_key"]
)
def test_route_invalid_permissions(
    mocker,
    notify_admin,
    fake_uuid,
    api_user_active,
    service_one,
    mock_get_api_keys,
    route,
):
    with notify_admin.test_request_context():

        def _get(mocker):
            return {"count": 0}

        mocker.patch("app.service_api_client.get_service_statistics")

        mocker.patch(
            "app.service_api_client.get_global_notification_count", side_effect=_get
        )

        validate_route_permission(
            mocker,
            notify_admin,
            "GET",
            403,
            url_for(route, service_id=service_one["id"], key_id=fake_uuid),
            [ServicePermission.VIEW_ACTIVITY],
            api_user_active,
            service_one,
        )


def test_should_show_guestlist_page(
    client_request,
    mock_login,
    api_user_active,
    mock_get_service,
    mock_has_permissions,
    mock_get_guest_list,
):
    page = client_request.get(
        "main.guest_list",
        service_id=SERVICE_ONE_ID,
    )
    textboxes = page.find_all("input", {"class": "usa-input"})
    for index, value in enumerate(
        ["test@example.com"] + [None] * 4 + ["2028675300"] + [None] * 4
    ):
        assert textboxes[index].get("value") == value


def test_should_update_guestlist(
    client_request,
    mock_update_guest_list,
):
    data = OrderedDict(
        [
            ("email_addresses-1", "test@example.com"),
            ("email_addresses-3", "test@example.com"),
            ("phone_numbers-0", "2028675300"),
            ("phone_numbers-2", "+1800-555-5555"),
        ]
    )

    client_request.post(
        "main.guest_list",
        service_id=SERVICE_ONE_ID,
        _data=data,
    )

    mock_update_guest_list.assert_called_once_with(
        SERVICE_ONE_ID,
        {
            "email_addresses": ["test@example.com", "test@example.com"],
            "phone_numbers": ["2028675300", "+1800-555-5555"],
        },
    )


def test_should_validate_guestlist_items(
    client_request,
    mock_update_guest_list,
):
    page = client_request.post(
        "main.guest_list",
        service_id=SERVICE_ONE_ID,
        _data=OrderedDict([("email_addresses-1", "abc"), ("phone_numbers-0", "123")]),
        _expected_status=200,
    )

    assert page.h1.string.strip() == "There was a problem with your guest list"
    jump_links = page.select(".banner-dangerous a")

    assert jump_links[0].string.strip() == "Enter valid email addresses"
    assert jump_links[0]["href"] == "#email_addresses"

    assert jump_links[1].string.strip() == "Enter valid phone numbers"
    assert jump_links[1]["href"] == "#phone_numbers"

    assert mock_update_guest_list.called is False


@pytest.mark.parametrize(
    "endpoint",
    [
        ("main.delivery_status_callback"),
        ("main.received_text_messages_callback"),
    ],
)
@pytest.mark.parametrize(
    ("url", "bearer_token", "expected_errors"),
    [
        ("https://example.com", "", "Cannot be empty"),
        ("http://not_https.com", "1234567890", "Must be a valid https URL"),
        ("https://test.com", "123456789", "Must be at least 10 characters"),
    ],
)
def test_callback_forms_validation(
    client_request,
    service_one,
    mock_get_valid_service_callback_api,
    endpoint,
    url,
    bearer_token,
    expected_errors,
):
    if endpoint == "main.received_text_messages_callback":
        service_one["permissions"] = [ServicePermission.INBOUND_SMS]

    data = {
        "url": url,
        "bearer_token": bearer_token,
    }

    response = client_request.post(
        endpoint, service_id=service_one["id"], _data=data, _expected_status=200
    )
    error_msgs = " ".join(
        msg.text.strip() for msg in response.select(".usa-error-message")
    )

    assert expected_errors in error_msgs


@pytest.mark.parametrize("bearer_token", ["", "some-bearer-token"])
@pytest.mark.parametrize(
    ("endpoint", "expected_delete_url"),
    [
        (
            "main.delivery_status_callback",
            "/service/{}/delivery-receipt-api/{}",
        ),
        (
            "main.received_text_messages_callback",
            "/service/{}/inbound-api/{}",
        ),
    ],
)
def test_callback_forms_can_be_cleared(
    client_request,
    service_one,
    endpoint,
    expected_delete_url,
    bearer_token,
    mocker,
    fake_uuid,
    mock_get_valid_service_callback_api,
    mock_get_valid_service_inbound_api,
):
    service_one["service_callback_api"] = [fake_uuid]
    service_one["inbound_api"] = [fake_uuid]
    service_one["permissions"] = [ServicePermission.INBOUND_SMS]
    mocked_delete = mocker.patch("app.service_api_client.delete")

    page = client_request.post(
        endpoint,
        service_id=service_one["id"],
        _data={
            "url": "",
            "bearer_token": bearer_token,
        },
        _expected_redirect=url_for(
            "main.api_callbacks",
            service_id=service_one["id"],
        ),
    )

    assert not page.select(".error-message")

    mocked_delete.assert_called_once_with(
        expected_delete_url.format(service_one["id"], fake_uuid)
    )


@pytest.mark.parametrize("bearer_token", ["", "some-bearer-token"])
@pytest.mark.parametrize(
    ("endpoint", "expected_delete_url"),
    [
        (
            "main.delivery_status_callback",
            "/service/{}/delivery-receipt-api/{}",
        ),
        (
            "main.received_text_messages_callback",
            "/service/{}/inbound-api/{}",
        ),
    ],
)
def test_callback_forms_can_be_cleared_when_callback_and_inbound_apis_are_empty(
    client_request,
    service_one,
    endpoint,
    expected_delete_url,
    bearer_token,
    mocker,
    mock_get_empty_service_callback_api,
    mock_get_empty_service_inbound_api,
):
    service_one["permissions"] = [ServicePermission.INBOUND_SMS]
    mocked_delete = mocker.patch("app.service_api_client.delete")

    page = client_request.post(
        endpoint,
        service_id=service_one["id"],
        _data={
            "url": "",
            "bearer_token": bearer_token,
        },
        _expected_redirect=url_for(
            "main.api_callbacks",
            service_id=service_one["id"],
        ),
    )

    assert not page.select(".error-message")
    assert mocked_delete.call_args_list == []


@pytest.mark.parametrize(
    ("has_inbound_sms", "expected_link"),
    [
        (True, "main.api_callbacks"),
        (False, "main.delivery_status_callback"),
    ],
)
def test_callbacks_button_links_straight_to_delivery_status_if_service_has_no_inbound_sms(
    client_request,
    service_one,
    mocker,
    mock_get_notifications,
    has_inbound_sms,
    expected_link,
):
    if has_inbound_sms:
        service_one["permissions"] = [ServicePermission.INBOUND_SMS]

    page = client_request.get(
        "main.api_integration",
        service_id=service_one["id"],
    )

    assert page.select(".pill-separate-item")[2]["href"] == url_for(
        expected_link, service_id=service_one["id"]
    )


def test_callbacks_page_redirects_to_delivery_status_if_service_has_no_inbound_sms(
    client_request,
    service_one,
    mocker,
    mock_get_valid_service_callback_api,
):
    page = client_request.get(
        "main.api_callbacks",
        service_id=service_one["id"],
        _follow_redirects=True,
    )

    assert (
        normalize_spaces(page.select_one("h1").text)
        == "Callbacks for delivery receipts"
    )


@pytest.mark.parametrize(
    ("has_inbound_sms", "expected_link"),
    [
        (True, "main.api_callbacks"),
        (False, "main.api_integration"),
    ],
)
def test_back_link_directs_to_api_integration_from_delivery_callback_if_no_inbound_sms(
    client_request, service_one, mocker, has_inbound_sms, expected_link
):
    if has_inbound_sms:
        service_one["permissions"] = [ServicePermission.INBOUND_SMS]

    page = client_request.get(
        "main.delivery_status_callback",
        service_id=service_one["id"],
        _follow_redirects=True,
    )

    assert page.select_one(".usa-back-link")["href"] == url_for(
        expected_link, service_id=service_one["id"]
    )


@pytest.mark.parametrize(
    "endpoint",
    [
        ("main.delivery_status_callback"),
        ("main.received_text_messages_callback"),
    ],
)
def test_create_delivery_status_and_receive_text_message_callbacks(
    client_request,
    service_one,
    mocker,
    mock_get_notifications,
    mock_create_service_inbound_api,
    mock_create_service_callback_api,
    endpoint,
    fake_uuid,
):
    if endpoint == "main.received_text_messages_callback":
        service_one["permissions"] = [ServicePermission.INBOUND_SMS]

    data = {
        "url": "https://test.url.com/",
        "bearer_token": "1234567890",
        "user_id": fake_uuid,
    }

    client_request.post(
        endpoint,
        service_id=service_one["id"],
        _data=data,
    )

    if endpoint == "main.received_text_messages_callback":
        mock_create_service_inbound_api.assert_called_once_with(
            service_one["id"],
            url="https://test.url.com/",
            bearer_token="1234567890",
            user_id=fake_uuid,
        )
    else:
        mock_create_service_callback_api.assert_called_once_with(
            service_one["id"],
            url="https://test.url.com/",
            bearer_token="1234567890",
            user_id=fake_uuid,
        )


def test_update_delivery_status_callback_details(
    client_request,
    service_one,
    mock_update_service_callback_api,
    mock_get_valid_service_callback_api,
    fake_uuid,
):
    service_one["service_callback_api"] = [fake_uuid]

    data = {
        "url": "https://test.url.com/",
        "bearer_token": "1234567890",
        "user_id": fake_uuid,
    }

    client_request.post(
        "main.delivery_status_callback",
        service_id=service_one["id"],
        _data=data,
    )

    mock_update_service_callback_api.assert_called_once_with(
        service_one["id"],
        url="https://test.url.com/",
        bearer_token="1234567890",
        user_id=fake_uuid,
        callback_api_id=fake_uuid,
    )


def test_update_receive_text_message_callback_details(
    client_request,
    service_one,
    mock_update_service_inbound_api,
    mock_get_valid_service_inbound_api,
    fake_uuid,
):
    service_one["inbound_api"] = [fake_uuid]
    service_one["permissions"] = [ServicePermission.INBOUND_SMS]

    data = {
        "url": "https://test.url.com/",
        "bearer_token": "1234567890",
        "user_id": fake_uuid,
    }

    client_request.post(
        "main.received_text_messages_callback",
        service_id=service_one["id"],
        _data=data,
    )

    mock_update_service_inbound_api.assert_called_once_with(
        service_one["id"],
        url="https://test.url.com/",
        bearer_token="1234567890",
        user_id=fake_uuid,
        inbound_api_id=fake_uuid,
    )


def test_update_delivery_status_callback_without_changes_does_not_update(
    client_request,
    service_one,
    mock_update_service_callback_api,
    fake_uuid,
    mock_get_valid_service_callback_api,
):
    service_one["service_callback_api"] = [fake_uuid]
    data = {
        "user_id": fake_uuid,
        "url": "https://hello2.gsa.gov",
        "bearer_token": "bearer_token_set",
    }

    client_request.post(
        "main.delivery_status_callback",
        service_id=service_one["id"],
        _data=data,
    )

    assert mock_update_service_callback_api.called is False


def test_update_receive_text_message_callback_without_changes_does_not_update(
    client_request,
    service_one,
    mock_update_service_inbound_api,
    fake_uuid,
    mock_get_valid_service_inbound_api,
):
    service_one["inbound_api"] = [fake_uuid]
    service_one["permissions"] = [ServicePermission.INBOUND_SMS]
    data = {
        "user_id": fake_uuid,
        "url": "https://hello3.gsa.gov",
        "bearer_token": "bearer_token_set",
    }

    client_request.post(
        "main.received_text_messages_callback",
        service_id=service_one["id"],
        _data=data,
    )

    assert mock_update_service_inbound_api.called is False


@pytest.mark.parametrize(
    ("service_callback_api", "delivery_url", "expected_1st_table_row"),
    [
        (None, {}, "Delivery receipts Not set Change"),
        (
            sample_uuid(),
            {"url": "https://delivery.receipts"},
            "Delivery receipts https://delivery.receipts Change",
        ),
    ],
)
@pytest.mark.parametrize(
    ("inbound_api", "inbound_url", "expected_2nd_table_row"),
    [
        (None, {}, "Received text messages Not set Change"),
        (
            sample_uuid(),
            {"url": "https://inbound.sms"},
            "Received text messages https://inbound.sms Change",
        ),
    ],
)
def test_callbacks_page_works_when_no_apis_set(
    client_request,
    service_one,
    mocker,
    service_callback_api,
    delivery_url,
    expected_1st_table_row,
    inbound_api,
    inbound_url,
    expected_2nd_table_row,
):
    service_one["permissions"] = [ServicePermission.INBOUND_SMS]
    service_one["inbound_api"] = inbound_api
    service_one["service_callback_api"] = service_callback_api

    mocker.patch(
        "app.service_api_client.get_service_callback_api", return_value=delivery_url
    )
    mocker.patch(
        "app.service_api_client.get_service_inbound_api", return_value=inbound_url
    )

    page = client_request.get(
        "main.api_callbacks", service_id=service_one["id"], _follow_redirects=True
    )
    expected_rows = [
        expected_1st_table_row,
        expected_2nd_table_row,
    ]
    rows = page.select("tbody tr")
    assert len(rows) == 2
    for index, row in enumerate(expected_rows):
        assert row == normalize_spaces(rows[index].text)
