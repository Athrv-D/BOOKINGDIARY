import frappe
import json

from frappe.utils import nowdate, add_days
from booking_diary.services.booking_schedule import get_resource_schedule


def get_context(context):

    resources = frappe.get_all(
        "Resource",
        fields=[
            "name",
            "resource_name",
            "resource_type",
            "available",
            "time_zone"
        ],
        order_by="resource_name asc",
    )

    current_user = frappe.session.user
    is_manager = (
        current_user == "Administrator"
        or "Booking Manager" in frappe.get_roles(current_user)
        or "System Manager" in frappe.get_roles(current_user)
    )

    bookings = frappe.get_all(
        "Booking Diary",
        fields=[
            "name",
            "booking_id",
            "resource",
            "booking_date",
            "start_time",
            "end_time",
            "customer",
            "customer_user",
            "status",
            "payment_status",
            "remarks",
        ],
        filters={
            "booking_date": [
                "between",
                [add_days(nowdate(), -90), add_days(nowdate(), 180)],
            ]
        },
        order_by="booking_date asc, start_time asc",
    )

    safe_bookings = []

    for booking in bookings:
        can_see_details = (
            is_manager or booking.get("customer_user") == current_user
        )

        if can_see_details:
            safe_bookings.append(booking)
        else:
            safe_bookings.append({
                "name": None,
                "booking_id": None,
                "resource": booking.resource,
                "booking_date": booking.booking_date,
                "start_time": booking.start_time,
                "end_time": booking.end_time,
                "customer": None,
                "status": None,
                "payment_status": None,
                "remarks": None,
            })

    availability = frappe.get_all(
        "Availability",
        fields=[
            "resource",
            "day_of_week",
            "start_time",
            "end_time",
            "available",
        ],
    )

    context.resources = resources
    context.bookings = safe_bookings
    context.availability = availability

    context.resources_json = json.dumps(
        resources,
        default=str
    )

    context.bookings_json = json.dumps(
        safe_bookings,
        default=str
    )

    context.availability_json = json.dumps(
        availability,
        default=str
    )

    return context


@frappe.whitelist()
def get_schedule(resource, booking_date, slot_duration=30):

    return get_resource_schedule(
        resource=resource,
        booking_date=booking_date,
        slot_duration=int(slot_duration),
    )