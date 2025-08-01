import ast
import inspect
import re

import pytest
from flask import current_app

from app.enums import ServicePermission
from tests import service_json
from tests.conftest import (
    ORGANISATION_ID,
    ORGANISATION_TWO_ID,
    SERVICE_ONE_ID,
    SERVICE_TWO_ID,
)


@pytest.mark.parametrize(
    ("user_services", "user_organizations", "expected_status", "organization_checked"),
    [
        ([SERVICE_ONE_ID], [], 200, False),
        ([SERVICE_ONE_ID, SERVICE_TWO_ID], [], 200, False),
        ([], [ORGANISATION_ID], 200, True),
        ([SERVICE_ONE_ID], [ORGANISATION_ID], 200, False),
        ([], [], 403, True),
        ([SERVICE_TWO_ID], [], 403, True),
        ([SERVICE_TWO_ID], [ORGANISATION_ID], 200, True),
        ([SERVICE_ONE_ID, SERVICE_TWO_ID], [ORGANISATION_ID], 200, False),
        ([], [ORGANISATION_TWO_ID], 403, True),
        ([], [ORGANISATION_ID, ORGANISATION_TWO_ID], 200, True),
    ],
)
def test_services_pages_that_org_users_are_allowed_to_see(
    client_request,
    mocker,
    api_user_active,
    mock_get_annual_usage_for_service,
    mock_get_monthly_usage_for_service,
    mock_get_free_sms_fragment_limit,
    mock_get_monthly_notification_stats,
    mock_get_service,
    mock_get_invites_for_service,
    mock_get_users_by_service,
    mock_get_template_folders,
    mock_get_organization,
    mock_has_jobs,
    user_services,
    user_organizations,
    expected_status,
    organization_checked,
):
    api_user_active["services"] = user_services
    api_user_active["organizations"] = user_organizations
    api_user_active["permissions"] = {
        service_id: [ServicePermission.MANAGE_USERS, ServicePermission.MANAGE_SETTINGS]
        for service_id in user_services
    }
    service = service_json(
        name="SERVICE WITH ORG",
        id_=SERVICE_ONE_ID,
        users=[api_user_active["id"]],
        organization_id=ORGANISATION_ID,
    )

    mock_get_service = mocker.patch(
        "app.notify_client.service_api_client.service_api_client.get_service",
        return_value={"data": service},
    )
    client_request.login(
        api_user_active,
        service=service if SERVICE_ONE_ID in user_services else None,
    )

    endpoints = (
        "main.usage",
        "main.manage_users",
    )

    for endpoint in endpoints:
        client_request.get(
            endpoint,
            service_id=SERVICE_ONE_ID,
            _expected_status=expected_status,
        )

    assert mock_get_service.called is organization_checked


def test_service_navigation_for_org_user(
    client_request,
    mocker,
    api_user_active,
    mock_get_annual_usage_for_service,
    mock_get_monthly_usage_for_service,
    mock_get_free_sms_fragment_limit,
    mock_get_monthly_notification_stats,
    mock_get_service,
    mock_get_invites_for_service,
    mock_get_users_by_service,
    mock_get_organization,
):
    api_user_active["services"] = []
    api_user_active["organizations"] = [ORGANISATION_ID]
    service = service_json(
        id_=SERVICE_ONE_ID,
        organization_id=ORGANISATION_ID,
    )
    mocker.patch("app.service_api_client.get_service", return_value={"data": service})
    client_request.login(api_user_active, service=service)

    page = client_request.get(
        "main.usage",
        service_id=SERVICE_ONE_ID,
    )
    assert [item.text.strip() for item in page.select("nav.nav a")] == [
        "Send messages",
        "Usage",
        "Team members",
    ]


@pytest.mark.parametrize(
    ("user_organizations", "expected_menu_items", "expected_status"),
    [
        (
            [],
            (
                "Send messages",
                "Sent messages",
            ),
            403,
        ),
        (
            [ORGANISATION_ID],
            (
                "Send messages",
                "Sent messages",
            ),
            200,
        ),
    ],
)
def test_service_user_without_manage_service_permission_can_see_usage_page_when_org_user(
    client_request,
    mocker,
    active_caseworking_user,
    mock_has_no_jobs,
    mock_get_annual_usage_for_service,
    mock_get_monthly_usage_for_service,
    mock_get_free_sms_fragment_limit,
    mock_get_monthly_notification_stats,
    mock_get_service,
    mock_get_invites_for_service,
    mock_get_users_by_service,
    mock_get_organization,
    mock_get_service_templates,
    mock_get_template_folders,
    mock_get_api_keys,
    user_organizations,
    expected_status,
    expected_menu_items,
):
    active_caseworking_user["services"] = [SERVICE_ONE_ID]
    active_caseworking_user["organizations"] = user_organizations
    service = service_json(
        id_=SERVICE_ONE_ID,
        organization_id=ORGANISATION_ID,
    )
    mocker.patch("app.service_api_client.get_service", return_value={"data": service})
    client_request.login(active_caseworking_user, service=service)
    page = client_request.get(
        "main.choose_template",
        service_id=SERVICE_ONE_ID,
    )
    assert (
        tuple(item.text.strip() for item in page.select("nav.nav a"))
        == expected_menu_items
    )

    client_request.get(
        "main.usage",
        service_id=SERVICE_ONE_ID,
        _expected_status=expected_status,
    )


