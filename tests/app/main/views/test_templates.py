import json
from unittest.mock import ANY, Mock

import pytest
from bs4 import BeautifulSoup
from flask import url_for
from freezegun import freeze_time

from app.enums import ServicePermission
from notifications_python_client.errors import HTTPError
from tests import template_json, validate_route_permission
from tests.app.main.views.test_template_folders import (
    CHILD_FOLDER_ID,
    FOLDER_TWO_ID,
    PARENT_FOLDER_ID,
    _folder,
    _template,
)
from tests.conftest import (
    SERVICE_ONE_ID,
    SERVICE_TWO_ID,
    TEMPLATE_ONE_ID,
    ElementNotFound,
    create_active_caseworking_user,
    create_active_user_view_permissions,
    create_template,
    normalize_spaces,
)


@pytest.mark.parametrize(
    ("permissions", "expected_message"),
    [
        (
            ["email"],
            (
                "Every message starts with a template. You can change it later. "
                "You need a template before you can send messages."
            ),
        ),
        (
            ["sms"],
            (
                "Every message starts with a template. You can change it later. "
                "You need a template before you can send messages."
            ),
        ),
        (
            ["email", "sms"],
            (
                "Every message starts with a template. You can change it later. "
                "You need a template before you can send messages."
            ),
        ),
    ],
)
def test_should_show_empty_page_when_no_templates(
    client_request,
    service_one,
    mock_get_service_templates_when_no_templates_exist,
    mock_get_template_folders,
    mock_get_no_api_keys,
    permissions,
    expected_message,
):
    service_one["permissions"] = permissions

    page = client_request.get(
        "main.choose_template",
        service_id=service_one["id"],
    )

    assert normalize_spaces(page.select_one("h1").text) == (
        "Select or create a template"
    )
    assert normalize_spaces(page.select_one("main p").text) == (expected_message)
    assert page.select_one("#add_new_folder_form")
    assert page.select_one("#add_new_template_form")


def test_should_show_add_template_form_if_service_has_folder_permission(
    client_request,
    service_one,
    mock_get_service_templates_when_no_templates_exist,
    mock_get_template_folders,
    mock_get_no_api_keys,
):
    page = client_request.get(
        "main.choose_template",
        service_id=service_one["id"],
    )

    assert normalize_spaces(page.select_one("h1").text) == (
        "Select or create a template"
    )
    assert normalize_spaces(page.select_one("main p").text) == (
        "Every message starts with a template. You can change it later. "
        "You need a template before you can send messages."
    )
    assert [(item["name"], item["value"]) for item in page.select("[type=radio]")] == [
        # ('add_template_by_template_type', 'email'),
        ("add_template_by_template_type", "sms"),
    ]
    assert not page.select("main a")


@pytest.mark.parametrize(
    (
        "user",
        "expected_page_title",
        "extra_args",
        "expected_nav_links",
        "expected_templates",
    ),
    [
        (
            create_active_user_view_permissions(),
            "Select or create a template",
            {},
            ["Email", "Text message"],
            [
                "sms_template_one",
                "sms_template_two",
                "email_template_one",
                "email_template_two",
            ],
        ),
        (
            create_active_user_view_permissions(),
            "Select or create a template",
            {"template_type": "sms"},
            ["All", "Email"],
            ["sms_template_one", "sms_template_two"],
        ),
        (
            create_active_user_view_permissions(),
            "Select or create a template",
            {"template_type": "email"},
            ["All", "Text message"],
            ["email_template_one", "email_template_two"],
        ),
        (
            create_active_caseworking_user(),
            "Select or create a template",
            {},
            ["Email", "Text message"],
            [
                "sms_template_one",
                "sms_template_two",
                "email_template_one",
                "email_template_two",
            ],
        ),
        (
            create_active_caseworking_user(),
            "Select or create a template",
            {"template_type": "email"},
            ["All", "Text message"],
            ["email_template_one", "email_template_two"],
        ),
    ],
)
def test_should_show_page_for_choosing_a_template(
    client_request,
    mock_get_service_templates,
    mock_get_template_folders,
    mock_has_no_jobs,
    mock_get_no_api_keys,
    extra_args,
    expected_nav_links,
    expected_templates,
    service_one,
    mocker,
    user,
    expected_page_title,
):
    client_request.login(user)

    page = client_request.get(
        "main.choose_template", service_id=service_one["id"], **extra_args
    )

    assert normalize_spaces(page.select_one("h1").text) == expected_page_title

    links_in_page = page.select(".pill a:not(.pill-item--selected)")

    assert len(links_in_page) == len(expected_nav_links)

    for index, expected_link in enumerate(expected_nav_links):
        assert links_in_page[index].text.strip() == expected_link

    template_links = page.select("#template-list a, .template-list-item a")

    assert len(template_links) == len(expected_templates)

    for index, expected_template in enumerate(expected_templates):
        assert template_links[index].text.strip() == expected_template

    mock_get_service_templates.assert_called_once_with(SERVICE_ONE_ID)
    mock_get_template_folders.assert_called_once_with(SERVICE_ONE_ID)


def test_choose_template_can_pass_through_an_initial_state_to_templates_and_folders_selection_form(
    client_request,
    mock_get_template_folders,
    mock_get_service_templates,
    mock_get_no_api_keys,
):
    page = client_request.get(
        "main.choose_template",
        service_id=SERVICE_ONE_ID,
        initial_state="add-new-template",
    )

    templates_and_folders_form = page.find("form")
    assert templates_and_folders_form["data-prev-state"] == "add-new-template"


def test_should_not_show_template_nav_if_only_one_type_of_template(
    client_request,
    mock_get_template_folders,
    mock_get_service_templates_with_only_one_template,
    mock_get_no_api_keys,
):
    page = client_request.get(
        "main.choose_template",
        service_id=SERVICE_ONE_ID,
    )

    assert not page.select(".pill")


def test_should_not_show_live_search_if_list_of_templates_fits_onscreen(
    client_request,
    mock_get_template_folders,
    mock_get_service_templates,
    mock_get_no_api_keys,
):
    page = client_request.get(
        "main.choose_template",
        service_id=SERVICE_ONE_ID,
    )

    assert not page.select(".live-search")


def test_should_show_live_search_if_list_of_templates_taller_than_screen(
    client_request,
    mock_get_template_folders,
    mock_get_more_service_templates_than_can_fit_onscreen,
    mock_get_no_api_keys,
):
    page = client_request.get(
        "main.choose_template",
        service_id=SERVICE_ONE_ID,
    )
    search = page.select_one(".live-search")

    assert search["data-module"] == "live-search"
    assert search["data-targets"] == "#template-list .template-list-item"
    assert normalize_spaces(search.select_one("label").text) == ("Search by name")

    assert (
        len(page.select(search["data-targets"]))
        == len(page.select("#template-list .usa-checkbox"))
        == 20
    )


