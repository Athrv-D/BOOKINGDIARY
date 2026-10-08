frappe.ui.form.on("Booking Diary", {
    onload(frm) {

        if (!frm.is_new()) {
            return;
        }

        const params = new URLSearchParams(window.location.search);

        const resource = params.get("resource");
        const bookingDate = params.get("booking_date");
        const startTime = params.get("start_time");
        const endTime = params.get("end_time");

        if (resource) {
            frm.set_value("resource", resource);
        }

        if (bookingDate) {
            frm.set_value("booking_date", bookingDate);
        }

        if (startTime) {
            frm.set_value("start_time", startTime);
        }

        if (endTime) {
            frm.set_value("end_time", endTime);
        }

        // Generate Booking ID
        frm.set_value(
            "booking_id",
            "BK-" + String(Date.now()).slice(-6)
        );
    }
});