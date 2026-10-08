import frappe
from frappe.model.document import Document


class BookingDiary(Document):

    def validate(self):
        self.validate_time()
        self.validate_availability()
        self.validate_conflict()

    def validate_time(self):
        if self.start_time >= self.end_time:
            frappe.throw("End Time must be after Start Time.")

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
              AND status NOT IN ('Cancelled')
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