def test_should_label_search_by_id_for_services_with_api_keys(
    client_request,
    mock_get_template_folders,
    mock_get_more_service_templates_than_can_fit_onscreen,
    mock_get_api_keys,
):
    page = client_request.get(
        "main.choose_template",
        service_id=SERVICE_ONE_ID,
    )
    assert normalize_spaces(page.select_one(".live-search label").text) == (
        "Search by name or ID"
    )


def test_should_show_live_search_if_service_has_lots_of_folders(
    client_request,
    mock_get_template_folders,
    mock_get_service_templates,  # returns 4 templates
    mock_get_no_api_keys,
):
    mock_get_template_folders.return_value = [
        _folder("one", PARENT_FOLDER_ID),
        _folder("two", None, parent=PARENT_FOLDER_ID),
        _folder("three", None, parent=PARENT_FOLDER_ID),
        _folder("four", None, parent=PARENT_FOLDER_ID),
    ]

    page = client_request.get(
        "main.choose_template",
        service_id=SERVICE_ONE_ID,
    )

    count_of_templates_and_folders = len(page.select("#template-list .usa-checkbox"))
    count_of_folders = len(page.select(".template-list-folder:first-of-type"))
    count_of_templates = count_of_templates_and_folders - count_of_folders

    assert len(page.select(".live-search")) == 1
    assert count_of_folders == 4
    assert count_of_templates == 4


@pytest.mark.parametrize(
    ("service_permissions", "expected_values", "expected_labels"),
    [
        pytest.param(
            ["email", "sms"],
            [
                # 'email',
                "sms",
                "copy-existing",
            ],
            [
                # 'Email',
                "Start with a blank template",
                "Copy an existing template",
            ],
        ),
        # TODO This is a duplicate of above. Why?
        # pytest.param(
        #     ["email", "sms"],
        #     [
        #         # 'email',
        #         "sms",
        #         "copy-existing",
        #     ],
        #     [
        #         # 'Email',
        #         "Start with a blank template",
        #         "Copy an existing template",
        #     ],
        # ),
    ],
)
def test_should_show_new_template_choices_if_service_has_folder_permission(
    client_request,
    service_one,
    mock_get_service_templates,
    mock_get_template_folders,
    mock_get_no_api_keys,
    service_permissions,
    expected_values,
    expected_labels,
):
    service_one["permissions"] = service_permissions

    page = client_request.get(
        "main.choose_template",
        service_id=SERVICE_ONE_ID,
    )

    if not page.select("#add_new_template_form"):
        raise ElementNotFound()

    assert normalize_spaces(
        page.select_one("#add_new_template_form fieldset legend").text
    ) == ("New template")
    assert [
        choice["value"]
        for choice in page.select("#add_new_template_form input[type=radio]")
    ] == expected_values
    assert [
        normalize_spaces(choice.text)
        for choice in page.select("#add_new_template_form label")
    ] == expected_labels


@pytest.mark.parametrize(
    ("permissions", "are_data_attrs_added"),
    [
        (["sms"], True),
        (["email"], True),
        (["sms", "email"], False),
    ],
)
def test_should_add_data_attributes_for_services_that_only_allow_one_type_of_notifications(
    client_request,
    service_one,
    mock_get_service_templates,
    mock_get_template_folders,
    mock_get_no_api_keys,
    permissions,
    are_data_attrs_added,
):
    service_one["permissions"] = permissions

    page = client_request.get(
        "main.choose_template",
        service_id=SERVICE_ONE_ID,
    )

    if not page.select("#add_new_template_form"):
        raise ElementNotFound()

    if are_data_attrs_added:
        assert (
            page.find(id="add_new_template_form").attrs["data-channel"]
            == permissions[0]
        )
        assert (
            page.find(id="add_new_template_form").attrs["data-service"]
            == SERVICE_ONE_ID
        )
    else:
        assert page.find(id="add_new_template_form").attrs.get("data-channel") is None
        assert page.find(id="add_new_template_form").attrs.get("data-service") is None


def test_should_show_page_for_one_template(
    client_request,
    mock_get_service_template,
    fake_uuid,
):
    template_id = fake_uuid
    page = client_request.get(
        ".edit_service_template",
        service_id=SERVICE_ONE_ID,
        template_id=template_id,
    )

    assert page.select_one("input[type=text]")["value"] == "Two week reminder"
    assert "Template &lt;em&gt;content&lt;/em&gt; with &amp; entity" in str(
        page.select_one("textarea")
    )
    assert page.select_one("textarea")["data-module"] == "enhanced-textbox"
    assert page.select_one("textarea")["data-highlight-placeholders"] == "true"
    assert "priority" not in str(page.select_one("main"))

    assert (
        (page.select_one("[data-module=update-status]")["data-target"])
        == (page.select_one("textarea")["id"])
        == ("template_content")
    )

    assert (
        page.select_one("[data-module=update-status]")["data-updates-url"]
    ) == url_for(
        ".count_content_length",
        service_id=SERVICE_ONE_ID,
        template_type="sms",
    )

    assert (page.select_one("[data-module=update-status]")["aria-live"]) == ("polite")

    mock_get_service_template.assert_called_with(SERVICE_ONE_ID, template_id, None)


def test_caseworker_redirected_to_set_sender_for_one_off(
    client_request,
    mock_get_service_templates,
    mock_get_service_template,
    mocker,
    fake_uuid,
    active_caseworking_user,
):
    client_request.login(active_caseworking_user)

    client_request.get(
        "main.view_template",
        service_id=SERVICE_ONE_ID,
        template_id=fake_uuid,
        _expected_status=302,
        _expected_redirect=url_for(
            "main.set_sender",
            service_id=SERVICE_ONE_ID,
            template_id=fake_uuid,
        ),
    )


@freeze_time("2020-01-01 20:00")
def test_caseworker_sees_template_page_if_template_is_deleted(
    client_request,
    mock_get_deleted_template,
    fake_uuid,
    mocker,
    active_caseworking_user,
):
    mocker.patch("app.user_api_client.get_user", return_value=active_caseworking_user)

    template_id = fake_uuid
    page = client_request.get(
        ".view_template",
        service_id=SERVICE_ONE_ID,
        template_id=template_id,
        _test_page_title=False,
    )

    content = str(page)
    assert (
        url_for("main.send_one_off", service_id=SERVICE_ONE_ID, template_id=fake_uuid)
        not in content
    )
    assert (
        page.select("p.hint")[0].text.strip()
        == "This template was deleted today at 15:00 America/New_York."
    )

    mock_get_deleted_template.assert_called_with(SERVICE_ONE_ID, template_id, None)


def test_user_with_only_send_and_view_redirected_to_set_sender_for_one_off(
    client_request,
    mock_get_service_templates,
    mock_get_service_template,
    active_user_with_permissions,
    mocker,
    fake_uuid,
):
    active_user_with_permissions["permissions"][SERVICE_ONE_ID] = [
        "send_messages",
        ServicePermission.VIEW_ACTIVITY,
    ]
    client_request.login(active_user_with_permissions)
    client_request.get(
        "main.view_template",
        service_id=SERVICE_ONE_ID,
        template_id=fake_uuid,
        _expected_status=302,
        _expected_redirect=url_for(
            "main.set_sender",
            service_id=SERVICE_ONE_ID,
            template_id=fake_uuid,
        ),
    )


