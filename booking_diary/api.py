import frappe


@frappe.whitelist()
def get_my_bookings():
    """Return bookings owned by the logged-in Booking User."""

    if frappe.session.user == "Guest":
        frappe.throw("Please log in to view your bookings.")

    if "Booking User" not in frappe.get_roles(frappe.session.user):
        frappe.throw("You do not have permission to view customer bookings.")

    bookings = frappe.get_list(
        "Booking Diary",
        filters={
            "customer_user": frappe.session.user,
        },
        fields=[
            "name",
            "resource",
            "booking_date",
            "start_time",
            "end_time",
            "status",
        ],
        order_by="booking_date desc, start_time desc",
    )

    return bookings

@frappe.whitelist()
def get_resources():
    if frappe.session.user == "Guest":
        frappe.throw("Please log in to view resources.")

    return frappe.get_list(
        "Resource",
        fields=[
            "name",
            "resource_name",
            "resource_type",
            "resource_category",
            "available",
            "time_zone",
            "capacity_mode",
            "capacity",
        ],
        order_by="resource_name asc",
        page_length=500,
    )

@frappe.whitelist()
def get_csrf_token():
    if frappe.session.user == "Guest":
        frappe.throw("Please log in.")

    return frappe.session.data.csrf_token

@frappe.whitelist()
def get_current_user_roles():
    """Return roles for the currently authenticated user."""
    if frappe.session.user == "Guest":
        frappe.throw("Please log in.")
    return frappe.get_roles(frappe.session.user)



@frappe.whitelist()
def create_group_booking(
    resources,
    booking_date,
    start_time,
    end_time,
    booking_type="Single Slot",
    repeat_until=None,
    customer="",
    customer_record=None,
    contact=None,
    customer_phone="",
    customer_email="",
    remarks="",
    attendee_count=1,
    booking_quantity=1,
):
    """Create one atomic booking group across multiple resources."""
    import json
    from frappe.utils import get_time, getdate

    if frappe.session.user == "Guest":
        frappe.throw("Please log in to create a booking.")

    roles = set(frappe.get_roles(frappe.session.user))
    if not (
        frappe.session.user == "Administrator"
        or "System Manager" in roles
        or "Booking Manager" in roles
        or "Booking User" in roles
    ):
        frappe.throw("You do not have permission to create bookings.")

    if isinstance(resources, str):
        try:
            resources = json.loads(resources)
        except (TypeError, ValueError):
            frappe.throw("Select one or more valid resources.")

    if not isinstance(resources, list):
        frappe.throw("Select one or more resources.")

    resources = sorted(set(
        str(resource).strip() for resource in resources if str(resource).strip()
    ))
    if not resources:
        frappe.throw("Select at least one resource.")

    if len(resources) > 20:
        frappe.throw("A group booking can include at most 20 resources.")

    if get_time(start_time) >= get_time(end_time):
        frappe.throw("End time must be after start time.")

    if booking_type not in ("Single Slot", "Recurring"):
        frappe.throw("Invalid booking type.")

    if booking_type == "Recurring":
        if not repeat_until or getdate(repeat_until) < getdate(booking_date):
            frappe.throw("Please select a valid repeat-until date.")

    # Validate every resource before inserting anything. DocType validation
    # checks time zone, blackout dates, configured availability, and conflicts.
    for resource in resources:
        if not frappe.db.exists("Resource", resource):
            frappe.throw(f"Resource not found: {resource}")
        if not frappe.db.get_value("Resource", resource, "available"):
            frappe.throw(f"Resource is unavailable: {resource}")

    group_id = "GB-" + frappe.generate_hash(length=10).upper()
    created = []

    try:
        for resource in resources:
            booking = frappe.get_doc({
                "doctype": "Booking Diary",
                "booking_id": "BK-" + frappe.generate_hash(length=8).upper(),
                "group_booking_id": group_id,
                "resource": resource,
                "booking_date": booking_date,
                "start_time": start_time,
                "end_time": end_time,
                "status": "Pending",
                "booking_type": booking_type,
                "repeat_until": repeat_until if booking_type == "Recurring" else None,
                "customer": (customer or "").strip(),
                "customer_record": customer_record or None,
                "contact": contact or None,
                "customer_phone": (customer_phone or "").strip(),
                "customer_email": (customer_email or "").strip(),
                "attendee_count": int(attendee_count or 1),
                "booking_quantity": int(booking_quantity or 1),
                "remarks": (remarks or "").strip(),
            })
            booking.insert()
            created.append({
                "name": booking.name,
                "booking_id": booking.booking_id,
                "resource": booking.resource,
                "group_booking_id": group_id,
            })
        frappe.db.commit()
    except Exception:
        frappe.db.rollback()
        raise

    return {
        "group_booking_id": group_id,
        "bookings": created,
        "count": len(created),
    }



