import calendar
from datetime import datetime
from functools import partial
from itertools import groupby

from flask import Response, abort, jsonify, render_template, request, session, url_for
from flask_login import current_user
from flask_socketio import emit
from werkzeug.utils import redirect

from app import (
    billing_api_client,
    current_service,
    job_api_client,
    service_api_client,
    socketio,
    template_statistics_client,
)
from app.formatters import format_date_numeric, format_datetime_numeric, get_time_left
from app.main import main
from app.statistics_utils import get_formatted_percentage
from app.utils import (
    DELIVERED_STATUSES,
    FAILURE_STATUSES,
    REQUESTED_STATUSES,
    service_has_permission,
)
from app.utils.csv import Spreadsheet
from app.utils.pagination import generate_next_dict, generate_previous_dict
from app.utils.time import get_current_financial_year
from app.utils.user import user_has_permissions
from notifications_utils.recipients import format_phone_number_human_readable


@socketio.on("fetch_daily_stats")
def handle_fetch_daily_stats():
    service_id = session.get("service_id")
    if service_id:
        date_range = get_stats_date_range()
        daily_stats = service_api_client.get_service_notification_statistics_by_day(
            service_id, start_date=date_range["start_date"], days=date_range["days"]
        )
        emit("daily_stats_update", daily_stats)
    else:
        emit("error", {"error": "No service_id provided"})


@socketio.on("fetch_daily_stats_by_user")
def handle_fetch_daily_stats_by_user():
    service_id = session.get("service_id")
    user_id = session.get("user_id")
    if service_id and user_id:
        date_range = get_stats_date_range()
        daily_stats_by_user = (
            service_api_client.get_user_service_notification_statistics_by_day(
                service_id,
                user_id,
                start_date=date_range["start_date"],
                days=date_range["days"],
            )
        )
        emit("daily_stats_by_user_update", daily_stats_by_user)
    else:
        emit("error", {"error": "No service_id or user_id provided"})


@main.route("/services/<uuid:service_id>/dashboard")
@user_has_permissions("view_activity", "send_messages")
def old_service_dashboard(service_id):
    return redirect(url_for(".service_dashboard", service_id=service_id))


@main.route("/services/<uuid:service_id>")
@user_has_permissions()
def service_dashboard(service_id):
    if session.get("invited_user_id"):
        session.pop("invited_user_id", None)
        session["service_id"] = service_id

    if not current_user.has_permissions("view_activity"):
        return redirect(url_for("main.choose_template", service_id=service_id))

    job_response = job_api_client.get_jobs(service_id)["data"]
    service_data_retention_days = 7

    jobs = [
        {
            "job_id": job["id"],
            "time_left": get_time_left(job["created_at"]),
            "download_link": url_for(
                ".view_job_csv", service_id=current_service.id, job_id=job["id"]
            ),
            "view_job_link": url_for(
                ".view_job", service_id=current_service.id, job_id=job["id"]
            ),
            "created_at": job["created_at"],
            "processing_finished": job.get("processing_finished"),
            "processing_started": job.get("processing_started"),
            "notification_count": job["notification_count"],
            "created_by": job["created_by"],
            "template_name": job["template_name"],
            "original_file_name": job["original_file_name"],
        }
        for job in job_response
    ]
    return render_template(
        "views/dashboard/dashboard.html",
        updates_url=url_for(".service_dashboard_updates", service_id=service_id),
        partials=get_dashboard_partials(service_id),
        jobs=jobs,
        service_data_retention_days=service_data_retention_days,
    )


@main.route("/services/<uuid:service_id>/dashboard.json")
@user_has_permissions("view_activity")
def service_dashboard_updates(service_id):
    return jsonify(**get_dashboard_partials(service_id))


@main.route("/services/<uuid:service_id>/template-activity")
@user_has_permissions("view_activity")
def template_history(service_id):
    return redirect(url_for("main.template_usage", service_id=service_id), code=301)


