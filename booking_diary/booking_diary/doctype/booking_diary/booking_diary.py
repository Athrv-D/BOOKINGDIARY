import frappe
from frappe.model.document import Document


class BookingDiary(Document):

    def validate(self):
        self.validate_time()
        self.validate_future_booking()
        self.validate_blackout()
        self.validate_availability()
        self.validate_conflict()

    def validate_time(self):
        if self.start_time >= self.end_time:
            frappe.throw("End Time must be after Start Time.")

    
     
    def validate_future_booking(self):
        from datetime import datetime
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

        booking_date = frappe.utils.getdate(self.booking_date)

        resource_timezone = frappe.db.get_value(
            "Resource",
            self.resource,
            "time_zone",
        )

        if not resource_timezone:
            frappe.throw(
                f"Please set a Time Zone for resource {self.resource}."
            )

        try:
            timezone = ZoneInfo(resource_timezone)
        except (ZoneInfoNotFoundError, ValueError):
            frappe.throw(
                f"Invalid time zone '{resource_timezone}' "
                f"configured for resource {self.resource}."
            )

        current_datetime = datetime.now(timezone)

        booking_start = datetime.combine(
            booking_date,
            frappe.utils.get_time(self.start_time),
        ).replace(tzinfo=timezone)

        if booking_start <= current_datetime:
            frappe.throw(
                f"Cannot book a time that has already passed "
                f"in the resource's time zone ({resource_timezone})."
            )


    
    def validate_blackout(self):
        blackouts = frappe.get_all(
        "Blackout Date",
        filters={
            "blackout_date": self.booking_date,
        },
        fields=[
            "resource",
            "reason",
            "applies_globally",
        ],
    )

        for blackout in blackouts:
         if (
            blackout.applies_globally
            or blackout.resource == self.resource
        ):
            reason = blackout.reason or "No reason provided"

            frappe.throw(
                f"Cannot create booking for {self.resource} "
                f"on {self.booking_date}. "
                f"Reason: {reason}"
            )


    def validate_availability(self):
        day_name = frappe.utils.getdate(
            self.booking_date
        ).strftime("%A")

        availabilities = frappe.get_all(
            "Availability",
            filters={
                "resource": self.resource,
                "day_of_week": day_name,
                "available": 1,
            },
            fields=["start_time", "end_time"],
            order_by="start_time asc",
        )

        if not availabilities:
            frappe.throw(
                f"{self.resource} is not available on {day_name}."
            )

        def convert_time(value):
            value = str(value)
            hours, minutes, seconds = value.split(":")[:3]

            return (
                int(hours) * 3600
                + int(minutes) * 60
                + int(float(seconds))
            )

        booking_start = convert_time(self.start_time)
        booking_end = convert_time(self.end_time)

        booking_fits = any(
            booking_start >= convert_time(slot.start_time)
            and booking_end <= convert_time(slot.end_time)
            for slot in availabilities
        )

        if not booking_fits:
            frappe.throw(
                f"Booking time is outside the available hours "
                f"for {self.resource}."
            )
    def validate_conflict(self):
        conflicts = frappe.db.sql(
            """
            SELECT name
            FROM `tabBooking Diary`
            WHERE resource = %s
              AND booking_date = %s
              AND name != %s
              AND status NOT IN ('Cancelled', 'Draft', 'No Show', 'Completed')
              AND start_time < %s
              AND end_time > %s
            """,
            (
                self.resource,
                self.booking_date,
                self.name or "",
                self.end_time,
                self.start_time,
            ),
            as_dict=True,
        )

        if conflicts:
            frappe.throw(
                "This resource is already booked during the selected time."
            )