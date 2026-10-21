 frappe.ui.form.on("Booking Diary", {
    

    // Keep your existing onload logic below.
    onload(frm) {
        if (!frm.is_new()) return;
  frappe.call({
    method: "booking_diary.booking_diary.doctype.booking_diary.booking_diary.is_booking_user",
    callback(r) {
        if (
            r.message === true &&
            frm.is_new() &&
            !frm.doc.customer_user
        ) {
            frm.set_value(
                "customer_user",
                frappe.session.user
            );
        }
    }
});
    

        const params = new URLSearchParams(window.location.search);

        for (const [field, param] of [
            ["resource", "resource"],
            ["booking_date", "booking_date"],
            ["start_time", "start_time"],
            ["end_time", "end_time"]
        ]) {
            const value = params.get(param);
            if (value) frm.set_value(field, value);
        }

        frm.set_value(
            "booking_id",
            "BK-" + String(Date.now()).slice(-6)
        );
         if (!frm.is_new()) return;

    frappe.call({
        method: "booking_diary.booking_diary.doctype.booking_diary.booking_diary.get_booking_source",
        callback(r) {
            if (r.message) {
                frm.set_value("booking_source", r.message);
            }
        }
    });
    },

    refresh(frm) {
        updateBookingTimezonePreview(frm);
    },
    
    
booking_type(frm) {
    if (frm.doc.booking_type === "Recurring") {
        if (!frm.doc.booking_series_id) {
            frm.set_value(
                "booking_series_id",
                frappe.utils.get_random(12)
            );
        }
    } else {
        frm.set_value("booking_series_id", "");

        if (frm.doc.repeat_until) {
            frm.set_value("repeat_until", "");
        }
    }
},

    resource(frm) {
        updateBookingTimezonePreview(frm);
    },

    booking_date(frm) {
        updateBookingTimezonePreview(frm);
    },

    start_time(frm) {
        updateBookingTimezonePreview(frm);
    },

    end_time(frm) {
        updateBookingTimezonePreview(frm);
    }
});

async function updateBookingTimezonePreview(frm) {
     const requestId = (frm._timezonePreviewRequestId || 0) + 1;
    frm._timezonePreviewRequestId = requestId;
    if (!frm.fields_dict.start_time || !frm.fields_dict.end_time) {
        return;
    }

    const resource = frm.doc.resource;
    if (!resource) {
        setTimezoneDescription(frm, "Select a resource to see timezone conversion.");
        return;
    }

    try {
        const [resourceResponse, userResponse] = await Promise.all([
            frappe.db.get_value("Resource", resource, "time_zone"),
            frappe.db.get_value("User", frappe.session.user, "time_zone")
        ]);
        if (requestId !== frm._timezonePreviewRequestId) return;

        const resourceTimezone = resourceResponse.message?.time_zone;
        const userTimezone =
            userResponse.message?.time_zone ||
            frappe.sys_defaults.time_zone ||
            Intl.DateTimeFormat().resolvedOptions().timeZone;

        if (!resourceTimezone || !userTimezone) {
            setTimezoneDescription(frm, "Unable to determine both timezones.");
            return;
        }

        for (const fieldname of ["start_time", "end_time"]) {
            const time = frm.doc[fieldname];
            let description = `Resource time: ${resourceTimezone}`;

            if (frm.doc.booking_date && time) {
                const converted = convertResourceTimeToUserTime(
                    frm.doc.booking_date,
                    time,
                    resourceTimezone,
                    userTimezone
                );

                if (converted) {
                    description +=
                        `<br>Your local time (${userTimezone}): ${converted}`;
                }
            }

            frm.fields_dict[fieldname].df.description = description;
            frm.fields_dict[fieldname].set_description();
        }
    } catch (error) {
        console.error("Unable to update timezone preview:", error);
    }
}

function setTimezoneDescription(frm, message) {
    for (const fieldname of ["start_time", "end_time"]) {
        const field = frm.fields_dict[fieldname];
        if (!field) continue;

        field.df.description = message;
        field.set_description();
    }
}

function convertResourceTimeToUserTime(
    date,
    time,
    resourceTimezone,
    userTimezone
) {
    if (!date || !time || !resourceTimezone || !userTimezone) {
        return null;
    }

    const [year, month, day] = date.split("-").map(Number);
    const [hour, minute, second = 0] =
        String(time).slice(0, 8).split(":").map(Number);

    const desiredAsUTC = Date.UTC(
        year, month - 1, day, hour, minute, second
    );

    let timestamp = desiredAsUTC;

    const resourceFormatter = new Intl.DateTimeFormat("en-GB", {
        timeZone: resourceTimezone,
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        hourCycle: "h23"
    });

    for (let i = 0; i < 4; i++) {
        const parts = Object.fromEntries(
            resourceFormatter.formatToParts(new Date(timestamp))
                .map(part => [part.type, part.value])
        );

        const displayedAsUTC = Date.UTC(
            Number(parts.year),
            Number(parts.month) - 1,
            Number(parts.day),
            Number(parts.hour),
            Number(parts.minute),
            Number(parts.second)
        );

        const difference = desiredAsUTC - displayedAsUTC;
        if (difference === 0) break;

        timestamp += difference;
    }

    return new Intl.DateTimeFormat("en-GB", {
        weekday: "short",
        year: "numeric",
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        hourCycle: "h12",
        timeZone: userTimezone
    }).format(new Date(timestamp));
}