@main.route("/services/<uuid:service_id>/template-usage")
@user_has_permissions("view_activity")
def template_usage(service_id):
    year, current_financial_year = requested_and_current_financial_year(request)
    stats = template_statistics_client.get_monthly_template_usage_for_service(
        service_id, year
    )

    stats = sorted(stats, key=lambda x: (x["count"]), reverse=True)

    def get_monthly_template_stats(month_name, stats):
        return {
            "name": month_name,
            "templates_used": [
                {
                    "id": stat["template_id"],
                    "name": stat["name"],
                    "type": stat["type"],
                    "requested_count": stat["count"],
                }
                for stat in stats
                if calendar.month_name[int(stat["month"])] == month_name
            ],
        }

    months = [
        get_monthly_template_stats(month, stats)
        for month in get_months_for_financial_year(year, time_format="%B")
    ]

    return render_template(
        "views/dashboard/all-template-statistics.html",
        months=months,
        stats=stats,
        most_used_template_count=max(
            (
                max(
                    (
                        template["requested_count"]
                        for template in month["templates_used"]
                    ),
                    default=0,
                )
                for month in months
            ),
            default=0,
        ),
        years=get_tuples_of_financial_years(
            partial(url_for, ".template_usage", service_id=service_id),
            start=current_financial_year - 2,
            end=current_financial_year,
        ),
        selected_year=year,
    )


@main.route("/services/<uuid:service_id>/usage")
@user_has_permissions("manage_service", allow_org_user=True)
def usage(service_id):
    year, current_financial_year = requested_and_current_financial_year(request)

    free_sms_allowance = billing_api_client.get_free_sms_fragment_limit_for_year(
        service_id
    )

    units = billing_api_client.get_monthly_usage_for_service(service_id, year)

    yearly_usage = billing_api_client.get_annual_usage_for_service(service_id, year)

    more_stats = format_monthly_stats_to_list(
        service_api_client.get_monthly_notification_stats(service_id, year)["data"]
    )
    return render_template(
        "views/usage.html",
        months=list(get_monthly_usage_breakdown(year, units, more_stats)),
        selected_year=year,
        years=get_tuples_of_financial_years(
            partial(url_for, ".usage", service_id=service_id),
            start=current_financial_year - 2,
            end=current_financial_year,
        ),
        **get_annual_usage_breakdown(yearly_usage, free_sms_allowance),
    )


@main.route("/services/<uuid:service_id>/monthly")
@user_has_permissions("view_activity")
def monthly(service_id):
    year, current_financial_year = requested_and_current_financial_year(request)
    return render_template(
        "views/dashboard/monthly.html",
        months=format_monthly_stats_to_list(
            service_api_client.get_monthly_notification_stats(service_id, year)["data"]
        ),
        years=get_tuples_of_financial_years(
            partial_url=partial(url_for, ".monthly", service_id=service_id),
            start=current_financial_year - 2,
            end=current_financial_year,
        ),
        selected_year=year,
    )


@main.route("/services/<uuid:service_id>/inbox")
@user_has_permissions("view_activity")
@service_has_permission("inbound_sms")
def inbox(service_id):
    return render_template(
        "views/dashboard/inbox.html",
        partials=get_inbox_partials(service_id),
        updates_url=url_for(
            ".inbox_updates", service_id=service_id, page=request.args.get("page")
        ),
    )


@main.route("/services/<uuid:service_id>/inbox.json")
@user_has_permissions("view_activity")
@service_has_permission("inbound_sms")
def inbox_updates(service_id):
    return jsonify(get_inbox_partials(service_id))


@main.route("/services/<uuid:service_id>/inbox.csv")
@user_has_permissions("view_activity")
def inbox_download(service_id):
    return Response(
        Spreadsheet.from_rows(
            [
                [
                    "Phone number",
                    "Message",
                    "Received",
                ]
            ]
            + [
                [
                    format_phone_number_human_readable(message["user_number"]),
                    message["content"].lstrip(("=+-@")),
                    format_datetime_numeric(message["created_at"]),
                ]
                for message in service_api_client.get_inbound_sms(service_id)["data"]
            ]
        ).as_csv_data,
        mimetype="text/csv",
        headers={
            "Content-Disposition": 'inline; filename="Received text messages {}.csv"'.format(
                format_date_numeric(datetime.utcnow().isoformat())
            )
        },
    )