@frappe.whitelist()
def validate_group_booking(
    resources,
    booking_date,
    start_time,
    end_time,
    booking_type="Single Slot",
    repeat_until=None,
    attendee_count=1,
    booking_quantity=1,
):
    """Validate a proposed group booking without inserting any booking rows."""
    import json

    if frappe.session.user == "Guest":
        frappe.throw("Please log in to validate a booking.")

    roles = set(frappe.get_roles(frappe.session.user))
    if not (
        frappe.session.user == "Administrator"
        or "System Manager" in roles
        or "Booking Manager" in roles
        or "Booking User" in roles
    ):
        frappe.throw("You do not have permission to create bookings.")

    if isinstance(resources, str):
        try:
            resources = json.loads(resources)
        except (TypeError, ValueError):
            frappe.throw("Select one or more valid resources.")

    if not isinstance(resources, list):
        frappe.throw("Select one or more resources.")

    resources = sorted(set(
        str(resource).strip() for resource in resources if str(resource).strip()
    ))
    if not resources:
        return {"valid": False, "errors": ["Select at least one resource."]}

    if len(resources) > 20:
        return {"valid": False, "errors": ["A group booking can include at most 20 resources."]}

    results = []
    for resource in resources:
        try:
            if not frappe.db.exists("Resource", resource):
                frappe.throw(f"Resource not found: {resource}")

            if not frappe.db.get_value("Resource", resource, "available"):
                frappe.throw(f"{resource} is marked unavailable.")

            candidate = frappe.get_doc({
                "doctype": "Booking Diary",
                "booking_id": "VALIDATE-" + frappe.generate_hash(length=8).upper(),
                "group_booking_id": "VALIDATION-ONLY",
                "resource": resource,
                "booking_date": booking_date,
                "start_time": start_time,
                "end_time": end_time,
                "status": "Pending",
                "booking_type": booking_type,
                "repeat_until": repeat_until if booking_type == "Recurring" else None,
                "customer": "",
                "attendee_count": int(attendee_count or 1),
                "booking_quantity": int(booking_quantity or 1),
                "customer_user": (
                    frappe.session.user
                    if "Booking User" in roles
                    and "Booking Manager" not in roles
                    and "System Manager" not in roles
                    and frappe.session.user != "Administrator"
                    else None
                ),
                "remarks": "",
            })
            candidate.validate()
            results.append({"resource": resource, "valid": True, "error": ""})
        except Exception as exc:
            message = str(exc).strip() or f"{resource} failed validation."
            # Remove HTML wrappers commonly added by Frappe exceptions.
            import re
            message = re.sub(r"<[^>]+>", " ", message)
            message = re.sub(r"\s+", " ", message).strip()
            results.append({"resource": resource, "valid": False, "error": message})

    errors = [item["error"] for item in results if not item["valid"]]
    return {"valid": not errors, "errors": errors, "resources": results}



