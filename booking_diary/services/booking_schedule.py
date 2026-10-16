import frappe
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


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


def convert_resource_time(
    booking_date,
    booking_time,
    resource_timezone,
    user_timezone,
):
    """Convert a resource-local date/time to the user's timezone."""

    try:
        source_timezone = ZoneInfo(resource_timezone)
        target_timezone = ZoneInfo(user_timezone)
    except (ZoneInfoNotFoundError, ValueError):
        frappe.throw("Invalid resource or user timezone.")

    local_date = frappe.utils.getdate(booking_date)
    local_time = frappe.utils.get_time(booking_time)

    resource_datetime = datetime.combine(
        local_date,
        local_time,
        tzinfo=source_timezone,
    )

    return resource_datetime.astimezone(target_timezone)


def get_resource_dates_for_user_day(
    user_date,
    resource_timezone,
    user_timezone,
):
    """Find resource-local dates that overlap a user's calendar day."""

    try:
        resource_tz = ZoneInfo(resource_timezone)
        user_tz = ZoneInfo(user_timezone)
    except (ZoneInfoNotFoundError, ValueError):
        frappe.throw("Invalid resource or user timezone.")

    user_date = frappe.utils.getdate(user_date)

    user_day_start = datetime.combine(
        user_date,
        datetime.min.time(),
        tzinfo=user_tz,
    )

    user_day_end = datetime.combine(
        user_date + timedelta(days=1),
        datetime.min.time(),
        tzinfo=user_tz,
    )

    resource_start_date = user_day_start.astimezone(
        resource_tz
    ).date()

    resource_end_date = (
        user_day_end - timedelta(microseconds=1)
    ).astimezone(resource_tz).date()

    dates = []
    current_date = resource_start_date

    while current_date <= resource_end_date:
        dates.append(current_date.isoformat())
        current_date += timedelta(days=1)

    return dates


def add_user_display_times(
    items,
    booking_date,
    resource_timezone,
    user_timezone,
):
    """Add user-local datetimes without changing stored booking times."""

    if not user_timezone:
        return

    for item in items:
        start_datetime = convert_resource_time(
            booking_date=booking_date,
            booking_time=item["start_time"],
            resource_timezone=resource_timezone,
            user_timezone=user_timezone,
        )

        end_date = frappe.utils.getdate(booking_date)

        start_minutes = time_to_minutes(item["start_time"])
        end_minutes = time_to_minutes(item["end_time"])

        # Handle a booking or slot that ends after midnight.
        if end_minutes < start_minutes:
            end_date = frappe.utils.add_days(end_date, 1)

        end_datetime = convert_resource_time(
            booking_date=end_date,
            booking_time=item["end_time"],
            resource_timezone=resource_timezone,
            user_timezone=user_timezone,
        )

        item["start_time_user_datetime"] = start_datetime.isoformat()
        item["end_time_user_datetime"] = end_datetime.isoformat()

