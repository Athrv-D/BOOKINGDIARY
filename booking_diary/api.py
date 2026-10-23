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
            "payment_status",
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
            "available",
            "time_zone",
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
    remarks="",
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