def get_name_of_decorator_from_ast_node(node):
    if isinstance(node, ast.Name):
        return str(node.id)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        return get_name_of_decorator_from_ast_node(node.func)
    if isinstance(node, ast.Attribute):
        return node.value.id
    return "{}.{}".format(node.func.value.id, node.func.attr)


def get_decorators_for_function(function):
    for node in ast.walk(ast.parse(inspect.getsource(function))):
        if isinstance(node, ast.FunctionDef):
            for decorator in node.decorator_list:
                yield get_name_of_decorator_from_ast_node(decorator)


SERVICE_ID_ARGUMENT = "service_id"
ORGANISATION_ID_ARGUMENT = "org_id"


def get_routes_and_decorators(argument_name=None):
    import app.main.views as views

    for module_name, module in inspect.getmembers(views):
        for function_name, function in inspect.getmembers(module):
            if inspect.isfunction(function):
                decorators = list(get_decorators_for_function(function))
                if "main.route" in decorators and (
                    not argument_name
                    or argument_name in inspect.signature(function).parameters.keys()
                ):
                    yield "{}.{}".format(module_name, function_name), decorators


def format_decorators(decorators, indent=8):
    return "\n".join(
        "{}@{}".format(" " * indent, decorator) for decorator in decorators
    )


def test_code_to_extract_decorators_works_with_known_examples():
    assert (
        "templates.choose_template",
        [
            "main.route",
            "main.route",
            "main.route",
            "main.route",
            "main.route",
            "main.route",
            "user_has_permissions",
        ],
    ) in list(get_routes_and_decorators(SERVICE_ID_ARGUMENT))
    assert (
        "organizations.organization_dashboard",
        ["main.route", "user_has_permissions"],
    ) in list(get_routes_and_decorators(ORGANISATION_ID_ARGUMENT))
    assert (
        "platform_admin.platform_admin",
        ["main.route", "user_is_platform_admin"],
    ) in list(get_routes_and_decorators())


def test_routes_have_permissions_decorators():
    for endpoint, decorators in list(
        get_routes_and_decorators(SERVICE_ID_ARGUMENT)
    ) + list(get_routes_and_decorators(ORGANISATION_ID_ARGUMENT)):
        file, function = endpoint.split(".")

        assert "user_is_logged_in" not in decorators, (
            "@user_is_logged_in used on service or organization specific endpoint\n"
            "Use @user_has_permissions() or @user_is_platform_admin only\n"
            "app/main/views/{}.py::{}\n"
        ).format(file, function)

        if "user_is_platform_admin" in decorators:
            continue

        assert "user_has_permissions" in decorators, (
            "Missing @user_has_permissions decorator\n"
            "Use @user_has_permissions() or @user_is_platform_admin instead\n"
            "app/main/views/{}.py::{}\n"
        ).format(file, function)

    for _endpoint, decorators in get_routes_and_decorators():
        assert "login_required" not in decorators, (
            "@login_required found\n"
            "For consistency, use @user_is_logged_in() instead (from app.utils)\n"
            "app/main/views/{}.py::{}\n"
        ).format(file, function)

        if "user_is_platform_admin" in decorators:
            assert "user_has_permissions" not in decorators, (
                "@user_has_permissions and @user_is_platform_admin decorating same function\n"
                "You can only use one of these at a time\n"
                "app/main/views/{}.py::{}\n"
            ).format(file, function)
            assert "user_is_logged_in" not in decorators, (
                "@user_is_logged_in used with @user_is_platform_admin\n"
                "Use @user_is_platform_admin only\n"
                "app/main/views/{}.py::{}\n"
            ).format(file, function)


def test_routes_require_uuids(client_request):
    for rule in current_app.url_map.iter_rules():
        for param in re.findall("<([^>]*)>", rule.rule):
            if "_id" in param and not param.startswith("uuid:"):
                pytest.fail(("Should be <uuid:{}> in {}").format(param, rule.rule))