def get_resource_schedule(resource, booking_date, slot_duration=DEFAULT_SLOT_DURATION, user_timezone=None,):
    """
    Generate the complete schedule for one resource on one date.

    Returns available/booked/unavailable time slots.
    """

    day_name = frappe.utils.getdate(booking_date).strftime("%A")
    blackout_filters = {
        "blackout_date": booking_date,
    }
    resource_timezone = frappe.db.get_value(
    "Resource",
    resource,
    "time_zone",
)

    blackouts = frappe.get_all(
        "Blackout Date",
        filters=blackout_filters,
        fields=[
            "resource",
            "reason",
            "applies_globally",
        ],
    )

    applicable_blackout = next(
        (
            blackout
            for blackout in blackouts
            if blackout.applies_globally
            or blackout.resource == resource
        ),
        None,
    )

    if applicable_blackout:
        return {
            "resource": resource,
            "date": str(booking_date),
            "day": day_name,
            "slots": [],
            "bookings": [],
            "is_blackout": True,
            "blackout_reason": applicable_blackout.reason,
            "time_zone":resource_timezone
        }

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
            "status": ["not in", ["Cancelled", "Draft", "No Show", "Completed",]],
        },
        fields=[
            "name",
            "booking_id",
            "start_time",
            "end_time",
            "customer",
            "customer_user",
            "status",
        ],
        order_by="start_time asc",
    )
    current_user = frappe.session.user
    manager = is_booking_manager(current_user)

    safe_bookings = []

    for booking in bookings:
        can_see_details = (
            manager
            or booking.customer_user == current_user
        )

        if can_see_details:
            safe_bookings.append(booking)
        else:
            safe_bookings.append({
                # Keep only data needed to draw the occupied block.
                "name": None,
                "booking_id": None,
                "start_time": booking.start_time,
                "end_time": booking.end_time,
                "customer": None,
                # "status": booking.status,
            })

    schedule = []

    # No availability configured
    if not availabilities:
        return {
            "resource": resource,
            "date": str(booking_date),
            "day": day_name,
            "slots": [],
            "bookings": safe_bookings,
            "time_zone":resource_timezone,
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
                can_see_details = (
                    manager
                    or booking.customer_user == current_user
                )

                slot_data = {
                    "start_time": slot_start_time,
                    "end_time": slot_end_time,
                    "status": "booked",
                }

                if can_see_details:
                    slot_data.update({
                        "booking_id": booking.booking_id,
                        "booking_name": booking.name,
                        "customer": booking.customer,
                    })

                schedule.append(slot_data)
            else:
                schedule.append({
                    "start_time": slot_start_time,
                    "end_time": slot_end_time,
                    "status": "available",
                })

            current += slot_duration
    add_user_display_times(
    schedule,
    booking_date,
    resource_timezone,
    user_timezone,
)

    add_user_display_times(
        safe_bookings,
        booking_date,
        resource_timezone,
        user_timezone,
    )

    return {
        "resource": resource,
        "date": str(booking_date),
        "day": day_name,
        "slots": schedule,
        "bookings": safe_bookings,
        "is_blackout": False,
        "blackout_reason": None,
        "time_zone":resource_timezone,
    
    }

def is_booking_manager(user=None):
    user = user or frappe.session.user
    roles = frappe.get_roles(user)

    return (
        user == "Administrator"
        or "Booking Manager" in roles
        or "System Manager" in roles
    )

@frappe.whitelist()
def get_schedule(resource, booking_date, slot_duration=30, user_timezone=None,):

    return get_resource_schedule(
        resource=resource,
        booking_date=booking_date,
        slot_duration=int(slot_duration),
        user_timezone=user_timezone,
    )

@frappe.whitelist()
def get_user_day_schedule(
    resource,
    user_date,
    slot_duration=DEFAULT_SLOT_DURATION,
    user_timezone=None,
):
    """Return resource schedules for a complete user-local calendar day."""

    if not user_timezone:
        user_timezone = get_user_timezone()

    resource_timezone = frappe.db.get_value(
        "Resource",
        resource,
        "time_zone",
    )

    if not resource_timezone:
        frappe.throw(
            f"Please set a Time Zone for resource {resource}."
        )

    resource_dates = get_resource_dates_for_user_day(
        user_date=user_date,
        resource_timezone=resource_timezone,
        user_timezone=user_timezone,
    )

    schedules = []

    for resource_date in resource_dates:
        schedule = get_resource_schedule(
            resource=resource,
            booking_date=resource_date,
            slot_duration=int(slot_duration),
            user_timezone=user_timezone,
        )

        schedules.append(schedule)

    return {
        "resource": resource,
        "user_date": str(user_date),
        "resource_timezone": resource_timezone,
        "user_timezone": user_timezone,
        "resource_dates": resource_dates,
        "schedules": schedules,
    }

@frappe.whitelist()
def get_user_timezone():
    """Return the logged-in user's configured timezone."""
    user_timezone = frappe.db.get_value(
        "User",
        frappe.session.user,
        "time_zone",
    )

    return user_timezone or frappe.db.get_single_value(
        "System Settings",
        "time_zone",
    ) or "UTC"
def get_user_datetime_parts(
    booking_date,
    booking_time,
    resource_timezone,
    user_timezone,
):
    """Return the user's local date and time for a resource-local datetime."""

    converted = convert_resource_time(
        booking_date=booking_date,
        booking_time=booking_time,
        resource_timezone=resource_timezone,
        user_timezone=user_timezone,
    )

    return {
        "datetime": converted,
        "date": converted.date().isoformat(),
        "time": converted.strftime("%H:%M:%S"),
        "minutes": converted.hour * 60 + converted.minute,
    }