@frappe.whitelist()
def cancel_booking(booking_name):
    """Cancel a booking only for its owner or an authorized manager."""
    if frappe.session.user == "Guest":
        frappe.throw("Please log in to cancel a booking.")

    roles = set(frappe.get_roles(frappe.session.user))
    is_admin = (
        frappe.session.user == "Administrator"
        or "System Manager" in roles
    )
    is_manager = "Booking Manager" in roles

    booking = frappe.get_doc("Booking Diary", booking_name)

    if not (is_admin or is_manager):
        if "Booking User" not in roles:
            frappe.throw("You do not have permission to cancel bookings.")
        if booking.customer_user != frappe.session.user:
            frappe.throw("You can cancel only your own bookings.")

    if booking.status not in ("Pending", "Confirmed"):
        frappe.throw("Only pending or confirmed bookings can be cancelled.")

    from datetime import datetime
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
    rules = frappe.db.get_value(
        "Resource", booking.resource,
        ["time_zone", "cancellation_cutoff_hours"], as_dict=True,
    ) or {}
    timezone_name = rules.get("time_zone") or "UTC"
    try:
        timezone = ZoneInfo(timezone_name)
    except (ZoneInfoNotFoundError, ValueError):
        timezone = ZoneInfo("UTC")
    booking_start = datetime.combine(
        frappe.utils.getdate(booking.booking_date),
        frappe.utils.get_time(booking.start_time),
    ).replace(tzinfo=timezone)
    cutoff_hours = int(rules.get("cancellation_cutoff_hours") or 0)
    now_local = datetime.now(timezone)
    if booking_start > now_local and (
        booking_start - now_local
    ).total_seconds() < cutoff_hours * 3600:
        frappe.throw(
            f"This booking must be cancelled at least {cutoff_hours} hours in advance."
        )

    # If the requested booking has already ended in the resource's timezone,
    # complete it rather than allowing a cancellation of past time.
    from datetime import datetime
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
    resource_timezone = frappe.db.get_value("Resource", booking.resource, "time_zone") or "UTC"
    try:
        timezone = ZoneInfo(resource_timezone)
    except (ZoneInfoNotFoundError, ValueError):
        timezone = ZoneInfo("UTC")
    end_date = booking.repeat_until if booking.booking_type == "Recurring" and booking.repeat_until else booking.booking_date
    booking_end = datetime.combine(
        frappe.utils.getdate(end_date),
        frappe.utils.get_time(booking.end_time),
    ).replace(tzinfo=timezone)
    if booking_end <= datetime.now(ZoneInfo("UTC")).astimezone(timezone):
        frappe.db.set_value("Booking Diary", booking.name, "status", "Completed", update_modified=True)
        return {
            "name": booking.name,
            "booking_id": booking.booking_id,
            "status": "Completed",
            "message": "This booking has already ended and was marked Completed instead of cancelled.",
        }

    # Update the status directly so legacy records missing newer mandatory
    # fields (such as booking_type) can still be cancelled safely. Ownership
    # and role authorization have already been checked above.
    frappe.db.set_value(
        "Booking Diary",
        booking.name,
        "status",
        "Cancelled",
        update_modified=True,
    )
    return {
        "name": booking.name,
        "booking_id": booking.booking_id,
        "status": "Cancelled",
    }


@frappe.whitelist()
def reschedule_customer_booking(booking_name, resource, booking_date, start_time, end_time):
    """Reschedule an active booking owned by the current customer."""
    from datetime import datetime
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

    if frappe.session.user == "Guest":
        frappe.throw("Please log in to reschedule a booking.")

    roles = set(frappe.get_roles(frappe.session.user))
    is_manager = (
        frappe.session.user == "Administrator"
        or "System Manager" in roles
        or "Booking Manager" in roles
    )
    if not is_manager and "Booking User" not in roles:
        frappe.throw("You do not have permission to reschedule bookings.")

    booking = frappe.get_doc("Booking Diary", booking_name)
    if not is_manager and booking.customer_user != frappe.session.user:
        frappe.throw("You can reschedule only your own bookings.")
    if booking.status not in ("Pending", "Confirmed"):
        frappe.throw("Only pending or confirmed bookings can be rescheduled.")

    rules = frappe.db.get_value(
        "Resource", booking.resource,
        ["time_zone", "cancellation_cutoff_hours"], as_dict=True,
    ) or {}
    timezone_name = rules.get("time_zone") or "UTC"
    try:
        timezone = ZoneInfo(timezone_name)
    except (ZoneInfoNotFoundError, ValueError):
        timezone = ZoneInfo("UTC")
    cutoff_hours = int(rules.get("cancellation_cutoff_hours") or 0)
    original_start = datetime.combine(
        frappe.utils.getdate(booking.booking_date),
        frappe.utils.get_time(booking.start_time),
    ).replace(tzinfo=timezone)
    if not is_manager and (
        original_start - datetime.now(timezone)
    ).total_seconds() < cutoff_hours * 3600:
        frappe.throw(
            f"This booking can only be rescheduled at least {cutoff_hours} hours in advance."
        )

    if not frappe.db.exists("Resource", resource):
        frappe.throw("Selected resource does not exist.")
    if not frappe.db.get_value("Resource", resource, "available"):
        frappe.throw("Selected resource is not available.")

    booking.resource = resource
    booking.booking_date = frappe.utils.getdate(booking_date)
    booking.start_time = frappe.utils.get_time(start_time)
    booking.end_time = frappe.utils.get_time(end_time)
    booking.flags.allow_customer_reschedule = True
    booking.save()
    frappe.db.commit()
    return {
        "name": booking.name,
        "booking_id": booking.booking_id,
        "resource": booking.resource,
        "booking_date": str(booking.booking_date),
        "start_time": str(booking.start_time),
        "end_time": str(booking.end_time),
        "status": booking.status,
    }


@frappe.whitelist()
def get_current_user():
    if frappe.session.user == "Guest":
        frappe.throw("Please log in.")
    return frappe.session.user



