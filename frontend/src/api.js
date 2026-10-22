
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


export async function createBooking({resource,bookingDate,startTime,endTime,bookingType ='Single Slot',repeatUntil =null,customer='',remarks='',}) {
  const doc = {
    doctype:'Booking Diary',
    booking_id:`BK-${String(Date.now()).slice(-6)}`,
    resource,
    booking_date:bookingDate,
    start_time:startTime,
    end_time:endTime,
    status:"Pending",
    booking_type:bookingType,
    customer:customer || '',
    remarks:remarks || '',
  }
  if(bookingType === 'Recurring'){
    doc.repeat_until = repeatUntil
  }

  return frappePost('frappe.client.insert',{doc})
  
}