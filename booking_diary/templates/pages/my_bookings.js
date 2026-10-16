frappe.ready(function () {
    frappe.call({
        method: "booking_diary.api.get_my_bookings",
        callback: function (response) {
            const bookings = response.message || [];
            const container = document.getElementById("my-bookings-list");

            if (!container) {
                console.error("Missing #my-bookings-list container.");
                return;
            }

            if (!bookings.length) {
                container.innerHTML = "<p>You don't have any bookings yet.</p>";
                return;
            }

            container.innerHTML = bookings.map((booking) => `
                <article class="booking-card">
                    <h3>Booking ID: ${frappe.utils.escape_html(booking.name)}</h3>
                    <p>Resource: ${frappe.utils.escape_html(booking.resource || "")}</p>
                    <p>Date: ${frappe.utils.escape_html(booking.booking_date || "")}</p>
                    <p>Time: ${frappe.utils.escape_html(booking.start_time || "")}
                       – ${frappe.utils.escape_html(booking.end_time || "")}</p>
                    <p>Status: ${frappe.utils.escape_html(booking.status || "")}</p>
                </article>
            `).join("");
        }
    });
});