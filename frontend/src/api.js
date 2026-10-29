
async function frappeGetList(doctype, fields, orderBy) {
  const params = new URLSearchParams({
    doctype,
    fields: JSON.stringify(fields),
    order_by: orderBy,
  })

  const response = await fetch(
    `/api/method/frappe.client.get_list?${params.toString()}`,
    {
      method: 'GET',
      credentials: 'same-origin',
      headers: { Accept: 'application/json' },
    },
  )

  if (!response.ok) {
    throw new Error(`Could not load ${doctype} (${response.status})`)
  }

  const result = await response.json()

  if (result.exc) {
    throw new Error(`Frappe returned an error loading ${doctype}`)
  }

  return result.message ?? []
}
export async function getResources() {
  const response = await fetch(
    '/api/method/booking_diary.api.get_resources',
    {
      credentials: 'include',
      headers: { Accept: 'application/json' },
    },
  )

  const result = await response.json()

  if (!response.ok || result.exc) {
    throw new Error(
      result.message || result.exception || 'Could not load resources',
    )
  }

  return result.message ?? []
}


async function frappeGet(method, params = {}) {
  const query = new URLSearchParams(params)
  const suffix = query.size ? `?${query.toString()}` : ''

  const response = await fetch(
    `/api/method/${method}${suffix}`,
    {
      credentials: 'same-origin',
      headers: { Accept: 'application/json' },
    },
  )

  const result = await response.json()

  if (!response.ok || result.exc || result.exception) {
    throw new Error(
      result.message || result.exception || `Request failed (${response.status})`,
    )
  }

  return result.message
}


async function frappePost(method, args = {}) {
  const tokenResponse = await fetch(
    `/api/method/booking_diary.api.get_csrf_token`,
    {
      method:'GET',
      credentials: 'same-origin',
      headers: { Accept: 'application/json' },
    }
  )

  const tokenResult = await tokenResponse.json()

  if (!tokenResponse.ok || tokenResult.exc || !tokenResult.message) {
    throw new Error( tokenResult.message || 'Could not retrieve the session security token.')
  }
 
  const response = await fetch(`/api/method/${method}`, {
    method: 'POST',
    credentials: 'same-origin',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
      'X-Frappe-CSRF-Token':tokenResult.message,
    },
    body: JSON.stringify(args),
  })

  const result = await response.json()

  if (!response.ok || result.exc || result.exception) {
    throw new Error(
      result.message || result.exception || `Request failed (${response.status})`,
    )
  }

  return result.message
}


 


export async function getUserTimezone() {
  return frappeGet(
    'booking_diary.services.booking_schedule.get_user_timezone',
  )
}

export async function getMultiDaySchedule(
  resource,
  startDate,
  endDate,
  userTimezone,
) {
  return frappeGet(
    'booking_diary.services.booking_schedule.get_multi_day_schedule',
    {
      resource,
      start_date: startDate,
      end_date: endDate,
      slot_duration: 30,
      user_timezone: userTimezone,
    },
  )
}

export async function getUserDaySchedule(
  resource,
  userDate,
  userTimezone,
) {
  return frappeGet(
    'booking_diary.services.booking_schedule.get_user_day_schedule',
    {
      resource,
      user_date: userDate,
      slot_duration: 30,
      user_timezone: userTimezone,
    },
  )
}


export async function createBooking({
  resource,
  resources = null,
  bookingDate,
  startTime,
  endTime,
  bookingType = 'Single Slot',
  repeatUntil = null,
  customer = '',
  customerRecord = '',
  contact = '',
  customerPhone = '',
  customerEmail = '',
  remarks = '',
  attendeeCount = 1,
  bookingQuantity = 1,
}) {
  const selectedResources = Array.isArray(resources) && resources.length
    ? resources
    : resource
      ? [resource]
      : []

  return frappePost('booking_diary.api.create_group_booking', {
    resources: selectedResources,
    booking_date: bookingDate,
    start_time: startTime,
    end_time: endTime,
    booking_type: bookingType,
    repeat_until: bookingType === 'Recurring' ? repeatUntil : null,
    customer,
    customer_record: customerRecord || null,
    contact: contact || null,
    customer_phone: customerPhone,
    customer_email: customerEmail,
    remarks,
    attendee_count: Number(attendeeCount) || 1,
    booking_quantity: Number(bookingQuantity) || 1,
  })
}


export async function validateGroupBooking({
  resources,
  bookingDate,
  startTime,
  endTime,
  bookingType = 'Single Slot',
  repeatUntil = null,
  attendeeCount = 1,
  bookingQuantity = 1,
}) {
  return frappeGet('booking_diary.api.validate_group_booking', {
    resources: JSON.stringify(resources || []),
    booking_date: bookingDate,
    start_time: startTime,
    end_time: endTime,
    booking_type: bookingType,
    repeat_until: bookingType === 'Recurring' ? repeatUntil : '',
    attendee_count: Number(attendeeCount) || 1,
    booking_quantity: Number(bookingQuantity) || 1,
  })
}


export async function getBooking(name) {
  return frappeGet('frappe.client.get', {
    doctype: 'Booking Diary',
    name,
  })
}


export async function updateBooking(doc) {
  return frappePost('frappe.client.save', { doc })
}


