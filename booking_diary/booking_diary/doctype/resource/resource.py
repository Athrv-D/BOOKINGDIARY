# Copyright (c) 2026, Katalystic Consulting Services and contributors
# For license information, please see license.txt


import frappe
from frappe.model.document import Document
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

class Resource(Document):
    def validate(self):
        self.validate_time_zone()
        self.validate_booking_rules()

    def validate_booking_rules(self):
        if self.capacity_mode not in ("Exclusive", "Per Booking", "Shared Pool"):
            frappe.throw("Capacity Mode must be Exclusive, Per Booking, or Shared Pool.")

        if (self.capacity or 0) < 1:
            frappe.throw("Capacity must be at least 1.")

        if (self.default_booking_duration or 0) < 1:
            frappe.throw("Default Booking Duration must be at least 1 minute.")

        for field, label in (
            ("buffer_before_minutes", "Buffer Before"),
            ("buffer_after_minutes", "Buffer After"),
            ("minimum_advance_hours", "Minimum Advance Booking"),
            ("maximum_advance_days", "Maximum Advance Booking"),
            ("cancellation_cutoff_hours", "Cancellation Cutoff"),
        ):
            if (self.get(field) or 0) < 0:
                frappe.throw(f"{label} cannot be negative.")

        if self.capacity_mode == "Exclusive" and (self.capacity or 1) != 1:
            frappe.throw("Exclusive resources must have capacity 1.")

    def validate_time_zone(self):
        if not self.time_zone:
            frappe.throw("Time Zone is required for this resource.")

        try:
            ZoneInfo(self.time_zone)
        except (ZoneInfoNotFoundError, ValueError):
            frappe.throw(
                f"Invalid time zone: {self.time_zone}. "
                "Use an IANA timezone such as Asia/Kolkata "
                "or America/New_York."
            )