@pytest.mark.parametrize(
    ("permissions", "links_to_be_shown", "permissions_warning_to_be_shown"),
    [
        (
            [ServicePermission.VIEW_ACTIVITY],
            [],
            "If you need to send this text message or edit this template, contact your manager.",
        ),
        (
            ["manage_api_keys"],
            [],
            None,
        ),
        (
            [ServicePermission.MANAGE_TEMPLATES],
            [
                (".edit_service_template", "Edit this template"),
            ],
            None,
        ),
        (
            [ServicePermission.SEND_MESSAGES, ServicePermission.MANAGE_TEMPLATES],
            [
                (".set_sender", "Use this template"),
                (".edit_service_template", "Edit this template"),
            ],
            None,
        ),
    ],
)
def test_should_be_able_to_view_a_template_with_links(
    client_request,
    mock_get_service_template,
    mock_get_template_folders,
    active_user_with_permissions,
    fake_uuid,
    permissions,
    links_to_be_shown,
    permissions_warning_to_be_shown,
):
    active_user_with_permissions["permissions"][SERVICE_ONE_ID] = permissions + [
        ServicePermission.VIEW_ACTIVITY
    ]
    client_request.login(active_user_with_permissions)

    page = client_request.get(
        ".view_template",
        service_id=SERVICE_ONE_ID,
        template_id=fake_uuid,
        _test_page_title=False,
    )

    assert normalize_spaces(page.select_one("h1").text) == ("Confirm your template")
    assert normalize_spaces(page.select_one("title").text) == (
        "Confirm your template – service one – Notify.gov"
    )

    assert [
        (link["href"], normalize_spaces(link.text))
        for link in page.select(".usa-pill-separate-item")
    ] == [
        (
            url_for(
                endpoint,
                service_id=SERVICE_ONE_ID,
                template_id=fake_uuid,
            ),
            text,
        )
        for endpoint, text in links_to_be_shown
    ]

    assert normalize_spaces(page.select_one("main p").text) == (
        "To: phone number" or permissions_warning_to_be_shown
    )


@pytest.mark.skip(
    reason="Hiding the copy-to-clipboard widget until API access is opened up"
)
def test_should_show_template_id_on_template_page(
    client_request,
    mock_get_service_template,
    mock_get_template_folders,
    fake_uuid,
):
    page = client_request.get(
        ".view_template",
        service_id=SERVICE_ONE_ID,
        template_id=fake_uuid,
        _test_page_title=False,
    )
    assert fake_uuid in page.select(".copy-to-clipboard__value")[0].text


def test_should_show_sms_template_with_downgraded_unicode_characters(
    client_request,
    mocker,
    service_one,
    mock_get_template_folders,
    fake_uuid,
):
    msg = "here:\tare some “fancy quotes” and zero\u200bwidth\u200bspaces"
    rendered_msg = "here: are some “fancy quotes” and zerowidthspaces"

    mocker.patch(
        "app.service_api_client.get_service_template",
        return_value={
            "data": template_json(
                service_one["id"], fake_uuid, type_="sms", content=msg
            )
        },
    )

    page = client_request.get(
        ".view_template",
        service_id=SERVICE_ONE_ID,
        template_id=fake_uuid,
        _test_page_title=False,
    )

    assert rendered_msg in page.text


@pytest.mark.parametrize(
    "prefix_sms", [True, pytest.param(False, marks=pytest.mark.xfail())]
)
def test_should_show_message_with_prefix_hint_if_enabled_for_service(
    client_request,
    mocker,
    mock_get_service_template,
    mock_get_users_by_service,
    service_one,
    fake_uuid,
    prefix_sms,
):
    service_one["prefix_sms"] = prefix_sms

    page = client_request.get(
        ".edit_service_template",
        service_id=service_one["id"],
        template_id=fake_uuid,
    )

    assert "Your service name will be added to the start of your message" in page.text


def test_should_show_page_template_with_priority_select_if_platform_admin(
    client_request,
    platform_admin_user,
    mocker,
    mock_get_service_template,
    service_one,
    fake_uuid,
):
    mocker.patch(
        "app.user_api_client.get_users_for_service", return_value=[platform_admin_user]
    )
    template_id = fake_uuid
    client_request.login(platform_admin_user)
    page = client_request.get(
        ".edit_service_template",
        service_id=service_one["id"],
        template_id=template_id,
    )

    assert page.select_one("input[name=name]")["value"] == "Two week reminder"
    assert "Template &lt;em&gt;content&lt;/em&gt; with &amp; entity" in str(
        page.select_one("textarea")
    )
    assert "Use priority queue?" not in page.text
    mock_get_service_template.assert_called_with(service_one["id"], template_id, None)


def test_choosing_to_copy_redirects(
    client_request,
    service_one,
    mock_get_service_templates,
    mock_get_template_folders,
):
    client_request.post(
        "main.choose_template",
        service_id=SERVICE_ONE_ID,
        _data={
            "operation": "add-new-template",
            "add_template_by_template_type": "copy-existing",
        },
        _expected_status=302,
        _expected_redirect=url_for(
            "main.choose_template_to_copy",
            service_id=SERVICE_ONE_ID,
        ),
    )


def test_choose_a_template_to_copy(
    client_request,
    mock_get_service_templates,
    mock_get_template_folders,
    mock_get_no_api_keys,
    mock_get_just_services_for_user,
):
    page = client_request.get(
        "main.choose_template_to_copy",
        service_id=SERVICE_ONE_ID,
    )

    assert page.select(".folder-heading") == []

    expected = [
        (""),
        ("Service 1 sms_template_one"),
        ("Service 1 sms_template_two"),
        ("Service 1 email_template_one"),
        ("Service 1 email_template_two"),
        (""),
        ("Service 2 sms_template_one"),
        ("Service 2 sms_template_two"),
        ("Service 2 email_template_one"),
        ("Service 2 email_template_two"),
    ]
    actual = page.select(".template-list-item")

    assert len(actual) == len(expected)

    zipobject = zip(actual, expected)
    for actual, expected in zipobject:
        assert normalize_spaces(actual.text) == expected
    links = page.select("main nav a")
    assert links[0]["href"] == url_for(
        "main.choose_template_to_copy",
        service_id=SERVICE_ONE_ID,
        from_service=SERVICE_TWO_ID,
    )


def test_choose_a_template_to_copy_when_user_has_one_service(
    client_request,
    mock_get_service_templates,
    mock_get_template_folders,
    mock_get_no_api_keys,
    mock_get_empty_organizations_and_one_service_for_user,
):
    page = client_request.get(
        "main.choose_template_to_copy",
        service_id=SERVICE_ONE_ID,
    )

    assert page.select(".folder-heading") == []

    expected = [
        ("sms_template_one"),
        ("sms_template_two"),
        ("email_template_one"),
        ("email_template_two"),
    ]
    actual = page.select(".template-list-item")

    assert len(actual) == len(expected)

    zipobject = zip(actual, expected)
    for actual, expected in zipobject:
        assert normalize_spaces(actual.text) == expected

    assert page.select("main nav a")[0]["href"] == url_for(
        "main.copy_template",
        service_id=SERVICE_ONE_ID,
        template_id=TEMPLATE_ONE_ID,
        from_service=SERVICE_TWO_ID,
    )


