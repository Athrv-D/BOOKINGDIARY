# Copyright (c) 2026, Katalystic Consulting Services and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class BlackoutDate(Document):
    def validate(self):
        if self.applies_globally:
            self.resource = None
        elif not self.resource:
            frappe.throw("Select a Resource or enable Applies Globally.")
        if not self.blackout_date:
            frappe.throw("Start date is required.")

        start_date = frappe.utils.getdate(self.blackout_date)
        end_date = frappe.utils.getdate(self.blackout_end_date or self.blackout_date)
        if end_date < start_date:
            frappe.throw("Blackout end date must be on or after the start date.")
        self.blackout_end_date = end_date

        if bool(self.start_time) != bool(self.end_time):
            frappe.throw("Enter both a start time and an end time, or leave both blank for an all-day blackout.")
        if self.start_time and frappe.utils.get_time(self.start_time) >= frappe.utils.get_time(self.end_time):
            frappe.throw("Blackout end time must be after the start time.")
