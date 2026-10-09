# Copyright (c) 2026, Katalystic Consulting Services and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class BlackoutDate(Document):
    def validate(self):
        if self.applies_globally:
            self.resource = None
        elif not self.resource:
            frappe.throw(
                "Select a Resource or enable Applies Globally."
            )

        if not self.blackout_date:
            frappe.throw("Date is required.")