def test_choose_a_template_to_copy_from_folder_within_service(
    mocker,
    client_request,
    mock_get_template_folders,
    mock_get_non_empty_organizations_and_services_for_user,
    mock_get_no_api_keys,
):
    mock_get_template_folders.return_value = [
        _folder("Parent folder", PARENT_FOLDER_ID),
        _folder("", CHILD_FOLDER_ID, parent=PARENT_FOLDER_ID),
        _folder("Child folder non-empty", FOLDER_TWO_ID, parent=PARENT_FOLDER_ID),
    ]
    mocker.patch(
        "app.service_api_client.get_service_templates",
        return_value={
            "data": [
                _template(
                    "sms",
                    "Should not appear in list (at service root)",
                ),
                _template(
                    "sms",
                    "Should appear in list (at same level)",
                    parent=PARENT_FOLDER_ID,
                ),
                _template(
                    "sms",
                    "Should appear in list (nested)",
                    parent=FOLDER_TWO_ID,
                    template_id=TEMPLATE_ONE_ID,
                ),
            ]
        },
    )
    page = client_request.get(
        "main.choose_template_to_copy",
        service_id=SERVICE_ONE_ID,
        from_service=SERVICE_ONE_ID,
        from_folder=PARENT_FOLDER_ID,
    )

    assert normalize_spaces(page.select_one(".folder-heading").text) == (
        "service one Parent folder"
    )
    breadcrumb_links = page.select(".folder-heading a")
    assert len(breadcrumb_links) == 1
    assert breadcrumb_links[0]["href"] == url_for(
        "main.choose_template_to_copy",
        service_id=SERVICE_ONE_ID,
        from_service=SERVICE_ONE_ID,
    )

    expected = [
        (""),
        (""),
        ("Child folder non-empty Should appear in list (nested)"),
        ("Should appear in list (at same level)"),
    ]
    actual = page.select(".template-list-item")

    assert len(actual) == len(expected)

    zipobject = zip(actual, expected)
    for actual, expected in zipobject:
        assert normalize_spaces(actual.text) == expected

    links = page.select("main nav a")
    assert links[0]["href"] == url_for(
        "main.choose_template_to_copy",
        service_id=SERVICE_ONE_ID,
        from_folder=FOLDER_TWO_ID,
    )
    # assert links[1]["href"] == url_for(
    #     "main.choose_template_to_copy",
    #     service_id=SERVICE_ONE_ID,
    #     from_service=SERVICE_ONE_ID,
    #     from_folder=PARENT_FOLDER_ID,
    # )
    # assert links[2]["href"] == url_for(
    #     "main.choose_template_to_copy",
    #     service_id=SERVICE_ONE_ID,
    #     from_folder=FOLDER_TWO_ID,
    # )
    # assert links[3]["href"] == url_for(
    #     "main.copy_template",
    #     service_id=SERVICE_ONE_ID,
    #     template_id=TEMPLATE_ONE_ID,
    #     from_service=SERVICE_ONE_ID,
    # )


@pytest.mark.parametrize(
    ("existing_template_names", "expected_name"),
    [
        (["Two week reminder"], "Two week reminder (copy)"),
        (["Two week reminder (copy)"], "Two week reminder (copy 2)"),
        (
            ["Two week reminder", "Two week reminder (copy)"],
            "Two week reminder (copy 2)",
        ),
        (
            ["Two week reminder (copy 8)", "Two week reminder (copy 9)"],
            "Two week reminder (copy 10)",
        ),
        (
            ["Two week reminder (copy)", "Two week reminder (copy 9)"],
            "Two week reminder (copy 10)",
        ),
        (
            ["Two week reminder (copy)", "Two week reminder (copy 10)"],
            "Two week reminder (copy 2)",
        ),
    ],
)
def test_load_edit_template_with_copy_of_template(
    client_request,
    active_user_with_permission_to_two_services,
    mock_get_service_templates,
    mock_get_service_email_template,
    mock_get_non_empty_organizations_and_services_for_user,
    existing_template_names,
    expected_name,
):
    mock_get_service_templates.side_effect = lambda service_id: {
        "data": [
            {"name": existing_template_name, "template_type": "sms"}
            for existing_template_name in existing_template_names
        ]
    }
    client_request.login(active_user_with_permission_to_two_services)
    page = client_request.get(
        "main.copy_template",
        service_id=SERVICE_ONE_ID,
        template_id=TEMPLATE_ONE_ID,
        from_service=SERVICE_TWO_ID,
    )

    assert page.select_one("form")["method"] == "post"

    assert page.select_one("input")["value"] == (expected_name)
    assert page.select_one("textarea").text.strip() == ("Your ((thing)) is due soon")
    mock_get_service_email_template.assert_called_once_with(
        SERVICE_TWO_ID,
        TEMPLATE_ONE_ID,
    )


def test_copy_template_loads_template_from_within_subfolder(
    client_request,
    active_user_with_permission_to_two_services,
    mock_get_service_templates,
    mock_get_non_empty_organizations_and_services_for_user,
    mocker,
):
    template = template_json(
        SERVICE_TWO_ID, TEMPLATE_ONE_ID, name="foo", folder=PARENT_FOLDER_ID
    )

    mock_get_service_template = mocker.patch(
        "app.service_api_client.get_service_template", return_value={"data": template}
    )
    mock_get_template_folder = mocker.patch(
        "app.template_folder_api_client.get_template_folder",
        return_value=_folder("Parent folder", PARENT_FOLDER_ID),
    )
    client_request.login(active_user_with_permission_to_two_services)

    page = client_request.get(
        "main.copy_template",
        service_id=SERVICE_ONE_ID,
        template_id=TEMPLATE_ONE_ID,
        from_service=SERVICE_TWO_ID,
    )

    assert page.select_one("input")["value"] == "foo (copy)"
    mock_get_service_template.assert_called_once_with(SERVICE_TWO_ID, TEMPLATE_ONE_ID)
    mock_get_template_folder.assert_called_once_with(SERVICE_TWO_ID, PARENT_FOLDER_ID)


def test_cant_copy_template_from_non_member_service(
    client_request,
    mock_get_service_email_template,
    mock_get_organizations_and_services_for_user,
):
    client_request.get(
        "main.copy_template",
        service_id=SERVICE_ONE_ID,
        template_id=TEMPLATE_ONE_ID,
        from_service=SERVICE_TWO_ID,
        _expected_status=403,
    )
    assert mock_get_service_email_template.call_args_list == []


