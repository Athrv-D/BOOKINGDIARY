# Copyright (c) 2026, Katalystic Consulting Services and contributors
# For license information, please see license.txt


import frappe
from frappe.model.document import Document
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

class Resource(Document):
    def validate(self):
        self.validate_time_zone()

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
