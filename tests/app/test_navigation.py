import pytest
from flask import Flask

from app import create_app
from app.navigation import (
    CaseworkNavigation,
    HeaderNavigation,
    MainNavigation,
    Navigation,
    OrgNavigation,
)
from tests.conftest import ORGANISATION_ID, SERVICE_ONE_ID, normalize_spaces

EXCLUDED_ENDPOINTS = tuple(map(Navigation.get_endpoint_with_blueprint, {
    'accept_invite',
    'accept_org_invite',
    'accessibility_statement',
    'action_blocked',
    'add_data_retention',
    'add_organisation',
    'add_service',
    'add_service_template',
    'api_callbacks',
    'api_documentation',
    'api_integration',
    'api_keys',
    'archive_service',
    'archive_user',
    'bat_phone',
    'begin_tour',
    'billing_details',
    'branding_and_customisation',
    'callbacks',
    'cancel_invited_org_user',
    'cancel_invited_user',
    'cancel_job',
    'change_user_auth',
    'check_and_resend_text_code',
    'check_and_resend_verification_code',
    'check_messages',
    'check_notification',
    'check_tour_notification',
    'choose_account',
    'choose_service',
    'choose_template',
    'choose_template_to_copy',
    'clear_cache',
    'confirm_edit_user_email',
    'confirm_edit_user_mobile_number',
    'confirm_redact_template',
    'conversation',
    'conversation_reply',
    'conversation_reply_with_template',
    'conversation_updates',
    'copy_template',
    'count_content_length',
    'create_and_send_messages',
    'create_api_key',
    'create_email_branding',
    'data_retention',
    'delete_service_template',
    'delete_template_folder',
    'delivery_and_failure',
    'delivery_status_callback',
    'design_content',
    'documentation',
    'download_notifications_csv',
    'download_organisation_usage_report',
    'edit_and_format_messages',
    'edit_data_retention',
    'edit_organisation_billing_details',
    'edit_organisation_domains',
    'edit_organisation_email_branding',
    'edit_organisation_go_live_notes',
    'edit_organisation_name',
    'edit_organisation_notes',
    'edit_organisation_type',
    'edit_organisation_user',
    'edit_service_billing_details',
    'edit_service_notes',
    'edit_service_template',
    'edit_sms_provider_ratio',
    'edit_user_email',
    'edit_user_mobile_number',
    'edit_user_permissions',
    'email_branding',
    'email_branding_govuk',
    'email_branding_govuk_and_org',
    'email_branding_nhs',
    'email_branding_organisation',
    'email_branding_request',
    'email_branding_something_else',
    'email_not_received',
    'email_template',
    'error',
    'estimate_usage',
    'features',
    'features_email',
    'features_sms',
    'feedback',
    'find_services_by_name',
    'find_users_by_email',
    'forgot_password',
    'get_billing_report',
    'get_daily_volumes',
    'get_daily_sms_provider_volumes',
    'get_volumes_by_service',
    'get_example_csv',
    'get_notifications_as_json',
    'get_started',
    'get_started_old',
    'go_to_dashboard_after_tour',
    'guest_list',
    'guidance_index',
    'history',
    'how_to_pay',
    'inbound_sms_admin',
    'inbox',
    'inbox_download',
    'inbox_updates',
    'index',
    'information_risk_management',
    'information_security',
    'integration_testing',
    'invite_org_user',
    'invite_user',
    'link_service_to_organisation',
    'live_services',
    'live_services_csv',
    'manage_org_users',
    'manage_template_folder',
    'manage_users',
    'message_status',
    'monthly',
    'new_password',
    'notifications_sent_by_service',
    'old_guest_list',
    'old_integration_testing',
    'old_roadmap',
    'old_service_dashboard',
    'old_terms',
    'old_using_notify',
    'organisation_billing',
    'organisation_dashboard',
    'organisation_preview_email_branding',
    'organisation_settings',
    'organisation_trial_mode_services',
    'organisations',
    'performance',
    'platform_admin',
    'platform_admin_list_complaints',
    'platform_admin_reports',
    'platform_admin_splash_page',
    'pricing',
    'privacy',
    'received_text_messages_callback',
    'redact_template',
    'register',
    'register_from_invite',
    'register_from_org_invite',
    'registration_continue',
    'remove_user_from_organisation',
    'remove_user_from_service',
    'request_to_go_live',
    'resend_email_link',
    'resend_email_verification',
    'resume_service',
    'revalidate_email_sent',
    'revoke_api_key',
    'roadmap',
    'security',
    'security_policy',
    'send_files_by_email',
    'send_files_by_email_contact_details',
    'send_messages',
    'send_notification',
    'send_one_off',
    'send_one_off_step',
    'send_one_off_to_myself',
    'service_add_email_reply_to',
    'service_add_sms_sender',
    'service_confirm_delete_email_reply_to',
    'service_confirm_delete_sms_sender',
    'service_dashboard',
    'service_dashboard_updates',
    'service_delete_email_reply_to',
    'service_delete_sms_sender',
    'service_edit_email_reply_to',
    'service_edit_sms_sender',
    'service_email_reply_to',
    'service_name_change',
    'service_preview_email_branding',
    'service_set_auth_type',
    'service_set_channel',
    'service_set_email_branding',
    'service_set_inbound_number',
    'service_set_inbound_sms',
    'service_set_international_sms',
    'service_set_permission',
    'service_set_reply_to_email',
    'service_set_sms_prefix',
    'service_settings',
    'service_sms_senders',
    'service_switch_count_as_live',
    'service_switch_live',
    'service_verify_reply_to_address',
    'service_verify_reply_to_address_updates',
    'services_or_dashboard',
    'set_free_sms_allowance',
    'set_message_limit',
    'set_rate_limit',
    'set_sender',
    'set_template_sender',
    'show_accounts_or_dashboard',
    'sign_in',
    'sign_out',
    'start_job',
    'submit_request_to_go_live',
    'support',
    'support_public',
    'suspend_service',
    'template_history',
    'template_usage',
    'terms',
    'thanks',
    'tour_step',
    'triage',
    'trial_mode',
    'trial_mode_new',
    'trial_services',
    'two_factor_sms',
    'two_factor_email',
    'two_factor_email_interstitial',
    'two_factor_email_sent',
    'two_factor_webauthn',
    'update_email_branding',
    'uploads',
    'usage',
    'user_information',
    'user_profile',
    'user_profile_confirm_delete_mobile_number',
    'user_profile_confirm_delete_security_key',
    'user_profile_delete_security_key',
    'user_profile_disable_platform_admin_view',
    'user_profile_email',
    'user_profile_email_authenticate',
    'user_profile_email_confirm',
    'user_profile_manage_security_key',
    'user_profile_mobile_number',
    'user_profile_mobile_number_authenticate',
    'user_profile_mobile_number_confirm',
    'user_profile_mobile_number_delete',
    'user_profile_name',
    'user_profile_password',
    'user_profile_security_keys',
    'using_notify',
    'verify',
    'verify_email',
    'view_job',
    'view_job_csv',
    'view_job_updates',
    'view_jobs',
    'view_notification',
    'view_notification_updates',
    'view_notifications',
    'view_notifications_csv',
    'view_provider',
    'view_providers',
    'view_template',
    'view_template_version',
    'view_template_versions',
    'webauthn_begin_register',
    'webauthn_complete_register',
    'webauthn_begin_authentication',
    'webauthn_complete_authentication',
    'who_its_for',
}))