@pytest.mark.parametrize(
    ("service_permissions", "data", "expected_error"),
    [
        (
            ["email"],
            {
                "operation": "add-new-template",
                "add_template_by_template_type": "sms",
            },
            "Sending text messages has been disabled for your service.",
        ),
    ],
)
def test_should_not_allow_creation_of_template_through_form_without_correct_permission(
    client_request,
    service_one,
    mock_get_service_templates,
    mock_get_template_folders,
    service_permissions,
    data,
    expected_error,
    fake_uuid,
):
    service_one["permissions"] = service_permissions
    page = client_request.post(
        "main.choose_template",
        service_id=SERVICE_ONE_ID,
        _data=data,
        _follow_redirects=True,
        _expected_status=403,
    )
    assert normalize_spaces(page.select("main p")[0].text) == expected_error
    assert page.select(".usa-back-link")[0].text == "Back"
    assert page.select(".usa-back-link")[0]["href"] == url_for(
        ".choose_template",
        service_id=SERVICE_ONE_ID,
    )


@pytest.mark.parametrize("method", ["get", "post"])
@pytest.mark.parametrize(
    ("type_of_template", "expected_error"),
    [
        ("email", "Sending emails has been disabled for your service."),
        ("sms", "Sending text messages has been disabled for your service."),
    ],
)
def test_should_not_allow_creation_of_a_template_without_correct_permission(
    client_request,
    service_one,
    mocker,
    method,
    type_of_template,
    expected_error,
):
    service_one["permissions"] = []

    page = getattr(client_request, method)(
        ".add_service_template",
        service_id=SERVICE_ONE_ID,
        template_type=type_of_template,
        _follow_redirects=True,
        _expected_status=403,
    )
    assert page.select("main p")[0].text.strip() == expected_error
    assert page.select(".usa-back-link")[0].text == "Back"
    assert page.select(".usa-back-link")[0]["href"] == url_for(
        ".choose_template",
        service_id=service_one["id"],
    )


def test_should_redirect_when_saving_a_template(
    client_request,
    mock_get_service_template,
    mock_get_api_keys,
    mock_update_service_template,
    fake_uuid,
):
    name = "new name"
    content = "template <em>content</em> with & entity"
    client_request.post(
        ".edit_service_template",
        service_id=SERVICE_ONE_ID,
        template_id=fake_uuid,
        _data={
            "id": fake_uuid,
            "name": name,
            "template_content": content,
            "template_type": "sms",
            "service": SERVICE_ONE_ID,
        },
        _expected_status=302,
        _expected_redirect=url_for(
            ".view_template",
            service_id=SERVICE_ONE_ID,
            template_id=fake_uuid,
        ),
    )
    mock_update_service_template.assert_called_with(
        fake_uuid, name, "sms", content, SERVICE_ONE_ID, None
    )


def test_should_edit_content_when_process_type_is_priority_not_platform_admin(
    client_request,
    mock_get_service_template_with_priority,
    mock_update_service_template,
    fake_uuid,
):
    client_request.post(
        ".edit_service_template",
        service_id=SERVICE_ONE_ID,
        template_id=fake_uuid,
        _data={
            "id": fake_uuid,
            "name": "new name",
            "template_content": "new template <em>content</em> with & entity",
            "template_type": "sms",
            "service": SERVICE_ONE_ID,
        },
        _expected_status=302,
        _expected_redirect=url_for(
            ".view_template",
            service_id=SERVICE_ONE_ID,
            template_id=fake_uuid,
        ),
    )
    mock_update_service_template.assert_called_with(
        fake_uuid,
        "new name",
        "sms",
        "new template <em>content</em> with & entity",
        SERVICE_ONE_ID,
        None,
    )


def test_should_not_allow_template_edits_without_correct_permission(
    client_request,
    mock_get_service_template,
    service_one,
    fake_uuid,
):
    service_one["permissions"] = ["email"]

    page = client_request.get(
        ".edit_service_template",
        service_id=SERVICE_ONE_ID,
        template_id=fake_uuid,
        _follow_redirects=True,
        _expected_status=403,
    )

    assert (
        page.select("main p")[0].text.strip()
        == "Sending text messages has been disabled for your service."
    )
    assert page.select(".usa-back-link")[0].text == "Back"
    assert page.select(".usa-back-link")[0]["href"] == url_for(
        ".view_template",
        service_id=SERVICE_ONE_ID,
        template_id=fake_uuid,
    )


def test_should_403_when_edit_template_with_process_type_of_priority_for_non_platform_admin(
    client_request,
    active_user_with_permissions,
    mocker,
    mock_get_service_template,
    mock_update_service_template,
    fake_uuid,
    service_one,
):
    service_one["users"] = [active_user_with_permissions]
    client_request.login(active_user_with_permissions)
    mocker.patch(
        "app.user_api_client.get_users_for_service",
        return_value=[active_user_with_permissions],
    )
    template_id = fake_uuid
    data = {
        "id": template_id,
        "name": "new name",
        "template_content": "template <em>content</em> with & entity",
        "template_type": "sms",
        "service": service_one["id"],
        "process_type": "priority",
    }
    client_request.post(
        ".edit_service_template",
        service_id=service_one["id"],
        template_id=template_id,
        _data=data,
        _expected_status=403,
    )
    assert mock_update_service_template.called is False


def test_should_403_when_create_template_with_process_type_of_priority_for_non_platform_admin(
    client_request,
    active_user_with_permissions,
    mocker,
    mock_get_service_template,
    mock_update_service_template,
    fake_uuid,
    service_one,
):
    service_one["users"] = [active_user_with_permissions]
    client_request.login(active_user_with_permissions, service_one)
    mocker.patch(
        "app.user_api_client.get_users_for_service",
        return_value=[active_user_with_permissions],
    )
    template_id = fake_uuid
    data = {
        "id": template_id,
        "name": "new name",
        "template_content": "template <em>content</em> with & entity",
        "template_type": "sms",
        "service": service_one["id"],
        "process_type": "priority",
    }
    client_request.post(
        ".add_service_template",
        service_id=service_one["id"],
        template_type="sms",
        _data=data,
        _expected_status=403,
    )
    assert mock_update_service_template.called is False


