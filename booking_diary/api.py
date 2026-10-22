import frappe


@frappe.whitelist()
def get_my_bookings():
    """Return bookings owned by the logged-in Booking User."""

    if frappe.session.user == "Guest":
        frappe.throw("Please log in to view your bookings.")

    if "Booking User" not in frappe.get_roles(frappe.session.user):
        frappe.throw("You do not have permission to view customer bookings.")

    bookings = frappe.get_list(
        "Booking Diary",
        filters={
            "customer_user": frappe.session.user,
        },
        fields=[
            "name",
            "resource",
            "booking_date",
            "start_time",
            "end_time",
            "status",
            "payment_status",
        ],
        order_by="booking_date desc, start_time desc",
    )

    return bookings

@frappe.whitelist()
def get_resources():
    if frappe.session.user == "Guest":
        frappe.throw("Please log in to view resources.")

    return frappe.get_list(
        "Resource",
        fields=[
            "name",
            "resource_name",
            "resource_type",
            "available",
            "time_zone",
        ],
        order_by="resource_name asc",
        page_length=500,
    )