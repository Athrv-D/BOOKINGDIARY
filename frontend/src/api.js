
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