@pytest.mark.parametrize(
    ("old_content", "new_content", "expected_paragraphs"),
    [
        (
            "my favorite color is blue",
            "my favorite color is ((color))",
            [
                "You added ((color))",
                "Before you send any messages, make sure your API calls include color.",
            ],
        ),
        (
            "hello ((name))",
            "hello ((first name)) ((middle name)) ((last name))",
            [
                "You removed ((name))",
                "You added ((first name)) ((middle name)) and ((last name))",
                "Before you send any messages, make sure your API calls include first name, middle name and last name.",
            ],
        ),
    ],
)
def test_should_show_interstitial_when_making_breaking_change(
    client_request,
    mock_update_service_template,
    mock_get_user_by_email,
    mock_get_api_keys,
    fake_uuid,
    mocker,
    new_content,
    old_content,
    expected_paragraphs,
):
    email_template = create_template(
        template_id=fake_uuid,
        template_type="email",
        subject="Your ((thing)) is due soon",
        content=old_content,
    )
    mocker.patch(
        "app.service_api_client.get_service_template",
        return_value={"data": email_template},
    )

    data = {
        "id": fake_uuid,
        "name": "new name",
        "template_content": new_content,
        "template_type": "email",
        "subject": "reminder '\" <span> & ((thing))",
        "service": SERVICE_ONE_ID,
        "process_type": "normal",
    }

    page = client_request.post(
        ".edit_service_template",
        service_id=SERVICE_ONE_ID,
        template_id=fake_uuid,
        _data=data,
        _expected_status=200,
    )

    assert page.h1.string.strip() == "Confirm changes"
    assert page.find("a", {"class": "usa-back-link"})["href"] == url_for(
        ".edit_service_template",
        service_id=SERVICE_ONE_ID,
        template_id=fake_uuid,
    )
    assert [
        normalize_spaces(paragraph.text) for paragraph in page.select("main p")
    ] == expected_paragraphs

    for key, value in {
        "name": "new name",
        "subject": "reminder '\" <span> & ((thing))",
        "template_content": new_content,
        "confirm": "true",
    }.items():
        assert page.find("input", {"name": key})["value"] == value

    # BeautifulSoup returns the value attribute as unencoded, let’s make
    # sure that it is properly encoded in the HTML
    assert str(page.find("input", {"name": "subject"})) == (
        """<input name="subject" type="hidden" value="reminder '&quot; &lt;span&gt; &amp; ((thing))"/>"""
    )


def test_removing_placeholders_is_not_a_breaking_change(
    client_request,
    mock_get_service_email_template,
    mock_update_service_template,
    fake_uuid,
):
    existing_template = mock_get_service_email_template(0, 0)["data"]
    client_request.post(
        ".edit_service_template",
        service_id=SERVICE_ONE_ID,
        template_id=fake_uuid,
        _data={
            "name": existing_template["name"],
            "template_content": "no placeholders",
            "subject": existing_template["subject"],
        },
        _expected_status=302,
        _expected_redirect=url_for(
            "main.view_template",
            service_id=SERVICE_ONE_ID,
            template_id=fake_uuid,
        ),
    )
    assert mock_update_service_template.called is True


def test_should_not_create_too_big_template(
    client_request,
    mock_get_service_template,
    mock_create_service_template_content_too_big,
    fake_uuid,
):
    page = client_request.post(
        ".add_service_template",
        service_id=SERVICE_ONE_ID,
        template_type="sms",
        _data={
            "name": "new name",
            "template_content": "template content",
            "template_type": "sms",
            "service": SERVICE_ONE_ID,
            "process_type": "normal",
        },
        _expected_status=200,
    )
    assert "Content has a character count greater than the limit of 459" in page.text


def test_should_not_update_too_big_template(
    client_request,
    mock_get_service_template,
    mock_update_service_template_400_content_too_big,
    fake_uuid,
):
    page = client_request.post(
        ".edit_service_template",
        service_id=SERVICE_ONE_ID,
        template_id=fake_uuid,
        _data={
            "id": fake_uuid,
            "name": "new name",
            "template_content": "template content",
            "service": SERVICE_ONE_ID,
            "template_type": "sms",
            "process_type": "normal",
        },
        _expected_status=200,
    )
    assert "Content has a character count greater than the limit of 459" in page.text


def test_should_redirect_when_saving_a_template_email(
    client_request,
    mock_get_service_email_template,
    mock_update_service_template,
    mock_get_user_by_email,
    fake_uuid,
):
    name = "new name"
    content = "template <em>content</em> with & entity ((thing)) ((date))"
    subject = "subject & entity"
    client_request.post(
        ".edit_service_template",
        service_id=SERVICE_ONE_ID,
        template_id=fake_uuid,
        _data={
            "id": fake_uuid,
            "name": name,
            "template_content": content,
            "template_type": "email",
            "service": SERVICE_ONE_ID,
            "subject": subject,
        },
        _expected_status=302,
        _expected_redirect=url_for(
            ".view_template",
            service_id=SERVICE_ONE_ID,
            template_id=fake_uuid,
        ),
    )
    mock_update_service_template.assert_called_with(
        fake_uuid, name, "email", content, SERVICE_ONE_ID, subject
    )


def test_should_show_delete_template_page_with_time_block(
    client_request,
    mock_get_service_template,
    mock_get_template_folders,
    mocker,
    fake_uuid,
):
    mocker.patch(
        "app.template_statistics_client.get_last_used_date_for_template",
        return_value="2012-01-01 12:00:00",
    )

    with freeze_time("2012-01-01 12:10:00"):
        page = client_request.get(
            ".delete_service_template",
            service_id=SERVICE_ONE_ID,
            template_id=fake_uuid,
            _test_page_title=False,
        )
    assert (
        "Are you sure you want to delete ‘Two week reminder’?"
        in page.select(".banner-dangerous")[0].text
    )
    assert normalize_spaces(page.select(".banner-dangerous p")[0].text) == (
        "This template was last used 10 minutes ago."
    )
    assert normalize_spaces(page.select(".sms-message-wrapper")[0].text) == (
        "service one: Template <em>content</em> with & entity"
    )
    mock_get_service_template.assert_called_with(SERVICE_ONE_ID, fake_uuid, None)


def test_should_show_delete_template_page_with_time_block_for_empty_notification(
    client_request,
    mock_get_service_template,
    mock_get_template_folders,
    mocker,
    fake_uuid,
):
    mocker.patch(
        "app.template_statistics_client.get_last_used_date_for_template",
        return_value=None,
    )

    with freeze_time("2012-01-01 11:00:00"):
        page = client_request.get(
            ".delete_service_template",
            service_id=SERVICE_ONE_ID,
            template_id=fake_uuid,
            _test_page_title=False,
        )
    assert (
        "Are you sure you want to delete ‘Two week reminder’?"
        in page.select(".banner-dangerous")[0].text
    )
    assert normalize_spaces(page.select(".banner-dangerous p")[0].text) == (
        "This template has never been used."
    )
    assert normalize_spaces(page.select(".sms-message-wrapper")[0].text) == (
        "service one: Template <em>content</em> with & entity"
    )
    mock_get_service_template.assert_called_with(SERVICE_ONE_ID, fake_uuid, None)


def test_should_show_delete_template_page_with_never_used_block(
    client_request,
    mock_get_service_template,
    mock_get_template_folders,
    fake_uuid,
    mocker,
):
    mocker.patch(
        "app.template_statistics_client.get_last_used_date_for_template",
        side_effect=HTTPError(
            response=Mock(status_code=404), message="Default message"
        ),
    )
    page = client_request.get(
        ".delete_service_template",
        service_id=SERVICE_ONE_ID,
        template_id=fake_uuid,
        _test_page_title=False,
    )
    assert (
        "Are you sure you want to delete ‘Two week reminder’?"
        in page.select(".banner-dangerous")[0].text
    )
    assert not page.select(".banner-dangerous p")
    assert normalize_spaces(page.select(".sms-message-wrapper")[0].text) == (
        "service one: Template <em>content</em> with & entity"
    )
    mock_get_service_template.assert_called_with(SERVICE_ONE_ID, fake_uuid, None)