@frappe.whitelist()
def complete_past_bookings():
    """Mark only elapsed Confirmed bookings Completed; Pending bookings stay Pending."""
    from datetime import datetime
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

    if frappe.session.user == "Guest":
        frappe.throw("Please log in.")

    rows = frappe.db.sql(
        """
        SELECT
            booking.name,
            booking.booking_type,
            booking.booking_date,
            booking.end_time,
            booking.repeat_until,
            resource.time_zone
        FROM `tabBooking Diary` booking
        INNER JOIN `tabResource` resource ON resource.name = booking.resource
        WHERE booking.status = 'Confirmed'
        """,
        as_dict=True,
    )

    completed = []
    now_utc = datetime.now(ZoneInfo("UTC"))
    for row in rows:
        timezone_name = row.time_zone or frappe.db.get_single_value(
            "System Settings", "time_zone"
        ) or "UTC"
        try:
            timezone = ZoneInfo(timezone_name)
        except (ZoneInfoNotFoundError, ValueError):
            continue

        if row.booking_type == "Recurring":
            if not row.repeat_until:
                continue
            final_date = frappe.utils.getdate(row.repeat_until)
        else:
            final_date = frappe.utils.getdate(row.booking_date)

        end_time = frappe.utils.get_time(row.end_time)
        end_datetime = datetime.combine(final_date, end_time).replace(tzinfo=timezone)
        now_local = now_utc.astimezone(timezone)

        if end_datetime <= now_local:
            frappe.db.set_value(
                "Booking Diary",
                row.name,
                "status",
                "Completed",
                update_modified=True,
            )
            completed.append(row.name)

    return {"completed_count": len(completed)}


@frappe.whitelist()
def get_overview_bookings():
    """Return only the current user's bookings, or all bookings to managers."""
    if frappe.session.user == "Guest":
        frappe.throw("Please log in to view bookings.")

    roles = set(frappe.get_roles(frappe.session.user))
    is_manager = (
        frappe.session.user == "Administrator"
        or "System Manager" in roles
        or "Booking Manager" in roles
    )
    filters = {} if is_manager else {"customer_user": frappe.session.user}
    return frappe.get_list(
        "Booking Diary",
        filters=filters,
        fields=[
            "name", "booking_id", "resource", "booking_date",
            "start_time", "end_time", "customer", "customer_user",
            "status", "booking_type", "remarks", "repeat_until",
        ],
        order_by="booking_date asc, start_time asc",
        page_length=500,
    )


@frappe.whitelist()
def update_managed_booking(
    booking_name,
    resource=None,
    booking_date=None,
    start_time=None,
    end_time=None,
    remarks=None,
    status=None,
):
    """Manager-only booking edits and confirmation decisions, fully validated."""
    from frappe.utils import getdate, get_time

    if frappe.session.user == "Guest":
        frappe.throw("Please log in.")
    roles = set(frappe.get_roles(frappe.session.user))
    if not (
        frappe.session.user == "Administrator"
        or "System Manager" in roles
        or "Booking Manager" in roles
    ):
        frappe.throw("Only Booking Managers and administrators can edit or decide bookings.")

    booking = frappe.get_doc("Booking Diary", booking_name)
    if status is not None and status not in ("Pending", "Confirmed", "Cancelled"):
        frappe.throw("Invalid booking status.")
    if status == "Confirmed" and booking.status not in ("Pending", "Confirmed"):
        frappe.throw("Only pending bookings can be confirmed.")
    if status == "Cancelled" and booking.status != "Pending":
        frappe.throw("Only pending bookings can be rejected.")

    if resource is not None and resource != booking.resource:
        if not frappe.db.exists("Resource", resource):
            frappe.throw("Selected resource does not exist.")
        if not frappe.db.get_value("Resource", resource, "available"):
            frappe.throw("Selected resource is not available.")
        booking.resource = resource
    if booking_date:
        booking.booking_date = getdate(booking_date)
    if start_time:
        booking.start_time = get_time(start_time)
    if end_time:
        booking.end_time = get_time(end_time)
    if "remarks" in frappe.form_dict:
        booking.remarks = remarks or ""
    if status is not None:
        booking.status = status

    if get_time(booking.start_time) >= get_time(booking.end_time):
        frappe.throw("End time must be after start time.")

    # Manager actions still run through DocType validation so duration,
    # availability, blackouts, buffers and capacity rules cannot be bypassed.
    booking.flags.allow_customer_reschedule = True
    booking.save()
    frappe.db.commit()
    return frappe.get_doc("Booking Diary", booking.name).as_dict()




