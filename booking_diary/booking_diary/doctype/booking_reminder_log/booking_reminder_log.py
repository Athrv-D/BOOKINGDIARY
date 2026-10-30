import frappe
from frappe.model.document import Document


class BookingReminderLog(Document):
    """Audit record for one scheduled booking reminder."""

    def validate(self):
        if self.dedupe_key:
            existing = frappe.db.exists(
                "Booking Reminder Log",
                {
                    "dedupe_key": self.dedupe_key,
                    "name": ["!=", self.name],
                },
            )
            if existing:
                frappe.throw("This booking reminder has already been recorded.")
