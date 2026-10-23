import frappe


def complete_elapsed_bookings():
    """Hourly scheduler job to mark ended bookings as Completed."""
    from booking_diary.api import complete_past_bookings

    complete_past_bookings()
