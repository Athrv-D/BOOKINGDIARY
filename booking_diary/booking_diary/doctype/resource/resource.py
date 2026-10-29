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
        # Backfill safe defaults when validating resources created before these
        # booking-rule fields were introduced.
        self.capacity_mode = self.capacity_mode or "Exclusive"
        self.capacity = self.capacity or 1
        self.resource_category = self.resource_category or "Other"
        self.pricing_model = self.pricing_model or "Fixed"
        self.fixed_price = self.fixed_price or 0
        self.hourly_rate = self.hourly_rate or 0
        self.default_booking_duration = self.default_booking_duration or 30
        if self.maximum_advance_days is None:
            self.maximum_advance_days = 365
        self.buffer_before_minutes = self.buffer_before_minutes or 0
        self.buffer_after_minutes = self.buffer_after_minutes or 0
        self.minimum_advance_hours = self.minimum_advance_hours or 0
        self.cancellation_cutoff_hours = self.cancellation_cutoff_hours or 0

        if self.capacity_mode not in ("Exclusive", "Per Booking", "Shared Pool"):
            frappe.throw("Capacity Mode must be Exclusive, Per Booking, or Shared Pool.")

        if self.resource_category not in ("Venue", "Staff", "Equipment", "Facility", "Other"):
            frappe.throw("Resource Category must be Venue, Staff, Equipment, Facility, or Other.")

        if self.pricing_model not in ("Fixed", "Hourly"):
            frappe.throw("Pricing Model must be Fixed or Hourly.")

        if (self.fixed_price or 0) < 0 or (self.hourly_rate or 0) < 0:
            frappe.throw("Resource prices cannot be negative.")

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