@pytest.mark.parametrize("parent", [PARENT_FOLDER_ID, None])
def test_should_redirect_when_deleting_a_template(
    mocker,
    client_request,
    mock_delete_service_template,
    mock_get_template_folders,
    parent,
):
    mock_get_template_folders.return_value = [
        {
            "id": PARENT_FOLDER_ID,
            "name": "Folder",
            "parent": None,
            "users_with_permission": [ANY],
        }
    ]
    mock_get_service_template = mocker.patch(
        "app.service_api_client.get_service_template",
        return_value={
            "data": _template(
                "sms",
                "Hello",
                parent=parent,
            )
        },
    )

    client_request.post(
        ".delete_service_template",
        service_id=SERVICE_ONE_ID,
        template_id=TEMPLATE_ONE_ID,
        _expected_status=302,
        _expected_redirect=url_for(
            ".choose_template",
            service_id=SERVICE_ONE_ID,
            template_folder_id=parent,
        ),
    )

    mock_get_service_template.assert_called_with(SERVICE_ONE_ID, TEMPLATE_ONE_ID, None)
    mock_delete_service_template.assert_called_with(SERVICE_ONE_ID, TEMPLATE_ONE_ID)


@freeze_time("2016-01-01T20:00")
def test_should_show_page_for_a_deleted_template(
    client_request,
    mock_get_template_folders,
    mock_get_deleted_template,
    mock_get_user,
    mock_get_user_by_email,
    mock_has_permissions,
    fake_uuid,
):
    template_id = fake_uuid
    page = client_request.get(
        ".view_template",
        service_id=SERVICE_ONE_ID,
        template_id=template_id,
        _test_page_title=False,
    )

    content = str(page)
    assert (
        url_for(
            "main.edit_service_template",
            service_id=SERVICE_ONE_ID,
            template_id=fake_uuid,
        )
        not in content
    )
    assert (
        url_for("main.send_one_off", service_id=SERVICE_ONE_ID, template_id=fake_uuid)
        not in content
    )
    assert (
        page.select("p.hint")[0].text.strip()
        == "This template was deleted today at 15:00 America/New_York."
    )
    assert "Delete this template" not in page.select_one("main").text

    mock_get_deleted_template.assert_called_with(SERVICE_ONE_ID, template_id, None)


@pytest.mark.parametrize(
    "route",
    [
        "main.add_service_template",
        "main.edit_service_template",
        "main.delete_service_template",
    ],
)
def test_route_permissions(
    route,
    mocker,
    notify_admin,
    client_request,
    api_user_active,
    service_one,
    mock_get_service_template,
    mock_get_template_folders,
    fake_uuid,
):
    mocker.patch(
        "app.template_statistics_client.get_last_used_date_for_template",
        return_value="2012-01-01 12:00:00",
    )
    validate_route_permission(
        mocker,
        notify_admin,
        "GET",
        200,
        url_for(
            route,
            service_id=service_one["id"],
            template_type="sms",
            template_id=fake_uuid,
        ),
        [ServicePermission.MANAGE_TEMPLATES],
        api_user_active,
        service_one,
    )


def test_route_permissions_for_choose_template(
    mocker,
    notify_admin,
    client_request,
    api_user_active,
    mock_get_template_folders,
    service_one,
    mock_get_service_templates,
    mock_get_no_api_keys,
):
    mocker.patch("app.job_api_client.get_job")
    validate_route_permission(
        mocker,
        notify_admin,
        "GET",
        200,
        url_for(
            "main.choose_template",
            service_id=service_one["id"],
        ),
        [],
        api_user_active,
        service_one,
    )


@pytest.mark.parametrize(
    "route",
    [
        "main.add_service_template",
        "main.edit_service_template",
        "main.delete_service_template",
    ],
)
def test_route_invalid_permissions(
    route,
    mocker,
    notify_admin,
    client_request,
    api_user_active,
    service_one,
    mock_get_service_template,
    fake_uuid,
):
    validate_route_permission(
        mocker,
        notify_admin,
        "GET",
        403,
        url_for(
            route,
            service_id=service_one["id"],
            template_type="sms",
            template_id=fake_uuid,
        ),
        [ServicePermission.VIEW_ACTIVITY],
        api_user_active,
        service_one,
    )


@pytest.mark.parametrize(
    ("template_type", "expected"),
    [
        ("email", "New email template"),
        ("sms", "New text message template"),
    ],
)
def test_add_template_page_title(
    client_request,
    service_one,
    template_type,
    expected,
):
    service_one["permissions"] += [template_type]
    page = client_request.get(
        ".add_service_template",
        service_id=SERVICE_ONE_ID,
        template_type=template_type,
    )
    assert normalize_spaces(page.select_one("h1").text) == expected


# def test_can_create_email_template_with_emoji(
#     client_request, mock_create_service_template
# ):
#     client_request.post(
#         ".add_service_template",
#         service_id=SERVICE_ONE_ID,
#         template_type="email",
#         _data={
#             "name": "new name",
#             "subject": "Food incoming!",
#             "template_content": "here's a burrito 🌯",
#             "template_type": "email",
#             "service": SERVICE_ONE_ID,
#             "process_type": "normal",
#         },
#         _expected_status=302,
#     )
#     assert mock_create_service_template.called is True


# @pytest.mark.parametrize(
#     ("template_type", "expected_error"),
#     [
#         (
#             "sms",
#             (
#                 "Please remove the unaccepted character 🍜 in your message, then save again"
#             ),
#         ),
#     ],
# )
# def test_should_not_create_sms_template_with_emoji(
#     client_request,
#     service_one,
#     mock_create_service_template,
#     template_type,
#     expected_error,
# ):
#     service_one["permissions"] += [template_type]
#     page = client_request.post(
#         ".add_service_template",
#         service_id=SERVICE_ONE_ID,
#         template_type=template_type,
#         _data={
#             "name": "new name",
#             "template_content": "here are some noodles 🍜",
#             "template_type": "sms",
#             "service": SERVICE_ONE_ID,
#             "process_type": "normal",
#         },
#         _expected_status=200,
#     )
#     # print(page.main.prettify())
#     assert expected_error in normalize_spaces(
#         page.select_one("#template_content-error").text
#     )
#     assert mock_create_service_template.called is False


# @pytest.mark.parametrize(
#     ("template_type", "expected_error"),
#     [
#         (
#             "sms",
#             (
#                 "Please remove the unaccepted character 🍔 in your message, then save again"
#             ),
#         ),
#     ],
# )
# def test_should_not_update_sms_template_with_emoji(
#     mocker,
#     client_request,
#     service_one,
#     mock_get_service_template,
#     mock_update_service_template,
#     fake_uuid,
#     template_type,
#     expected_error,
# ):
#     service_one["permissions"] += [template_type]
#     return mocker.patch(
#         "app.service_api_client.get_service_template",
#         return_value=template_json(
#             SERVICE_ONE_ID,
#             fake_uuid,
#             type_=template_type,
#         ),
#     )
#     page = client_request.post(
#         ".edit_service_template",
#         service_id=SERVICE_ONE_ID,
#         template_id=fake_uuid,
#         _data={
#             "id": fake_uuid,
#             "name": "new name",
#             "template_content": "here's a burger 🍔",
#             "service": SERVICE_ONE_ID,
#             "template_type": template_type,
#             "process_type": "normal",
#         },
#         _expected_status=200,
#     )
#     assert expected_error in page.text
#     assert mock_update_service_template.called is False