def get_inbox_partials(service_id):
    page = int(request.args.get("page", 1))
    inbound_messages_data = service_api_client.get_most_recent_inbound_sms(
        service_id, page=page
    )
    inbound_messages = inbound_messages_data["data"]
    if not inbound_messages:
        inbound_number = current_service.inbound_number
    else:
        inbound_number = None

    prev_page = None
    if page > 1:
        prev_page = generate_previous_dict("main.inbox", service_id, page)
    next_page = None
    if inbound_messages_data["has_next"]:
        next_page = generate_next_dict("main.inbox", service_id, page)

    return {
        "messages": render_template(
            "views/dashboard/_inbox_messages.html",
            messages=inbound_messages,
            inbound_number=inbound_number,
            prev_page=prev_page,
            next_page=next_page,
        )
    }


def filter_out_cancelled_stats(template_statistics):
    return [s for s in template_statistics if s["status"] != "cancelled"]


def aggregate_template_usage(template_statistics, sort_key="count"):
    template_statistics = filter_out_cancelled_stats(template_statistics)
    templates = []
    for k, v in groupby(
        sorted(template_statistics, key=lambda x: x["template_id"]),
        key=lambda x: x["template_id"],
    ):
        template_stats = list(v)

        templates.append(
            {
                "template_id": k,
                "template_name": template_stats[0]["template_name"],
                "template_type": template_stats[0]["template_type"],
                "count": sum(s["count"] for s in template_stats),
            }
        )

    return sorted(templates, key=lambda x: x[sort_key], reverse=True)


def aggregate_notifications_stats(template_statistics):
    template_statistics = filter_out_cancelled_stats(template_statistics)
    notifications = {
        template_type: {status: 0 for status in ("requested", "delivered", "failed")}
        for template_type in ["sms", "email"]
    }
    for stat in template_statistics:
        notifications[stat["template_type"]]["requested"] += stat["count"]
        if stat["status"] in DELIVERED_STATUSES:
            notifications[stat["template_type"]]["delivered"] += stat["count"]
        elif stat["status"] in FAILURE_STATUSES:
            notifications[stat["template_type"]]["failed"] += stat["count"]

    return notifications


def get_dashboard_partials(service_id):
    all_statistics = template_statistics_client.get_template_statistics_for_service(
        service_id, limit_days=7
    )
    template_statistics = aggregate_template_usage(all_statistics)
    stats = aggregate_notifications_stats(all_statistics)

    dashboard_totals = (get_dashboard_totals(stats),)
    free_sms_allowance = billing_api_client.get_free_sms_fragment_limit_for_year(
        current_service.id,
    )
    # These 2 calls will update the dashboard sms allowance count while in trial mode.
    billing_api_client.get_monthly_usage_for_service(
        service_id, get_current_financial_year()
    )
    billing_api_client.create_or_update_free_sms_fragment_limit(
        service_id, free_sms_fragment_limit=free_sms_allowance
    )

    yearly_usage = billing_api_client.get_annual_usage_for_service(
        service_id,
        get_current_financial_year(),
    )
    return {
        "upcoming": render_template(
            "views/dashboard/_upcoming.html",
        ),
        "inbox": render_template(
            "views/dashboard/_inbox.html",
        ),
        "totals": render_template(
            "views/dashboard/_totals.html",
            service_id=service_id,
            statistics=dashboard_totals[0],
        ),
        "template-statistics": render_template(
            "views/dashboard/template-statistics.html",
            template_statistics=template_statistics,
            most_used_template_count=max(
                [row["count"] for row in template_statistics] or [0]
            ),
        ),
        "usage": render_template(
            "views/dashboard/_usage.html",
            **get_annual_usage_breakdown(yearly_usage, free_sms_allowance),
        ),
    }


