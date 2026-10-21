
import frappe
from datetime import timedelta
from frappe.model.document import Document


RESERVING_STATUSES = {"Pending", "Confirmed"}

ALLOWED_STATUS_TRANSITIONS = {
    "Draft": {"Pending"},
    "Pending": {"Confirmed", "Cancelled"},
    "Confirmed": {"Completed", "Cancelled", "No Show"},
    "Completed": set(),
    "Cancelled": set(),
    "No Show": set(),
}


class BookingDiary(Document):
    def set_booking_series_id(self):
        if self.booking_type != "Recurring":
            self.booking_series_id = None
            return

        if not self.booking_series_id:
            self.booking_series_id = frappe.generate_hash(length=12)

    def validate(self):
        self.set_booking_series_id()
        self.set_booking_source()
        self.validate_customer_ownership()
        self.validate_status_transition()
        self.validate_field_protection()
        self.validate_time()


        # Only active bookings need scheduling validations.
        # Completed and cancelled bookings must remain editable.
        if self.status in RESERVING_STATUSES:
            if self.booking_type == "Recurring":
                self.validate_recurring_range()
            else:
                self.validate_future_booking()
                self.validate_blackout()
                self.validate_availability()
                self.validate_conflict()
    
    def validate_customer_ownership(self):
        user = frappe.session.user
        roles = set(frappe.get_roles(user))

        # Managers and System Managers can create bookings
        # on behalf of customers.
        if (
            user == "Administrator"
            or "System Manager" in roles
            or "Booking Manager" in roles
        ):
            return

        # Restrict this ownership rule to Booking Users.
        if "Booking User" not in roles:
            return

        if self.is_new():
            # Customers can create bookings only for themselves.
            if self.customer_user and self.customer_user != user:
                frappe.throw(
                    "You can create bookings only for your own account."
                )

            self.customer_user = user

        elif self.customer_user != user:
            frappe.throw(
                "You cannot change the owner of a booking "
                "or modify another user's booking."
            )


    def validate_status_transition(self):
        user = frappe.session.user
        roles = set(frappe.get_roles(user))

        is_admin = (
            user == "Administrator"
            or "System Manager" in roles
        )
        is_manager = "Booking Manager" in roles

        # New bookings cannot start in a terminal or confirmed state.
        if self.is_new():
            if self.status not in {"Draft", "Pending"}:
                frappe.throw(
                    "A new booking must start as Draft or Pending."
                )
            return

        previous_doc = self.get_doc_before_save()

        if not previous_doc:
            return

        old_status = previous_doc.status
        new_status = self.status

        # Saving other fields without changing the status is allowed
        # subject to the other validation and ownership rules.
        if old_status == new_status:
            return

        allowed_transitions = {
            "Draft": {"Pending"},
            "Pending": {"Confirmed", "Cancelled"},
            "Confirmed": {"Completed", "Cancelled", "No Show"},
            "Completed": set(),
            "Cancelled": set(),
            "No Show": set(),
        }

        if new_status not in allowed_transitions.get(old_status, set()):
            frappe.throw(
                f"Invalid booking status transition: "
                f"{old_status} → {new_status}."
            )

        # Only managers and administrators may confirm, complete,
        # or mark a booking as No Show.
        if new_status in {"Confirmed", "Completed", "No Show"}:
            if not (is_admin or is_manager):
                frappe.throw(
                    "You do not have permission to perform this "
                    "booking status transition."
                )


    def validate_time(self):
        self.start_time = frappe.utils.get_time(self.start_time)
        self.end_time = frappe.utils.get_time(self.end_time)
        if self.start_time >= self.end_time:
            frappe.throw("End Time must be after Start Time.")
    
    def validate_recurring_range(self):
        if self.booking_type != "Recurring":
            return

        if not self.repeat_until:
            frappe.throw("Please select Repeat Until for a recurring booking.")

        first_date = frappe.utils.getdate(self.booking_date)
        last_date = frappe.utils.getdate(self.repeat_until)

        if last_date < first_date:
            frappe.throw("Repeat Until must be on or after Booking Date.")

        # Guard against accidentally creating a very large series.
        if (last_date - first_date).days > 90:
            frappe.throw("A recurring booking cannot exceed 91 dates.")

        original_date = self.booking_date

        try:
            current_date = first_date

            while current_date <= last_date:
                self.booking_date = current_date

                self.validate_future_booking()
                self.validate_blackout()
                self.validate_availability()
                self.validate_conflict()

                current_date += timedelta(days=1)

        finally:
            self.booking_date = original_date

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
                "Cannot book a time that has already passed "
                f"in the resource's time zone ({resource_timezone})."
            )

    def validate_blackout(self):
        blackouts = frappe.get_all(
            "Blackout Date",
            filters={"blackout_date": self.booking_date},
            fields=["resource", "reason", "applies_globally"],
        )

        for blackout in blackouts:
            if (
                blackout.applies_globally
                or blackout.resource == self.resource
            ):
                reason = blackout.reason or "No reason provided"

                frappe.throw(
                    f"Cannot create booking for {self.resource} "
                    f"on {self.booking_date}. Reason: {reason}"
                )

   
    def validate_availability(self):
        day_name = frappe.utils.getdate(
            self.booking_date
        ).strftime("%A")

        # 1. Get availability configured using the old Single Day fields.
        # Blank availability_type is included for legacy records.
        single_day_availability = frappe.db.sql(
            """
            SELECT start_time, end_time
            FROM `tabAvailability`
            WHERE resource = %s
            AND day_of_week = %s
            AND available = 1
            AND (
                availability_type = 'Single Day'
                OR IFNULL(availability_type, '') = ''
            )
            """,
            (self.resource, day_name),
            as_dict=True,
        )

        # 2. Get availability configured through the Multiple Days child table.
        multiple_day_availability = frappe.db.sql(
            """
            SELECT child.start_time, child.end_time
            FROM `tabAvailability Day` child
            INNER JOIN `tabAvailability` parent
                ON child.parent = parent.name
            WHERE parent.resource = %s
            AND parent.availability_type = 'Multiple Days'
            AND child.parenttype = 'Availability'
            AND child.parentfield = 'weekly_schedule'
            AND child.day_of_week = %s
            AND child.available = 1
            """,
            (self.resource, day_name),
            as_dict=True,
        )

        # 3. Combine both availability types.
        availabilities = (
            single_day_availability + multiple_day_availability
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
                f"Booking time is outside in {day_name} available hours "
                f"for {self.resource}."
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
        # Serialize booking checks for the same resource.
        frappe.db.sql(
            """
            SELECT name
            FROM `tabResource`
            WHERE name = %s
            FOR UPDATE
            """,
            (self.resource,),
        )

        # A single booking checks its own date.
        # A recurring request checks every date in its range.
        if self.booking_type == "Recurring":
            if not self.repeat_until:
                frappe.throw("Repeat Until is required for a recurring booking.")

            start_date = frappe.utils.getdate(self.booking_date)
            end_date = frappe.utils.getdate(self.repeat_until)

            if end_date < start_date:
                frappe.throw("Repeat Until cannot be before the booking start date.")

            dates_to_check = []
            current_date = start_date

            while current_date <= end_date:
                dates_to_check.append(current_date)
                current_date = frappe.utils.add_days(current_date, 1)
        else:
            dates_to_check = [frappe.utils.getdate(self.booking_date)]

        # Check each date against existing single bookings and recurring ranges.
        for date_to_check in dates_to_check:
            conflicts = frappe.db.sql(
                """
                SELECT name
                FROM `tabBooking Diary`
                WHERE resource = %s
                AND name != %s
                AND status NOT IN (
                    'Cancelled', 'Draft', 'No Show', 'Completed'
                )
                AND (
                    booking_date = %s
                    OR (
                        booking_type = 'Recurring'
                        AND booking_date <= %s
                        AND repeat_until >= %s
                    )
                )
                AND start_time < %s
                AND end_time > %s
                LIMIT 1
                FOR UPDATE
                """,
                (
                    self.resource,
                    self.name or "",
                    date_to_check,
                    date_to_check,
                    date_to_check,
                    self.end_time,
                    self.start_time,
                ),
                as_dict=True,
            )

            if conflicts:
                frappe.throw(
                    f"This resource is already booked during the selected time "
                    f"on {date_to_check}."
                )
    def validate_field_protection(self):
    # New documents have no previous values to protect.
        if self.is_new():
            return

        previous_doc = self.get_doc_before_save()
        if not previous_doc:
            return

        if self.booking_source != previous_doc.booking_source:
           frappe.throw("Booking Source cannot be changed after creation.")
        # Booking ID must never change after creation.
        if self.booking_id != previous_doc.booking_id:
            frappe.throw("Booking ID cannot be changed after creation.")

        # A booking's customer assignment cannot be changed after creation.
        if self.customer_user != previous_doc.customer_user:
            frappe.throw("The booking owner cannot be changed after creation.")

        user = frappe.session.user
        roles = set(frappe.get_roles(user))

        is_admin = (
        user == "Administrator"
        or "System Manager" in roles
    )

        is_manager = "Booking Manager" in roles

        protected_fields = (
                "resource",
                "customer_user",
                "booking_date",
                "start_time",
                "end_time",
            )
        if is_manager and not is_admin:
            if previous_doc.booking_source != "Staff":
                fields_to_check = {
                    "resource": lambda value: value,
                    "customer_user": lambda value: value,
                    "booking_date": lambda value: (
                        str(value) if value else None
                    ),
                    "start_time": lambda value: (
                        str(frappe.utils.get_time(value)) if value else None
                    ),
                    "end_time": lambda value: (
                        str(frappe.utils.get_time(value)) if value else None
                    ),
                }

                for field, normalize in fields_to_check.items():
                    old_value = normalize(previous_doc.get(field))
                    new_value = normalize(self.get(field))

                    if old_value != new_value:
                        frappe.throw(
                            "You cannot change the details of a "
                            "customer-created booking."
                        )
        is_staff = (
            is_admin
            or is_manager
        )
        def _norm(field, value):
            if not value:
                return None
            if field in ("start_time", "end_time"):
                return str(frappe.utils.get_time(value))
            if field == "booking_date":
                return str(frappe.utils.getdate(value))
            return value
        # Customers cannot modify booking details once the booking
        # has progressed beyond Draft or Pending.
        if not is_staff and "Booking User" in roles:
            if previous_doc.status not in {"Draft", "Pending"}:

                for field in protected_fields:
                    if _norm(field,self.get(field)) != _norm(field,previous_doc.get(field)):
                        frappe.throw(
                            "Booking details cannot be changed "
                            "after the booking is confirmed or closed."
                        )
        
    def set_booking_source(self):
        if not self.is_new():
            return

        user = frappe.session.user
        roles = set(frappe.get_roles(user))

        if (
            user == "Administrator"
            or "System Manager" in roles
            or "Booking Manager" in roles
        ):
            self.booking_source = "Staff"

        elif "Booking User" in roles:
            self.booking_source = "Customer"

        else:
            frappe.throw(
                "You do not have permission to create bookings."
            )


@frappe.whitelist()
def get_booking_source():
    user = frappe.session.user
    roles = set(frappe.get_roles(user))

    if (
        user == "Administrator"
        or "System Manager" in roles
        or "Booking Manager" in roles
    ):
        return "Staff"

    if "Booking User" in roles:
        return "Customer"

    frappe.throw("You do not have permission to create bookings.")


@frappe.whitelist()
def get_my_booking(booking_name):
    if frappe.session.user == "Guest":
        frappe.throw("Please log in.")

    booking = frappe.get_doc("Booking Diary", booking_name)

    if booking.customer_user != frappe.session.user:
        frappe.throw("You do not have permission to access this booking.")

    return {
        "name": booking.name,
        "resource": booking.resource,
        "booking_date": booking.booking_date,
        "start_time": booking.start_time,
        "end_time": booking.end_time,
        "status": booking.status,
        "payment_status": booking.payment_status,
    }


from booking_diary.services.booking_schedule import DEFAULT_SLOT_DURATION
@frappe.whitelist()
def get_multi_day_schedule(
    resource,
    start_date,
    end_date,
    slot_duration=DEFAULT_SLOT_DURATION,
    user_timezone=None,
):
    start_date = frappe.utils.getdate(start_date)
    end_date = frappe.utils.getdate(end_date)

    if end_date < start_date:
        frappe.throw("End date cannot be before start date.")

    if (end_date - start_date).days > 90:
        frappe.throw("The date range cannot exceed 91 days.")

    schedules = []
    current_date = start_date

    while current_date <= end_date:
        daily_schedule = get_resource_schedule(
            resource=resource,
            booking_date=current_date,
            slot_duration=int(slot_duration),
            user_timezone=user_timezone,
        )

        schedules.append({
            "date": str(current_date),
            "schedule": daily_schedule,
        })

        current_date = frappe.utils.add_days(current_date, 1)

    return {
        "resource": resource,
        "start_date": str(start_date),
        "end_date": str(end_date),
        "schedules": schedules,
    }
@frappe.whitelist()
def is_booking_user():
    return "Booking User" in frappe.get_roles(frappe.session.user)
    