@pytest.mark.parametrize(
    "template_type",
    [
        "sms",
    ],
)
def test_should_create_sms_template_without_downgrading_unicode_characters(
    client_request,
    service_one,
    mock_create_service_template,
    template_type,
):
    service_one["permissions"] += [template_type]

    msg = "here:\tare some “fancy quotes” and non\u200bbreaking\u200bspaces"

    client_request.post(
        ".add_service_template",
        service_id=SERVICE_ONE_ID,
        template_type="sms",
        _data={
            "name": "new name",
            "template_content": msg,
            "template_type": template_type,
            "service": SERVICE_ONE_ID,
        },
        expected_status=302,
    )

    mock_create_service_template.assert_called_with(
        ANY,  # name
        ANY,  # type
        msg,  # content
        ANY,  # service_id
        ANY,  # subject
        ANY,  # parent_folder_id
    )


def test_should_show_message_before_redacting_template(
    client_request,
    mock_get_service_template,
    service_one,
    fake_uuid,
):
    page = client_request.get(
        "main.redact_template",
        service_id=SERVICE_ONE_ID,
        template_id=fake_uuid,
        _test_page_title=False,
    )

    assert (
        "Are you sure you want to hide all personalized and conditional"
        " content after sending for increased privacy protection?"
    ) in page.select(".banner-dangerous")[0].text

    form = page.select(".banner-dangerous form")[0]

    assert "action" not in form
    assert form["method"] == "post"


def test_should_show_redact_template(
    client_request,
    mock_get_service_template,
    mock_get_template_folders,
    mock_redact_template,
    service_one,
    fake_uuid,
):
    page = client_request.post(
        "main.redact_template",
        service_id=SERVICE_ONE_ID,
        template_id=fake_uuid,
        _follow_redirects=True,
    )

    assert normalize_spaces(page.select(".banner-default-with-tick")[0].text) == (
        "Personalized content will be hidden for messages sent with this template"
    )

    mock_redact_template.assert_called_once_with(SERVICE_ONE_ID, fake_uuid)


def test_should_show_hint_once_template_redacted(
    client_request,
    mocker,
    service_one,
    mock_get_template_folders,
    fake_uuid,
):
    template = create_template(
        template_type="email", content="hi ((name))", redact_personalisation=True
    )
    mocker.patch(
        "app.service_api_client.get_service_template", return_value={"data": template}
    )

    page = client_request.get(
        "main.view_template",
        service_id=SERVICE_ONE_ID,
        template_id=fake_uuid,
        _test_page_title=False,
    )

    assert page.select(".hint")[0].text == "Personalization is hidden after sending"


def test_set_template_sender(
    client_request,
    fake_uuid,
    mock_update_service_template_sender,
    mock_get_service_template,
    single_sms_sender,
):
    data = {
        "sender": "1234",
    }

    client_request.post(
        "main.set_template_sender",
        service_id=SERVICE_ONE_ID,
        template_id=fake_uuid,
        _data=data,
    )

    mock_update_service_template_sender.assert_called_once_with(
        SERVICE_ONE_ID,
        fake_uuid,
        "1234",
    )


@pytest.mark.parametrize(
    ("template_type", "prefix_sms", "content", "expected_message", "expected_class"),
    [
        (
            "sms",
            False,
            "a" * 160,
            "Will be charged as 1 text message",
            None,
        ),
        (
            "sms",
            False,
            "a" * 161,
            "Will be charged as 2 text messages",
            None,
        ),
        (
            "sms",
            True,
            "a" * 147,
            "Will be charged as 1 text message",
            None,
        ),
        (
            # service name takes 13 characters, 148 + 13 = 161
            "sms",
            True,
            "a" * 148,
            "Will be charged as 2 text messages",
            None,
        ),
        (
            "sms",
            False,
            "a" * 918,
            "Will be charged as 6 text messages",
            None,
        ),
        (
            # Service name increases fragment count but doesn’t count
            # against total character limit
            "sms",
            True,
            "a" * 918,
            "Will be charged as 7 text messages",
            None,
        ),
        (
            # Can’t make a 7 fragment text template from content alone
            "sms",
            False,
            "a" * 919,
            "You have 1 character too many",
            "usa-error-message",
        ),
        (
            # Service name increases content count but character count
            # is based on content alone
            "sms",
            True,
            "a" * 919,
            "You have 1 character too many",
            "usa-error-message",
        ),
        (
            # Service name increases content count but character count
            # is based on content alone
            "sms",
            True,
            "a" * 920,
            "You have 2 characters too many",
            "usa-error-message",
        ),
        (
            "sms",
            False,
            "Ẅ" * 70,
            "Will be charged as 1 text message.",  # noqa E501
            None,
        ),
        (
            "sms",
            False,
            "Ẅ" * 71,
            "Will be charged as 2 text messages",
            None,
        ),
        (
            "sms",
            False,
            "Ẅ" * 918,
            "Will be charged as 14 text messages",
            None,
        ),
        (
            "sms",
            False,
            "Ẅ" * 919,
            "You have 1 character too many",
            "usa-error-message",
        ),
        (
            "sms",
            False,
            "Hello ((name))",
            "Will be charged as 1 text message (not including personalization).",
            None,
        ),
        (
            # Length of placeholder body doesn’t count towards fragment count
            "sms",
            False,
            f'Hello (( {"a" * 999} ))',
            "Will be charged as 1 text message (not including personalization).",
            None,
        ),
    ],
)
def test_content_count_json_endpoint(
    client_request,
    service_one,
    template_type,
    prefix_sms,
    content,
    expected_message,
    expected_class,
):
    service_one["prefix_sms"] = prefix_sms
    response = client_request.post_response(
        "main.count_content_length",
        service_id=SERVICE_ONE_ID,
        template_type=template_type,
        _data={
            "template_content": content,
        },
        _expected_status=200,
    )

    html = json.loads(response.get_data(as_text=True))["html"]
    snippet = BeautifulSoup(html, "html.parser").select_one("span")

    assert expected_message in normalize_spaces(snippet.text)

    if snippet.has_attr("class"):
        assert snippet["class"] == [expected_class]
    else:
        assert expected_class is None


@pytest.mark.parametrize(
    "template_type",
    [
        "email",
        "banana",
    ],
)
def test_content_count_json_endpoint_for_unsupported_template_types(
    client_request,
    template_type,
):
    client_request.post(
        "main.count_content_length",
        service_id=SERVICE_ONE_ID,
        template_type=template_type,
        content="foo",
        _expected_status=404,
    )
