import pytest

from app.enums import ServicePermission
from app.models.user import AnonymousUser, InvitedOrgUser, InvitedUser, User
from tests.conftest import SERVICE_ONE_ID, USER_ONE_ID


def test_anonymous_user(notify_admin):
    assert AnonymousUser().is_authenticated is False
    assert AnonymousUser().default_organization.name is None
    assert AnonymousUser().default_organization.domains == []
    assert AnonymousUser().default_organization.organization_type is None


def test_user(notify_admin):
    user_data = {
        "id": 1,
        "name": "Test User",
        "email_address": "test@user.gsa.gov",
        "mobile_number": "+12021231234",
        "state": "pending",
        "preferred_timezone": "America/Chicago",
        "failed_login_count": 0,
        "platform_admin": False,
    }
    user = User(user_data)

    assert user.id == 1
    assert user.name == "Test User"
    assert user.email_address == "test@user.gsa.gov"
    assert user.mobile_number == "+12021231234"
    assert user.state == "pending"

    # user has ten failed logins before being locked
    assert user.MAX_FAILED_LOGIN_COUNT == 10
    assert user.failed_login_count == 0
    assert user.locked is False

    # set failed logins to threshold
    user.failed_login_count = 10
    assert user.locked is True

    with pytest.raises(TypeError):
        user.has_permissions("to_do_bad_things")


def test_activate_user(notify_admin, api_user_pending, mock_activate_user):
    assert User(api_user_pending).activate() == User(api_user_pending)
    mock_activate_user.assert_called_once_with(api_user_pending["id"])


def test_activate_user_already_active(
    notify_admin, api_user_active, mock_activate_user
):
    assert User(api_user_active).activate() == User(api_user_active)
    assert mock_activate_user.called is False


@pytest.mark.parametrize(
    ("is_platform_admin", "value_in_session", "expected_result"),
    [
        (True, True, False),
        (True, False, True),
        (True, None, True),
        (False, True, False),
        (False, False, False),
        (False, None, False),
    ],
)
def test_platform_admin_flag_set_in_session(
    client_request, mocker, is_platform_admin, value_in_session, expected_result
):
    session_dict = {}
    if value_in_session is not None:
        session_dict["disable_platform_admin_view"] = value_in_session

    mocker.patch.dict("app.models.user.session", values=session_dict, clear=True)

    assert (
        User({"id": 1, "platform_admin": is_platform_admin}).platform_admin
        == expected_result
    )


def test_has_live_services(
    client_request,
    mock_get_non_empty_organizations_and_services_for_user,
    fake_uuid,
):
    user = User(
        {
            "id": fake_uuid,
            "platform_admin": False,
        }
    )
    assert len(user.live_services) == 5
    for service in user.live_services:
        assert service.live


def test_has_live_services_when_there_are_no_services(
    client_request,
    mock_get_organizations_and_services_for_user,
    fake_uuid,
):
    assert (
        User(
            {
                "id": fake_uuid,
                "platform_admin": False,
            }
        ).live_services
        == []
    )


def test_has_live_services_when_service_is_not_live(
    client_request,
    mock_get_empty_organizations_and_one_service_for_user,
    fake_uuid,
):
    assert (
        User(
            {
                "id": fake_uuid,
                "platform_admin": False,
            }
        ).live_services
        == []
    )


def test_invited_user_from_session_uses_id(
    client_request, mocker, mock_get_invited_user_by_id
):
    session_dict = {"invited_user_id": USER_ONE_ID}
    mocker.patch.dict("app.models.user.session", values=session_dict, clear=True)

    assert InvitedUser.from_session().id == USER_ONE_ID

    mock_get_invited_user_by_id.assert_called_once_with(USER_ONE_ID)


def test_invited_user_from_session_returns_none_if_nothing_present(
    client_request, mocker
):
    mocker.patch.dict("app.models.user.session", values={}, clear=True)
    assert InvitedUser.from_session() is None


def test_invited_org_user_from_session_uses_id(
    client_request, mocker, mock_get_invited_org_user_by_id, sample_org_invite
):
    session_dict = {"invited_org_user_id": sample_org_invite["id"]}
    mocker.patch.dict("app.models.user.session", values=session_dict, clear=True)

    assert InvitedOrgUser.from_session().id == sample_org_invite["id"]

    mock_get_invited_org_user_by_id.assert_called_once_with(sample_org_invite["id"])


def test_invited_org_user_from_session_returns_none_if_nothing_present(
    client_request, mocker
):
    mocker.patch.dict("app.models.user.session", values={}, clear=True)
    assert InvitedOrgUser.from_session() is None


def test_set_permissions(
    client_request, mocker, active_user_view_permissions, fake_uuid
):
    mock_api = mocker.patch("app.models.user.user_api_client.set_user_permissions")
    mock_event = mocker.patch("app.models.user.create_set_user_permissions_event")

    User(active_user_view_permissions).set_permissions(
        service_id=SERVICE_ONE_ID,
        permissions={ServicePermission.MANAGE_TEMPLATES},
        folder_permissions=[],
        set_by_id=fake_uuid,
    )

    mock_api.assert_called_once()
    mock_event.assert_called_once_with(
        service_id=SERVICE_ONE_ID,
        user_id=active_user_view_permissions["id"],
        original_ui_permissions={ServicePermission.VIEW_ACTIVITY},
        new_ui_permissions={ServicePermission.MANAGE_TEMPLATES},
        set_by_id=fake_uuid,
    )


def test_add_to_service(client_request, mocker, api_user_active, fake_uuid):
    mock_api = mocker.patch("app.models.user.user_api_client.add_user_to_service")
    mock_event = mocker.patch("app.models.user.create_add_user_to_service_event")

    User(api_user_active).add_to_service(
        service_id=SERVICE_ONE_ID,
        permissions={ServicePermission.MANAGE_TEMPLATES},
        folder_permissions=[],
        invited_by_id=fake_uuid,
    )

    mock_api.assert_called_once()
    mock_event.assert_called_once_with(
        service_id=SERVICE_ONE_ID,
        user_id=api_user_active["id"],
        invited_by_id=fake_uuid,
        ui_permissions={ServicePermission.MANAGE_TEMPLATES},
    )