def flask_app():
    app = Flask('app')
    create_app(app)

    ctx = app.app_context()
    ctx.push()

    yield app


all_endpoints = [
    rule.endpoint for rule in next(flask_app()).url_map.iter_rules()
]

navigation_instances = (
    MainNavigation(),
    HeaderNavigation(),
    OrgNavigation(),
    CaseworkNavigation(),
)


@pytest.mark.parametrize(
    'navigation_instance',
    navigation_instances,
    ids=(x.__class__.__name__ for x in navigation_instances)
)
def test_navigation_items_are_properly_defined(navigation_instance):
    for endpoint in navigation_instance.endpoints_with_navigation:
        assert (
            endpoint in all_endpoints
        ), '{} is not a real endpoint (in {}.mapping)'.format(
            endpoint,
            type(navigation_instance).__name__
        )
        assert (
            navigation_instance.endpoints_with_navigation.count(endpoint) == 1
        ), '{} found more than once in {}.mapping'.format(
            endpoint,
            type(navigation_instance).__name__
        )


def test_excluded_navigation_items_are_properly_defined():
    for endpoint in EXCLUDED_ENDPOINTS:
        assert (
            endpoint in all_endpoints
        ), f'{endpoint} is not a real endpoint (in EXCLUDED_ENDPOINTS)'

        assert (
            EXCLUDED_ENDPOINTS.count(endpoint) == 1
        ), f'{endpoint} found more than once in EXCLUDED_ENDPOINTS'


