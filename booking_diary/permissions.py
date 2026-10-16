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


def booking_diary_query_conditions(user=None):
    user = user or frappe.session.user

    if not is_booking_user(user):
        return ""

    return (
        "`tabBooking Diary`.`customer_user` = "
        f"{frappe.db.escape(user)}"
    )


def booking_diary_has_permission(doc, user=None, permission_type=None):
    user = user or frappe.session.user

    # Managers and system administrators use normal Frappe permissions.
    if not is_booking_user(user):
        return None

    # Restrict customer access to their own booking documents.
    protected_actions = {
        "read",
        "write",
        "delete",
        "share",
        "print",
        "email",
        "export",
        "select",
    }

    if permission_type in protected_actions:
        return doc.customer_user == user

    return None