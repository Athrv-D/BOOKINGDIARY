
import frappe


def is_booking_user(user=None):
    user = user or frappe.session.user

    if user == "Administrator":
        return False

    roles = frappe.get_roles(user)

    return (
        "Booking User" in roles
        and "Booking Manager" not in roles
        and "System Manager" not in roles
    )


def booking_diary_query_conditions(user):
    if not user:
        user = frappe.session.user

    if not is_booking_user(user):
        return ""

    return f"`tabBooking Diary`.`customer_user` = {frappe.db.escape(user)}"


def booking_diary_has_permission(doc, user=None, permission_type=None):
    user = user or frappe.session.user

    if not is_booking_user(user):
        return None

    if permission_type in ("read", "write", "share", "delete"):
        return doc.customer_user == user

    return None
