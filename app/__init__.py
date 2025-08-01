import os
import pathlib
import re
import secrets
import sys
from functools import partial
from time import monotonic
from urllib.parse import unquote, urlparse, urlunparse

import jinja2
from flask import (
    current_app,
    flash,
    g,
    make_response,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask.globals import request_ctx
from flask_login import LoginManager, current_user
from flask_talisman import Talisman
from flask_wtf import CSRFProtect
from flask_wtf.csrf import CSRFError
from itsdangerous import BadSignature
from werkzeug.exceptions import HTTPException as WerkzeugHTTPException
from werkzeug.exceptions import abort
from werkzeug.local import LocalProxy

from app import proxy_fix
from app.asset_fingerprinter import asset_fingerprinter
from app.config import configs
from app.extensions import redis_client
from app.formatters import (
    convert_markdown_template,
    convert_time_unixtimestamp,
    convert_to_boolean,
    format_auth_type,
    format_billions,
    format_date,
    format_date_human,
    format_date_normal,
    format_date_numeric,
    format_date_short,
    format_datetime,
    format_datetime_24h,
    format_datetime_human,
    format_datetime_normal,
    format_datetime_relative,
    format_datetime_scheduled_notification,
    format_datetime_table,
    format_day_of_week,
    format_delta,
    format_delta_days,
    format_list_items,
    format_mobile_network,
    format_notification_status,
    format_notification_status_as_field_status,
    format_notification_status_as_time,
    format_notification_status_as_url,
    format_notification_type,
    format_number_in_pounds_as_currency,
    format_thousands,
    format_time_24h,
    format_yes_no,
    id_safe,
    iteration_count,
    linkable_name,
    message_count,
    message_count_label,
    message_count_noun,
    nl2br,
    recipient_count,
    recipient_count_label,
    round_to_significant_figures,
    square_metres_to_square_miles,
    valid_phone_number,
)
from app.models.organization import Organization
from app.models.service import Service
from app.models.user import AnonymousUser, User
from app.navigation import (
    CaseworkNavigation,
    HeaderNavigation,
    MainNavigation,
    OrgNavigation,
    SecondaryNavigation,
)
from app.notify_client import InviteTokenError
from app.notify_client.api_key_api_client import api_key_api_client
from app.notify_client.billing_api_client import billing_api_client
from app.notify_client.complaint_api_client import complaint_api_client
from app.notify_client.events_api_client import events_api_client
from app.notify_client.inbound_number_client import inbound_number_client
from app.notify_client.invite_api_client import invite_api_client
from app.notify_client.job_api_client import job_api_client
from app.notify_client.notification_api_client import notification_api_client
from app.notify_client.org_invite_api_client import org_invite_api_client
from app.notify_client.organizations_api_client import organizations_client
from app.notify_client.performance_dashboard_api_client import (
    performance_dashboard_api_client,
)
from app.notify_client.platform_stats_api_client import (
    platform_stats_api_client,
)
from app.notify_client.service_api_client import service_api_client
from app.notify_client.status_api_client import status_api_client
from app.notify_client.template_folder_api_client import (
    template_folder_api_client,
)
from app.notify_client.template_statistics_api_client import (
    template_statistics_client,
)
from app.notify_client.upload_api_client import upload_api_client
from app.notify_client.user_api_client import user_api_client
from app.url_converters import SimpleDateTypeConverter, TemplateTypeConverter
from app.utils.api_health import is_api_down
from app.utils.govuk_frontend_jinja.flask_ext import init_govuk_frontend
from notifications_python_client.errors import HTTPError
from notifications_utils import logging, request_helper
from notifications_utils.formatters import (
    formatted_list,
    get_lines_with_normalised_whitespace,
)
from notifications_utils.recipients import format_phone_number_human_readable
from notifications_utils.url_safe_token import generate_token

login_manager = LoginManager()
csrf = CSRFProtect()
talisman = Talisman()

# The current service attached to the request stack.
current_service = LocalProxy(partial(getattr, request_ctx, "service"))

# The current organization attached to the request stack.
current_organization = LocalProxy(partial(getattr, request_ctx, "organization"))

navigation = {
    "casework_navigation": CaseworkNavigation(),
    "main_navigation": MainNavigation(),
    "header_navigation": HeaderNavigation(),
    "org_navigation": OrgNavigation(),
    "secondary_navigation": SecondaryNavigation(),
}


def _csp(config):
    asset_domain = config["ASSET_DOMAIN"]
    api_public_url = config["API_PUBLIC_URL"]
    api_public_ws_url = config["API_PUBLIC_WS_URL"]

    return {
        "default-src": ["'self'", asset_domain],
        "frame-src": [
            "https://www.youtube.com",
            "https://www.youtube-nocookie.com",
            "https://www.googletagmanager.com",
        ],
        "frame-ancestors": "'none'",
        "form-action": "'self'",
        "script-src": [
            "'self'",
            asset_domain,
            "https://js-agent.newrelic.com",
            "https://gov-bam.nr-data.net",
            "https://www.googletagmanager.com",
            "https://www.google-analytics.com",
            "https://dap.digitalgov.gov",
            "https://cdn.socket.io",
        ],
        "connect-src": [
            "'self'",
            "https://gov-bam.nr-data.net",
            "https://www.google-analytics.com",
            f"{api_public_url}",
            f"{api_public_ws_url}",
        ],
        "style-src": ["'self'", asset_domain],
        "img-src": ["'self'", asset_domain],
    }


def create_app(application):
    @application.after_request
    def add_security_headers(response):
        response.headers["Cross-Origin-Embedder-Policy"] = "credentialless"
        return response

    @application.context_processor
    def inject_feature_flags():
        # this is where feature flags can be easily added as a dictionary within context
        feature_socket_enabled = application.config.get("FEATURE_SOCKET_ENABLED", False)
        return dict(
            FEATURE_SOCKET_ENABLED=feature_socket_enabled,
        )

    @application.context_processor
    def inject_is_api_down():
        return {"is_api_down": is_api_down()}

    @application.context_processor
    def inject_initial_signin_url():
        ttl = 24 * 60 * 60

        # make and store the state
        state = generate_token(
            str(request.remote_addr),
            current_app.config["SECRET_KEY"],
            current_app.config["DANGEROUS_SALT"],
        )

        state_key = f"login-state-{unquote(state)}"
        redis_client.set(state_key, state, ex=ttl)

        # make and store the nonce
        nonce = secrets.token_urlsafe()
        nonce_key = f"login-nonce-{unquote(nonce)}"
        redis_client.set(nonce_key, nonce, ex=ttl)

        url = os.getenv("LOGIN_DOT_GOV_INITIAL_SIGNIN_URL")
        if url is not None:
            url = url.replace("NONCE", nonce)
            url = url.replace("STATE", state)

        return {"initial_signin_url": url}

    notify_environment = os.environ["NOTIFY_ENVIRONMENT"]

    application.config.from_object(configs[notify_environment])
    asset_fingerprinter._asset_root = application.config["ASSET_PATH"]

    init_app(application)

    if "extensions" not in application.jinja_options:
        application.jinja_options["extensions"] = []

    init_govuk_frontend(application)
    init_jinja(application)

    for client in (
        csrf,
        login_manager,
        proxy_fix,
        request_helper,
        # API clients
        api_key_api_client,
        billing_api_client,
        complaint_api_client,
        events_api_client,
        inbound_number_client,
        invite_api_client,
        job_api_client,
        notification_api_client,
        org_invite_api_client,
        organizations_client,
        performance_dashboard_api_client,
        platform_stats_api_client,
        service_api_client,
        status_api_client,
        template_folder_api_client,
        template_statistics_client,
        upload_api_client,
        user_api_client,
        # External API clients
        redis_client,
    ):
        client.init_app(application)

    talisman.init_app(
        application,
        content_security_policy=_csp(application.config),
        content_security_policy_nonce_in=["style-src", "script-src"],
        permissions_policy={
            "accelerometer": '(self "https://www.youtube-nocookie.com")',
            "autoplay": '(self "https://www.youtube-nocookie.com")',
            "camera": "()",
            "geolocation": "()",
            "gyroscope": '(self "https://www.youtube-nocookie.com")',
            "local-fonts": "()",
            "magnetometer": "()",
            "microphone": "()",
            "midi": "()",
            "payment": "()",
            "screen-wake-lock": "()",
        },
        frame_options="deny",
        force_https=(application.config["HTTP_PROTOCOL"] == "https"),
    )
    logging.init_app(application)

    # Hopefully will help identify if there is a race condition causing the CSRF errors
    # that we have occasionally seen in our environments.
    for key in ("SECRET_KEY", "DANGEROUS_SALT"):
        try:
            value = application.config[key]
        except KeyError:
            application.logger.error(f"Env Var {key} doesn't exist.")
        else:
            try:
                data_len = len(value.strip())
            except (TypeError, AttributeError):
                application.logger.error(f"Env Var {key} invalid type: {type(value)}")
            else:
                if data_len:
                    application.logger.info(f"Env Var {key} is a non-zero length.")
                else:
                    application.logger.error(f"Env Var {key} is empty.")

    login_manager.login_view = "main.sign_in"
    login_manager.login_message_category = "default"
    login_manager.session_protection = None
    login_manager.anonymous_user = AnonymousUser

    # make sure we handle unicode correctly
    redis_client.redis_store.decode_responses = True

    from app.main import main as main_blueprint
    from app.status import status as status_blueprint

    application.register_blueprint(main_blueprint)

    application.register_blueprint(status_blueprint)

    add_template_filters(application)

    register_errorhandlers(application)

    setup_event_handlers()


def init_app(application):
    application.before_request(redirect_notify_to_beta)
    application.before_request(load_service_before_request)
    application.before_request(load_organization_before_request)
    application.before_request(request_helper.check_proxy_header_before_request)
    application.before_request(make_session_permanent)
    application.after_request(save_service_or_org_after_request)

    start = len(asset_fingerprinter._filesystem_path)
    font_paths = [
        str(item)[start:]
        for item in pathlib.Path(asset_fingerprinter._filesystem_path).glob(
            "fonts/*.woff2"
        )
    ]

    @application.context_processor
    def _attach_current_service():
        return {"current_service": current_service}

    @application.context_processor
    def _attach_current_organization():
        return {"current_org": current_organization}

    @application.context_processor
    def _attach_current_user():
        return {"current_user": current_user}

    @application.context_processor
    def _attach_enums():
        from app.enums import ServicePermission

        return {"ServicePermission": ServicePermission}

    @application.context_processor
    def _nav_selected():
        return navigation

    @application.context_processor
    def _attach_current_global_daily_messages():
        global_limit = 0
        remaining_global_messages = 0
        if current_app:
            if request.view_args:
                service_id = request.view_args.get(
                    "service_id", session.get("service_id")
                )
            else:
                service_id = session.get("service_id")

            if service_id:
                global_limit = current_app.config["GLOBAL_SERVICE_MESSAGE_LIMIT"]
                global_messages_count = (
                    service_api_client.get_global_notification_count(service_id)
                )
                remaining_global_messages = global_limit - global_messages_count.get(
                    "count"
                )
        return {
            "global_message_limit": global_limit,
            "daily_global_messages_remaining": remaining_global_messages,
        }

    @application.before_request
    def record_start_time():
        g.start = monotonic()
        g.endpoint = request.endpoint

    @application.context_processor
    def inject_global_template_variables():
        return {
            "asset_path": application.config["ASSET_PATH"],
            "header_colour": application.config["HEADER_COLOUR"],
            "asset_url": asset_fingerprinter.get_url,
            "font_paths": font_paths,
        }

    application.url_map.converters["uuid"].to_python = lambda self, value: value
    application.url_map.converters["template_type"] = TemplateTypeConverter
    application.url_map.converters["simple_date"] = SimpleDateTypeConverter


@login_manager.user_loader
def load_user(user_id):
    return User.from_id(user_id)


def make_session_permanent():
    """
    Make sessions permanent. By permanent, we mean "admin app sets when it expires". Normally the cookie would expire
    whenever you close the browser. With this, the session expiry is set in `config['PERMANENT_SESSION_LIFETIME']`
    (30 min) and is refreshed after every request. IE: you will be logged out after thirty minutes of inactivity.

    We don't _need_ to set this every request (it's saved within the cookie itself under the `_permanent` flag), only
    when you first log in/sign up/get invited/etc, but we do it just to be safe. For more reading, check here:
    https://stackoverflow.com/questions/34118093/flask-permanent-session-where-to-define-them
    """
    session.permanent = True


def create_beta_url(url):
    url_created = None
    try:
        url_created = urlparse(url)
        url_list = list(url_created)
        url_list[1] = "beta.notify.gov"
        url_for_redirect = urlunparse(url_list)
        return url_for_redirect
    except ValueError:
        # This might be happening due to IPv6, see issue # 1395.
        # If we see "'RequestContext' object has no attribute 'service'" in the logs
        # we can search around that timestamp and find this output, hopefully.
        # It may be sufficient to just catch and log, and prevent the stack trace from being in the logs
        # but we need to confirm the root cause first.
        current_app.logger.error(
            f"create_beta_url orig_url: {url} \
                                 url_created = {str(url_created)} url_for_redirect {str(url_for_redirect)}"
        )


def redirect_notify_to_beta():
    if (
        current_app.config["NOTIFY_ENVIRONMENT"] == "production"
        and "beta.notify.gov" not in request.url
    ):
        # TODO add debug here to trace what is going on with the URL for the 'RequestContext' error
        url_to_beta = create_beta_url(request.url)
        return redirect(url_to_beta, 302)


def load_service_before_request():
    if "/static/" in request.url:
        request_ctx.service = None
        return
    if request_ctx is not None:
        request_ctx.service = None

        if request.view_args:
            service_id = request.view_args.get("service_id", session.get("service_id"))
        else:
            service_id = session.get("service_id")

        if service_id:
            try:
                request_ctx.service = Service(
                    service_api_client.get_service(service_id)["data"]
                )
                stats = service_api_client.get_service_statistics(
                    service_id, limit_days=7
                )
                request_ctx.service.stats = stats
            except HTTPError as exc:
                # if service id isn't real, then 404 rather than 500ing later because we expect service to be set
                if exc.status_code == 404:
                    abort(404)
                else:
                    raise


def load_organization_before_request():
    if "/static/" in request.url:
        request_ctx.organization = None
        return
    if request_ctx is not None:
        request_ctx.organization = None

        if request.view_args:
            org_id = request.view_args.get("org_id")

            if org_id:
                try:
                    request_ctx.organization = Organization.from_id(org_id)
                except HTTPError as exc:
                    # if org id isn't real, then 404 rather than 500ing later because we expect org to be set
                    if exc.status_code == 404:
                        abort(404)
                    else:
                        raise


def save_service_or_org_after_request(response):
    # Only save the current session if the request is 200
    service_id = (
        request.view_args.get("service_id", None) if request.view_args else None
    )
    organization_id = (
        request.view_args.get("org_id", None) if request.view_args else None
    )
    if response.status_code == 200:
        if service_id:
            session["service_id"] = service_id
            session["organization_id"] = None
        elif organization_id:
            session["service_id"] = None
            session["organization_id"] = organization_id
    return response


def register_errorhandlers(application):  # noqa (C901 too complex)
    def _error_response(error_code, error_page_template=None):
        if error_page_template is None:
            error_page_template = error_code
        return make_response(
            render_template("error/{0}.html".format(error_page_template)), error_code
        )

    @application.errorhandler(HTTPError)
    def render_http_error(error):
        error_url = error.response.url if error.response else "unknown URL"

        application.logger.warning(
            f"API {error_url} failed with status {error.status_code} message {error.message}",
            exc_info=sys.exc_info(),
            stack_info=True,
        )

        error_code = error.status_code

        if error_code not in [401, 404, 403, 410]:
            # probably a 500 or 503.
            # it might be a 400, which we should handle as if it's an internal server error. If the API might
            # legitimately return a 400, we should handle that within the view or the client that calls it.
            application.logger.exception(
                f"API {error_url} failed with status {error.status_code} message {error.message}",
                exc_info=sys.exc_info(),
                stack_info=True,
            )

            error_code = 500

        return _error_response(error_code)

    @application.errorhandler(400)
    def handle_client_error(error):
        # This is tripped if we call `abort(400)`.
        application.logger.exception("Unhandled 400 client error")
        return _error_response(400, error_page_template=500)

    @application.errorhandler(410)
    def handle_gone(error):
        return _error_response(410)

    @application.errorhandler(404)
    def handle_not_found(error):
        return _error_response(404)

    @application.errorhandler(403)
    def handle_not_authorized(error):
        return _error_response(403)

    @application.errorhandler(401)
    def handle_no_permissions(error):
        return _error_response(401)

    @application.errorhandler(BadSignature)
    def handle_bad_token(error):
        # if someone has a malformed token
        flash("There’s something wrong with the link you’ve used.")
        return _error_response(404)

    @application.errorhandler(CSRFError)
    def handle_csrf(reason):
        application.logger.warning("csrf.error_message: {}".format(reason))

        if "user_id" not in session:
            application.logger.warning(
                "csrf.session_expired: Redirecting user to log in page"
            )

            return application.login_manager.unauthorized()

        application.logger.warning(
            "csrf.invalid_token: Aborting request, user_id: {user_id}",
            extra={"user_id": session["user_id"]},
        )

        return _error_response(400, error_page_template=500)

    @application.errorhandler(405)
    def handle_method_not_allowed(error):
        return _error_response(405, error_page_template=500)

    @application.errorhandler(WerkzeugHTTPException)
    def handle_http_error(error):
        if error.code == 301:
            # PermanentRedirect exception
            return error

        return _error_response(error.code)

    @application.errorhandler(InviteTokenError)
    def handle_bad_invite_token(error):
        flash(str(error))
        return redirect(url_for("main.sign_in"))

    @application.errorhandler(500)
    @application.errorhandler(Exception)
    def handle_bad_request(error):
        current_app.logger.exception(error)
        # We want the Flask in browser stacktrace
        if current_app.config.get("DEBUG", None):
            raise error
        return _error_response(500)


def setup_event_handlers():
    from flask_login import user_logged_in

    from app.event_handlers import on_user_logged_in

    user_logged_in.connect(on_user_logged_in)


def add_template_filters(application):
    application.add_template_filter(slugify)

    for fn in [
        format_auth_type,
        format_billions,
        format_datetime,
        format_datetime_24h,
        format_datetime_normal,
        format_datetime_scheduled_notification,
        format_datetime_table,
        valid_phone_number,
        linkable_name,
        format_date,
        format_date_human,
        format_date_normal,
        format_date_numeric,
        format_date_short,
        format_datetime_human,
        format_datetime_relative,
        format_day_of_week,
        format_delta,
        format_delta_days,
        format_time_24h,
        format_notification_status,
        format_notification_type,
        format_notification_status_as_time,
        format_notification_status_as_field_status,
        format_notification_status_as_url,
        format_number_in_pounds_as_currency,
        formatted_list,
        get_lines_with_normalised_whitespace,
        nl2br,
        format_phone_number_human_readable,
        format_thousands,
        id_safe,
        convert_to_boolean,
        convert_time_unixtimestamp,
        format_list_items,
        iteration_count,
        recipient_count,
        recipient_count_label,
        round_to_significant_figures,
        message_count_label,
        message_count,
        message_count_noun,
        format_mobile_network,
        format_yes_no,
        square_metres_to_square_miles,
        convert_markdown_template,
    ]:
        application.add_template_filter(fn)


def init_jinja(application):
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    template_folders = [
        os.path.join(repo_root, "app/templates"),
    ]
    jinja_loader = jinja2.FileSystemLoader(template_folders)
    application.jinja_loader = jinja_loader


def slugify(text):
    """
    Converts text to lowercase, replaces spaces with hyphens, and removes invalid characters.
    """
    return re.sub(r"[^a-z0-9-]", "", re.sub(r"\s+", "-", text.lower()))
