import frappe
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


REMINDER_OFFSETS = ((24 * 60, "24 hours"), (60, "1 hour"))


def complete_elapsed_bookings():
    """Hourly scheduler job to mark ended bookings as Completed."""
    from booking_diary.api import complete_past_bookings

    complete_past_bookings()


def send_booking_reminders():
    """Queue email and in-app reminders for confirmed upcoming bookings.

    The job runs every 15 minutes. Reminder log records make each reminder
    idempotent per booking occurrence and offset.
    """
    bookings = frappe.get_all(
        "Booking Diary",
        filters={"status": "Confirmed"},
        fields=[
            "name", "booking_id", "resource", "booking_date", "start_time",
            "end_time", "customer", "customer_email", "customer_user",
            "booking_type", "repeat_until",
        ],
        limit_page_length=5000,
    )
    now_utc = datetime.now(ZoneInfo("UTC"))

    for booking in bookings:
        resource_timezone = frappe.db.get_value(
            "Resource", booking.resource, "time_zone"
        ) or "UTC"
        try:
            timezone = ZoneInfo(resource_timezone)
        except (ZoneInfoNotFoundError, ValueError):
            timezone = ZoneInfo("UTC")

        now_local = now_utc.astimezone(timezone)
        first_date = frappe.utils.getdate(booking.booking_date)
        is_recurring = (
            booking.booking_type == "Recurring" and booking.repeat_until
        )
        last_date = (
            frappe.utils.getdate(booking.repeat_until)
            if is_recurring else first_date
        )

        occurrence_date = max(first_date, now_local.date())
        while occurrence_date <= last_date:
            booking_start = datetime.combine(
                occurrence_date,
                frappe.utils.get_time(booking.start_time),
            ).replace(tzinfo=timezone)

            if booking_start > now_local:
                break

            if not is_recurring:
                occurrence_date = None
                break

            occurrence_date += timedelta(days=1)

        if occurrence_date is None or occurrence_date > last_date:
            continue

        booking_start = datetime.combine(
            occurrence_date,
            frappe.utils.get_time(booking.start_time),
        ).replace(tzinfo=timezone)
        remaining_seconds = (booking_start - now_local).total_seconds()
        if remaining_seconds <= 0:
            continue

        for offset_minutes, offset_label in REMINDER_OFFSETS:
            # The scheduler runs every 15 minutes. A bounded window prevents
            # both reminders from firing together and avoids repeated sends.
            window_seconds = 15 * 60
            if (offset_minutes - 15) * 60 < remaining_seconds <= offset_minutes * 60:
                _send_one_booking_reminder(
                    booking, occurrence_date, offset_minutes, offset_label,
                    resource_timezone,
                )


def _send_one_booking_reminder(
    booking, occurrence_date, offset_minutes, offset_label, timezone_name
):
    dedupe_key = f"{booking.name}:{occurrence_date}:{offset_minutes}"
    log_name = frappe.db.get_value(
        "Booking Reminder Log", {"dedupe_key": dedupe_key}, "name"
    )
    if log_name:
        reminder_log = frappe.get_doc("Booking Reminder Log", log_name)
    else:
        reminder_log = frappe.get_doc({
            "doctype": "Booking Reminder Log",
            "booking": booking.name,
            "occurrence_date": occurrence_date,
            "reminder_offset": offset_label,
            "dedupe_key": dedupe_key,
            "email_status": "Pending",
            "in_app_sent": 0,
        })
        reminder_log.insert(ignore_permissions=True)

    subject = f"Booking reminder ({offset_label}): {booking.booking_id or booking.name}"
    customer_name = booking.customer or "there"
    resource_name = booking.resource
    date_label = frappe.utils.formatdate(occurrence_date)
    start_label = str(booking.start_time)[:5]
    end_label = str(booking.end_time)[:5]
    details = (
        f"Your booking is coming up in approximately {offset_label}.<br><br>"
        f"<strong>Booking:</strong> {frappe.utils.escape_html(booking.booking_id or booking.name)}<br>"
        f"<strong>Resource:</strong> {frappe.utils.escape_html(resource_name)}<br>"
        f"<strong>Date:</strong> {date_label}<br>"
        f"<strong>Time:</strong> {start_label}–{end_label} ({frappe.utils.escape_html(timezone_name)})"
    )
    message = f"Hello {frappe.utils.escape_html(customer_name)},<br><br>{details}"

    # Email is queued once. A failed queue attempt remains retryable.
    if reminder_log.email_status in ("Pending", "Failed"):
        email_address = booking.customer_email
        if not email_address and booking.customer_user:
            email_address = frappe.db.get_value(
                "User", booking.customer_user, "email"
            )

        if not email_address:
            reminder_log.email_status = "Skipped"
            reminder_log.last_error = "No customer email address is available."
        else:
            try:
                frappe.sendmail(
                    recipients=[email_address],
                    subject=subject,
                    message=message,
                    reference_doctype="Booking Diary",
                    reference_name=booking.name,
                    delayed=True,
                )
                reminder_log.email_status = "Queued"
                reminder_log.email_sent_on = frappe.utils.now_datetime()
                reminder_log.last_error = None
            except Exception:
                reminder_log.email_status = "Failed"
                reminder_log.last_error = frappe.get_traceback()

    # Deliver an in-app Notification Log to the customer and booking managers.
    recipients = set()
    if booking.customer_user and booking.customer_user != "Guest":
        recipients.add(booking.customer_user)
    recipients.add("Administrator")
    manager_users = frappe.get_all(
        "Has Role",
        filters={"role": ["in", ["Booking Manager", "System Manager"]]},
        pluck="parent",
    )
    recipients.update(user for user in manager_users if user and user != "Guest")

    for user in recipients:
        already_notified = frappe.db.exists("Notification Log", {
            "for_user": user,
            "document_type": "Booking Diary",
            "document_name": booking.name,
            "subject": subject,
        })
        if already_notified:
            continue
        frappe.get_doc({
            "doctype": "Notification Log",
            "subject": subject,
            "email_content": message,
            "for_user": user,
            "type": "Alert",
            "document_type": "Booking Diary",
            "document_name": booking.name,
        }).insert(ignore_permissions=True)

    reminder_log.in_app_sent = 1
    reminder_log.save(ignore_permissions=True)