export async function createResource({
  resourceName,
  resourceType,
  resourceCategory = 'Other',
  description = '',
  available = true,
  timeZone = 'Asia/Kolkata',
  capacityMode = 'Exclusive',
  capacity = 1,
  pricingModel = 'Fixed',
  fixedPrice = 0,
  hourlyRate = 0,
  defaultBookingDuration = 30,
  bufferBeforeMinutes = 0,
  bufferAfterMinutes = 0,
  minimumAdvanceHours = 0,
  maximumAdvanceDays = 365,
  cancellationCutoffHours = 0,
}) {
  const doc = {
    doctype: 'Resource',
    resource_name: resourceName.trim(),
    resource_type: resourceType.trim(),
    resource_category: resourceCategory,
    description: description.trim(),
    available: available ? 1 : 0,
    time_zone: timeZone,
    capacity_mode: capacityMode,
    capacity: Number(capacity) || 1,
    pricing_model: pricingModel,
    fixed_price: Math.max(0, Number(fixedPrice) || 0),
    hourly_rate: Math.max(0, Number(hourlyRate) || 0),
    default_booking_duration: Number(defaultBookingDuration) || 30,
    buffer_before_minutes: Number(bufferBeforeMinutes) || 0,
    buffer_after_minutes: Number(bufferAfterMinutes) || 0,
    minimum_advance_hours: Number(minimumAdvanceHours) || 0,
    maximum_advance_days: Number(maximumAdvanceDays) || 365,
    cancellation_cutoff_hours: Number(cancellationCutoffHours) || 0,
  }

  return frappePost('frappe.client.insert', { doc })
}

export async function getResource(name) {
  return frappeGet('frappe.client.get', {
    doctype: 'Resource',
    name,
  })
}

export async function updateResource(doc) {
  return frappePost('frappe.client.save', { doc })
}


export async function getResourceAvailabilities(resource) {
  return frappeGet(
    'frappe.client.get_list',
    {
      doctype: 'Availability',
      fields: JSON.stringify([
        'name',
        'resource',
        'availability_type',
        'day_of_week',
        'start_time',
        'end_time',
        'available',
      ]),
      filters: JSON.stringify({ resource }),
      order_by: 'modified desc',
      limit_page_length: 100,
    },
  )
}

export async function getAvailability(name) {
  return frappeGet('frappe.client.get', {
    doctype: 'Availability',
    name,
  })
}

export async function createAvailability(doc) {
  return frappePost('frappe.client.insert', { doc })
}

export async function updateAvailability(doc) {
  return frappePost('frappe.client.save', { doc })
}

export async function deleteAvailability(name) {
  return frappePost('frappe.client.delete', {
    doctype: 'Availability',
    name,
  })
}



export async function getOverviewBookings() {
  return frappeGet('booking_diary.api.get_overview_bookings')
}

export async function updateManagedBooking({ name, resource, booking_date, start_time, end_time, remarks, status }) {
  return frappePost('booking_diary.api.update_managed_booking', {
    booking_name: name, resource, booking_date, start_time, end_time, remarks, status,
  })
}

export async function getBookings() {
  return frappeGet('frappe.client.get_list', {
    doctype: 'Booking Diary',
    fields: JSON.stringify([
      'name',
      'booking_id',
      'resource',
      'booking_date',
      'start_time',
      'end_time',
      'customer',
      'status',
      'remarks',
    ]),
    order_by: 'booking_date desc',
    limit_page_length: 500,
  })
}


export async function getBlackoutDates() {
  return frappeGet('frappe.client.get_list', {
    doctype: 'Blackout Date',
    fields: JSON.stringify(['name', 'resource', 'blackout_date', 'blackout_end_date', 'start_time', 'end_time', 'reason', 'applies_globally']),
    order_by: 'blackout_date desc',
    limit_page_length: 500,
  })
}

export async function createBlackoutDate({ resource = '', blackoutDate, blackoutEndDate = '', startTime = '', endTime = '', reason = '', appliesGlobally = false }) {
  const doc = {
    doctype: 'Blackout Date',
    resource: appliesGlobally ? '' : resource,
    blackout_date: blackoutDate,
    blackout_end_date: blackoutEndDate || blackoutDate,
    start_time: startTime ? `${startTime}:00` : null,
    end_time: endTime ? `${endTime}:00` : null,
    reason: reason.trim(),
    applies_globally: appliesGlobally ? 1 : 0,
  }
  return frappePost('frappe.client.insert', { doc })
}


export async function getCurrentUserRoles() {
  return frappeGet('booking_diary.api.get_current_user_roles')
}


export async function cancelBooking(bookingName) {
  return frappePost('booking_diary.api.cancel_booking', {
    booking_name: bookingName,
  })
}


export async function rescheduleCustomerBooking({ name, resource, bookingDate, startTime, endTime }) {
  return frappePost('booking_diary.api.reschedule_customer_booking', {
    booking_name: name,
    resource,
    booking_date: bookingDate,
    start_time: startTime,
    end_time: endTime,
  })
}

export async function getCurrentUser() {
  return frappeGet('booking_diary.api.get_current_user')
}


export async function getCustomerOptions() {
  return frappeGet('booking_diary.api.get_customer_options')
}
