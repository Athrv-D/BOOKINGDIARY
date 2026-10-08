import frappe
from datetime import datetime, timedelta


DEFAULT_SLOT_DURATION = 30


def time_to_minutes(value):
    value = str(value)
    parts = value.split(":")

    return (
        int(parts[0]) * 60
        + int(parts[1] or 0)
    )


def minutes_to_time(minutes):
    hours = minutes // 60
    mins = minutes % 60

    return f"{hours:02d}:{mins:02d}:00"


def get_resource_schedule(resource, booking_date, slot_duration=DEFAULT_SLOT_DURATION):
    """
    Generate the complete schedule for one resource on one date.

    Returns available/booked/unavailable time slots.
    """

    day_name = frappe.utils.getdate(booking_date).strftime("%A")

    # Get all availability periods for this resource/day
    availabilities = frappe.get_all(
        "Availability",
        filters={
            "resource": resource,
            "day_of_week": day_name,
            "available": 1,
        },
        fields=["start_time", "end_time"],
        order_by="start_time asc",
    )

    # Get existing bookings for this resource/date
    bookings = frappe.get_all(
        "Booking Diary",
        filters={
            "resource": resource,
            "booking_date": booking_date,
            "status": ["not in", ["Cancelled"]],
        },
        fields=[
            "name",
            "booking_id",
            "start_time",
            "end_time",
            "customer",
            "status",
        ],
        order_by="start_time asc",
    )

    schedule = []

    # No availability configured
    if not availabilities:
        return {
            "resource": resource,
            "date": str(booking_date),
            "day": day_name,
            "slots": [],
            "bookings": bookings,
        }

    for availability in availabilities:

        availability_start = time_to_minutes(
            availability.start_time
        )

        availability_end = time_to_minutes(
            availability.end_time
        )

        current = availability_start

        while current + slot_duration <= availability_end:

            slot_start = current
            slot_end = current + slot_duration

            slot_start_time = minutes_to_time(slot_start)
            slot_end_time = minutes_to_time(slot_end)

            # Check whether an existing booking overlaps this slot
            booking = None

            for existing_booking in bookings:

                booking_start = time_to_minutes(
                    existing_booking.start_time
                )

                booking_end = time_to_minutes(
                    existing_booking.end_time
                )

                if (
                    booking_start < slot_end
                    and booking_end > slot_start
                ):
                    booking = existing_booking
                    break

            if booking:
                schedule.append({
                    "start_time": slot_start_time,
                    "end_time": slot_end_time,
                    "status": "booked",
                    "booking_id": booking.booking_id,
                    "booking_name": booking.name,
                    "customer": booking.customer,
                })
            else:
                schedule.append({
                    "start_time": slot_start_time,
                    "end_time": slot_end_time,
                    "status": "available",
                })

            current += slot_duration

    return {
        "resource": resource,
        "date": str(booking_date),
        "day": day_name,
        "slots": schedule,
        "bookings": bookings,
    }


@frappe.whitelist()
def get_schedule(resource, booking_date, slot_duration=30):

    return get_resource_schedule(
        resource=resource,
        booking_date=booking_date,
        slot_duration=int(slot_duration),
    )