# import frappe
# from frappe.model.document import Document


# class BookingDiary(Document):

#     def validate(self):
#         self.validate_time()
#         self.validate_future_booking()
#         self.validate_blackout()
#         self.validate_availability()
#         self.validate_conflict()

#     def validate_time(self):
#         if self.start_time >= self.end_time:
#             frappe.throw("End Time must be after Start Time.")

    
     
#     def validate_future_booking(self):
#         from datetime import datetime
#         from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

#         booking_date = frappe.utils.getdate(self.booking_date)

#         resource_timezone = frappe.db.get_value(
#             "Resource",
#             self.resource,
#             "time_zone",
#         )

#         if not resource_timezone:
#             frappe.throw(
#                 f"Please set a Time Zone for resource {self.resource}."
#             )

#         try:
#             timezone = ZoneInfo(resource_timezone)
#         except (ZoneInfoNotFoundError, ValueError):
#             frappe.throw(
#                 f"Invalid time zone '{resource_timezone}' "
#                 f"configured for resource {self.resource}."
#             )

#         current_datetime = datetime.now(timezone)

#         booking_start = datetime.combine(
#             booking_date,
#             frappe.utils.get_time(self.start_time),
#         ).replace(tzinfo=timezone)

#         if booking_start <= current_datetime:
#             frappe.throw(
#                 f"Cannot book a time that has already passed "
#                 f"in the resource's time zone ({resource_timezone})."
#             )


    
#     def validate_blackout(self):
#         blackouts = frappe.get_all(
#         "Blackout Date",
#         filters={
#             "blackout_date": self.booking_date,
#         },
#         fields=[
#             "resource",
#             "reason",
#             "applies_globally",
#         ],
#     )

#         for blackout in blackouts:
#          if (
#             blackout.applies_globally
#             or blackout.resource == self.resource
#         ):
#             reason = blackout.reason or "No reason provided"

#             frappe.throw(
#                 f"Cannot create booking for {self.resource} "
#                 f"on {self.booking_date}. "
#                 f"Reason: {reason}"
#             )


#     def validate_availability(self):
#         day_name = frappe.utils.getdate(
#             self.booking_date
#         ).strftime("%A")

#         availabilities = frappe.get_all(
#             "Availability",
#             filters={
#                 "resource": self.resource,
#                 "day_of_week": day_name,
#                 "available": 1,
#             },
#             fields=["start_time", "end_time"],
#             order_by="start_time asc",
#         )

#         if not availabilities:
#             frappe.throw(
#                 f"{self.resource} is not available on {day_name}."
#             )

#         def convert_time(value):
#             value = str(value)
#             hours, minutes, seconds = value.split(":")[:3]

#             return (
#                 int(hours) * 3600
#                 + int(minutes) * 60
#                 + int(float(seconds))
#             )

#         booking_start = convert_time(self.start_time)
#         booking_end = convert_time(self.end_time)

#         booking_fits = any(
#             booking_start >= convert_time(slot.start_time)
#             and booking_end <= convert_time(slot.end_time)
#             for slot in availabilities
#         )

#         if not booking_fits:
#             frappe.throw(
#                 f"Booking time is outside the available hours "
#                 f"for {self.resource}."
#             )
#     def validate_conflict(self):
#         conflicts = frappe.db.sql(
#             """
#             SELECT name
#             FROM `tabBooking Diary`
#             WHERE resource = %s
#               AND booking_date = %s
#               AND name != %s
#               AND status NOT IN ('Cancelled', 'Draft', 'No Show', 'Completed')
#               AND start_time < %s
#               AND end_time > %s
#             """,
#             (
#                 self.resource,
#                 self.booking_date,
#                 self.name or "",
#                 self.end_time,
#                 self.start_time,
#             ),
#             as_dict=True,
#         )

#         if conflicts:
#             frappe.throw(
#                 "This resource is already booked during the selected time."
#             )



import frappe
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

    def validate(self):
        self.validate_customer_ownership()
        self.validate_status_transition()
        self.validate_time()

        # Only active bookings need scheduling validations.
        # Completed and cancelled bookings must remain editable.
        if self.status in RESERVING_STATUSES:
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
        # Lock this resource row so concurrent booking requests
        # for the same resource are serialized until transaction end.
        frappe.db.sql(
            """
            SELECT name
            FROM `tabResource`
            WHERE name = %s
            FOR UPDATE
            """,
            (self.resource,),
        )

        # Use a locking read to check the latest committed bookings.
        conflicts = frappe.db.sql(
            """
            SELECT name
            FROM `tabBooking Diary`
            WHERE resource = %s
            AND booking_date = %s
            AND name != %s
            AND status NOT IN (
                'Cancelled', 'Draft', 'No Show', 'Completed'
            )
            AND start_time < %s
            AND end_time > %s
            LIMIT 1
            FOR UPDATE
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