@frappe.whitelist()
def get_booking_report(start_date, end_date):
    """Return manager-only booking report rows for a validated date range."""
    from frappe.utils import getdate

    if frappe.session.user == "Guest":
        frappe.throw("Please log in to view booking reports.")

    roles = set(frappe.get_roles(frappe.session.user))
    if not (
        frappe.session.user == "Administrator"
        or "System Manager" in roles
        or "Booking Manager" in roles
    ):
        frappe.throw("Only Booking Managers and administrators can access reports.")

    start = getdate(start_date)
    end = getdate(end_date)
    if end < start:
        frappe.throw("End date must be on or after the start date.")
    if (end - start).days > 366:
        frappe.throw("Reports can cover at most 367 calendar days at a time.")

    return frappe.db.sql(
        """
        SELECT
            booking.name,
            booking.booking_id,
            booking.customer,
            booking.resource,
            resource.resource_name,
            resource.resource_category,
            booking.booking_date,
            booking.start_time,
            booking.end_time,
            booking.status,
            booking.booking_type,
            booking.repeat_until
        FROM `tabBooking Diary` booking
        INNER JOIN `tabResource` resource ON resource.name = booking.resource
        WHERE booking.booking_date BETWEEN %s AND %s
        ORDER BY booking.booking_date DESC, booking.start_time DESC
        LIMIT 5000
        """,
        (start, end),
        as_dict=True,
    )


@frappe.whitelist()
def get_booking_audit_trail(booking_name):
    """Return a permission-checked history of changes to a booking."""
    import json

    if frappe.session.user == "Guest":
        frappe.throw("Please log in to view booking history.")
    booking = frappe.get_doc("Booking Diary", booking_name)
    roles = set(frappe.get_roles(frappe.session.user))
    is_manager = (
        frappe.session.user == "Administrator"
        or "System Manager" in roles
        or "Booking Manager" in roles
    )
    if not is_manager and (
        "Booking User" not in roles or booking.customer_user != frappe.session.user
    ):
        frappe.throw("You do not have permission to view this booking history.")

    versions = frappe.get_all(
        "Version",
        filters={"ref_doctype": "Booking Diary", "docname": booking_name},
        fields=["name", "owner", "creation", "data"],
        order_by="creation desc",
        limit_page_length=100,
    )
    history = []
    for version in versions:
        try:
            data = json.loads(version.data or "{}")
        except (TypeError, ValueError):
            data = {}
        changes = []
        for item in data.get("changed", []):
            if len(item) >= 3:
                changes.append({
                    "field": str(item[0]).replace("_", " ").title(),
                    "old_value": str(item[1] if item[1] is not None else ""),
                    "new_value": str(item[2] if item[2] is not None else ""),
                })
        history.append({
            "name": version.name,
            "user": version.owner,
            "timestamp": str(version.creation),
            "action": "Booking updated" if changes else "Booking activity",
            "changes": changes,
        })
    return history


@frappe.whitelist()
def get_customer_options():
    """Return a bounded list of ERPNext customers and contacts for booking forms."""
    if frappe.session.user == "Guest":
        frappe.throw("Please log in to view customer records.")

    customers = []
    contacts = []
    if frappe.db.exists("DocType", "Customer"):
        customers = frappe.get_list(
            "Customer", fields=["name", "customer_name"],
            order_by="customer_name asc", page_length=500,
        )
    if frappe.db.exists("DocType", "Contact"):
        contacts = frappe.get_list(
            "Contact", fields=["name", "first_name", "last_name", "email_id", "phone"],
            order_by="first_name asc", page_length=500,
        )
    return {"customers": customers, "contacts": contacts}



@frappe.whitelist()
def get_my_reminders():
    """Return recent in-app booking reminders for the logged-in user."""
    if frappe.session.user == "Guest":
        frappe.throw("Please log in to view reminders.")

    return frappe.get_all(
        "Notification Log",
        filters={
            "for_user": frappe.session.user,
            "document_type": "Booking Diary",
        },
        fields=[
            "name", "subject", "email_content", "document_name",
            "read", "creation",
        ],
        order_by="creation desc",
        limit_page_length=50,
    )


@frappe.whitelist()
def mark_reminder_read(notification_name):
    """Mark a notification as read only for its intended recipient."""
    if frappe.session.user == "Guest":
        frappe.throw("Please log in to update reminders.")

    owner = frappe.db.get_value(
        "Notification Log", notification_name, "for_user"
    )
    if owner != frappe.session.user:
        frappe.throw("You cannot update another user's notification.")

    frappe.db.set_value(
        "Notification Log", notification_name, "read", 1,
        update_modified=False,
    )
    return {"name": notification_name, "read": 1}