def get_dashboard_totals(statistics):
    for msg_type in statistics.values():
        msg_type["failed_percentage"] = get_formatted_percentage(
            msg_type["failed"], msg_type["requested"]
        )
        msg_type["show_warning"] = float(msg_type["failed_percentage"]) > 3
    return statistics


def get_annual_usage_breakdown(usage, free_sms_fragment_limit):
    sms = get_usage_breakdown_by_type(usage, "sms")
    sms_chargeable_units = sum(row["chargeable_units"] for row in sms)
    sms_free_allowance = free_sms_fragment_limit
    sms_cost = sum(row["cost"] for row in sms)

    emails = get_usage_breakdown_by_type(usage, "email")
    emails_sent = sum(row["notifications_sent"] for row in emails)

    return {
        "emails_sent": emails_sent,
        "sms_free_allowance": sms_free_allowance,
        "sms_sent": sms_chargeable_units,
        "sms_allowance_remaining": max(0, (sms_free_allowance - sms_chargeable_units)),
        "sms_cost": sms_cost,
        "sms_breakdown": sms,
    }


def format_monthly_stats_to_list(historical_stats):
    return sorted(
        (
            dict(
                date=key,
                future=yyyy_mm_to_datetime(key) > datetime.utcnow(),
                name=yyyy_mm_to_datetime(key).strftime("%B"),
                **aggregate_status_types(value),
            )
            for key, value in historical_stats.items()
        ),
        key=lambda x: x["date"],
    )


def yyyy_mm_to_datetime(string):
    return datetime(int(string[0:4]), int(string[5:7]), 1)


def aggregate_status_types(counts_dict):
    return get_dashboard_totals(
        {
            "{}_counts".format(message_type): {
                "failed": sum(stats.get(status, 0) for status in FAILURE_STATUSES),
                "requested": sum(stats.get(status, 0) for status in REQUESTED_STATUSES),
            }
            for message_type, stats in counts_dict.items()
        }
    )


def get_months_for_financial_year(year, time_format="%B"):
    return [month.strftime(time_format) for month in (get_months_for_year(1, 13, year))]


def get_current_month_for_financial_year(year):
    current_month = datetime.now().month
    return current_month


def get_stats_date_range():
    current_financial_year = get_current_financial_year()
    current_month = get_current_month_for_financial_year(current_financial_year)
    start_date = datetime.now().strftime("%Y-%m-%d")
    days = 7
    return {
        "current_financial_year": current_financial_year,
        "current_month": current_month,
        "start_date": start_date,
        "days": days,
    }


def get_months_for_year(start, end, year):
    return [datetime(year, month, 1) for month in range(start, end)]


def get_usage_breakdown_by_type(usage, notification_type):
    return [row for row in usage if row["notification_type"] == notification_type]


def get_monthly_usage_breakdown(year, monthly_usage, more_stats):
    sms = get_usage_breakdown_by_type(monthly_usage, "sms")

    for month in get_months_for_financial_year(year):
        monthly_sms = [row for row in sms if row["month"] == month]
        sms_free_allowance_used = sum(row["free_allowance_used"] for row in monthly_sms)
        sms_cost = sum(row["cost"] for row in monthly_sms)
        sms_breakdown = [row for row in monthly_sms if row["charged_units"]]
        sms_counts = [
            row["sms_counts"]
            for row in more_stats
            if row["sms_counts"] and row["name"] == month
        ]

        yield {
            "month": month,
            "sms_free_allowance_used": sms_free_allowance_used,
            "sms_breakdown": sms_breakdown,
            "sms_cost": sms_cost,
            "sms_counts": sms_counts,
        }


def requested_and_current_financial_year(request):
    try:
        return (
            int(request.args.get("year", get_current_financial_year())),
            get_current_financial_year(),
        )
    except ValueError:
        abort(404)


def get_tuples_of_financial_years(
    partial_url,
    start=2015,
    end=None,
):
    return (
        (
            "fiscal year",
            year,
            partial_url(year=year),
            "{} to {}".format(year, year + 1),
        )
        for year in reversed(range(start, end + 1))
    )