@pytest.mark.parametrize(
    'navigation_instance',
    navigation_instances,
    ids=(x.__class__.__name__ for x in navigation_instances)
)
def test_all_endpoints_are_covered(navigation_instance):
    covered_endpoints = (
        navigation_instance.endpoints_with_navigation +
        EXCLUDED_ENDPOINTS +
        ('static', 'status.show_status', 'status.show_redis_status', 'metrics')
    )

    for endpoint in all_endpoints:
        assert endpoint in covered_endpoints, f'{endpoint} is not listed or excluded'


@pytest.mark.parametrize(
    'navigation_instance',
    navigation_instances,
    ids=(x.__class__.__name__ for x in navigation_instances)
)
def test_raises_on_invalid_navigation_item(
    client_request, navigation_instance
):
    with pytest.raises(expected_exception=KeyError):
        navigation_instance.is_selected('foo')


@pytest.mark.parametrize('endpoint, selected_nav_item', [
    ('main.choose_template', 'Send messages'),
    ('main.manage_users', 'Team members'),
])
def test_a_page_should_nave_selected_navigation_item(
    client_request,
    mock_get_service_templates,
    mock_get_users_by_service,
    mock_get_invites_for_service,
    mock_get_template_folders,
    mock_get_api_keys,
    endpoint,
    selected_nav_item,
):
    page = client_request.get(endpoint, service_id=SERVICE_ONE_ID)
    selected_nav_items = page.select('.navigation a.selected')
    assert len(selected_nav_items) == 1
    assert selected_nav_items[0].text.strip() == selected_nav_item


@pytest.mark.parametrize('endpoint, selected_nav_item', [
    # ('main.documentation', 'Documentation'),
    ('main.support', 'Support'),
])
def test_a_page_should_nave_selected_header_navigation_item(
    client_request,
    endpoint,
    selected_nav_item,
):
    page = client_request.get(endpoint, service_id=SERVICE_ONE_ID)
    selected_nav_items = page.select('.usa-current')
    assert len(selected_nav_items) == 1
    assert selected_nav_items[0].text.strip() == selected_nav_item


@pytest.mark.parametrize('endpoint, selected_nav_item', [
    ('main.organisation_dashboard', 'Usage'),
    ('main.manage_org_users', 'Team members'),
])
def test_a_page_should_nave_selected_org_navigation_item(
    client_request,
    mock_get_organisation,
    mock_get_users_for_organisation,
    mock_get_invited_users_for_organisation,
    endpoint,
    selected_nav_item,
    mocker
):
    mocker.patch(
        'app.organisations_client.get_services_and_usage', return_value={'services': {}}
    )
    page = client_request.get(endpoint, org_id=ORGANISATION_ID)
    selected_nav_items = page.select('.navigation a.selected')
    assert len(selected_nav_items) == 1
    assert selected_nav_items[0].text.strip() == selected_nav_item


def test_navigation_urls(
    client_request,
    mock_get_service_templates,
    mock_get_template_folders,
    mock_get_api_keys,
):
    page = client_request.get('main.choose_template', service_id=SERVICE_ONE_ID)
    assert [
        a['href'] for a in page.select('.navigation a')
    ] == [
        '/services/{}'.format(SERVICE_ONE_ID),
        '/services/{}/templates'.format(SERVICE_ONE_ID),
        '/services/{}/users'.format(SERVICE_ONE_ID),
        '/services/{}/usage'.format(SERVICE_ONE_ID),
        '/services/{}/service-settings'.format(SERVICE_ONE_ID),
        # '/services/{}/api'.format(SERVICE_ONE_ID),
    ]


def test_caseworkers_get_caseworking_navigation(
    client_request,
    mock_get_template_folders,
    mock_get_service_templates,
    mock_has_no_jobs,
    mock_get_api_keys,
    active_caseworking_user,
):
    client_request.login(active_caseworking_user)
    page = client_request.get('main.choose_template', service_id=SERVICE_ONE_ID)
    assert normalize_spaces(page.select_one('header + .govuk-width-container nav').text) == (
        'Send messages Sent messages Team members'
    )


def test_caseworkers_see_jobs_nav_if_jobs_exist(
    client_request,
    mock_get_service_templates,
    mock_get_template_folders,
    mock_has_jobs,
    active_caseworking_user,
    mock_get_api_keys,
):
    client_request.login(active_caseworking_user)
    page = client_request.get('main.choose_template', service_id=SERVICE_ONE_ID)
    assert normalize_spaces(page.select_one('header + .govuk-width-container nav').text) == (
        'Send messages Sent messages Team members'
    )
