 
<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import {
  getResources,
  getUserTimezone,
  getMultiDaySchedule,
  getUserDaySchedule,
  getBooking,
  getBookings,
  updateBooking,
  createBooking as submitBooking,
  getResource,
  createResource,
  updateResource,
  createAvailability,
  updateAvailability,
  deleteAvailability,
  getResourceAvailabilities,
  getAvailability,
  createBlackoutDate,
  getCurrentUserRoles,
  getCurrentUser,
  getCustomerOptions,
  validateGroupBooking,
  cancelBooking,
  getOverviewBookings,
  getBookingReport,
  updateManagedBooking,
  rescheduleCustomerBooking,
} from './api'

const activeView = ref('Overview')
const canManageResources = ref(false)
const currentUserRoles = ref([])
const currentUser = ref('')
const isBookingManager = computed(() =>
  currentUser.value === 'Administrator' ||
  currentUserRoles.value.includes('System Manager') ||
  currentUserRoles.value.includes('Booking Manager')
)
const todayForReports = new Date()
const reportStartDate = ref(`${todayForReports.getFullYear()}-${String(todayForReports.getMonth() + 1).padStart(2, '0')}-01`)
const reportEndDate = ref(`${todayForReports.getFullYear()}-${String(todayForReports.getMonth() + 1).padStart(2, '0')}-${String(new Date(todayForReports.getFullYear(), todayForReports.getMonth() + 1, 0).getDate()).padStart(2, '0')}`)
const reportRecords = ref([])
const reportLoading = ref(false)
const reportError = ref('')
const reportLoaded = ref(false)
const reportActiveCount = computed(() => reportRecords.value.filter(row => ['Pending', 'Confirmed'].includes(row.status)).length)
const reportConfirmedCount = computed(() => reportRecords.value.filter(row => row.status === 'Confirmed').length)
const reportPendingCount = computed(() => reportRecords.value.filter(row => row.status === 'Pending').length)
const reportCancelledCount = computed(() => reportRecords.value.filter(row => row.status === 'Cancelled').length)
const reportCompletedCount = computed(() =>
  reportRecords.value.filter(row => row.status === 'Completed').length
)

const reportNoShowCount = computed(() =>
  reportRecords.value.filter(row => row.status === 'No Show').length
)
const reportByResource = computed(() => {
  const grouped = new Map()
  for (const row of reportRecords.value) {
    const key = row.resource_name || row.resource || 'Unknown'
    const entry = grouped.get(key) || { name: key, count: 0, confirmed: 0, pending: 0, cancelled: 0 }
    entry.count += 1
    if (row.status === 'Confirmed') entry.confirmed += 1
    if (row.status === 'Pending') entry.pending += 1
    if (row.status === 'Cancelled') entry.cancelled += 1
    grouped.set(key, entry)
  }
  return [...grouped.values()].sort((a, b) => b.count - a.count || a.name.localeCompare(b.name))
})
async function loadReports() {
  if (!isBookingManager.value) {
    reportError.value = 'Reports are available to Booking Managers and administrators only.'
    return
  }
  if (!reportStartDate.value || !reportEndDate.value || reportEndDate.value < reportStartDate.value) {
    reportError.value = 'Choose a valid date range.'
    return
  }
  reportLoading.value = true
  reportError.value = ''
  try {
    reportRecords.value = await getBookingReport(reportStartDate.value, reportEndDate.value)
    reportLoaded.value = true
  } catch (error) {
    reportError.value = error.message || 'Could not load booking reports.'
  } finally {
    reportLoading.value = false
  }
}
function exportBookingReport() {
  const columns = [
    ['Booking ID', 'booking_id'], ['Customer', 'customer'], ['Resource', 'resource_name'],
    ['Category', 'resource_category'], ['Date', 'booking_date'], ['Start', 'start_time'],
    ['End', 'end_time'], ['Status', 'status'],
  ]
  const quote = value => `"${String(value ?? '').replace(/"/g, '""')}"`
  const csv = [columns.map(([label]) => quote(label)).join(','), ...reportRecords.value.map(row => columns.map(([, key]) => quote(row[key])).join(','))].join('\r\n')
  const blob = new Blob(['\ufeff', csv], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `booking-report-${reportStartDate.value}-to-${reportEndDate.value}.csv`
  link.click()
  URL.revokeObjectURL(url)
}

const overviewRecords = ref([])
const overviewLoading = ref(false)
const overviewError = ref('')
const overviewToday = computed(() => dateKey(new Date()))
const overviewTodayBookings = computed(() => overviewRecords.value.filter(b => b.booking_date === overviewToday.value && b.status !== 'Cancelled'))
const overviewPending = computed(() => overviewRecords.value.filter(b => b.status === 'Pending').slice(0, 8))
const overviewUpcoming = computed(() => overviewRecords.value.filter(b => b.booking_date >= overviewToday.value && ['Pending', 'Confirmed'].includes(b.status)).slice(0, 8))
const overviewConfirmedCount = computed(() => overviewRecords.value.filter(b => b.status === 'Confirmed' && b.booking_date >= overviewToday.value).length)

async function loadOverview() {
  overviewLoading.value = true
  overviewError.value = ''
  try {
    overviewRecords.value = await getOverviewBookings()
  } catch (error) {
    overviewError.value = error.message || 'Could not load overview.'
  } finally {
    overviewLoading.value = false
  }
}

async function setBookingDecision(booking, status) {
  if (!isBookingManager.value) return
  const label = status === 'Confirmed' ? 'confirm' : 'reject'
  if (!window.confirm(`${label === 'confirm' ? 'Confirm' : 'Reject'} this booking?`)) return
  try {
    await updateManagedBooking({ name: booking.name, status })
    await Promise.all([loadOverview(), loadBookingsPage(), loadSchedule()])
  } catch (error) {
    overviewError.value = error.message || `Could not ${label} booking.`
  }
}
const calendarView = ref('Week')
const selectedDate = ref(new Date())
const resourceFilter = ref('All resources')
const statusFilter = ref('All statuses')
const searchQuery = ref('')

const navigation = [
  { name: 'Overview', icon: '⌂' },
  { name: 'Resource Desk', icon: '▦' },
  { name: 'Bookings', icon: '▤' },
  { name: 'Resources', icon: '▧' },
  { name: 'Reports', icon: '▤' },
]

const resources = ref([])
const resourcesLoading = ref(false)
const resourcesError = ref('')


const resourceFormOpen = ref(false)
const resourceEditMode = ref(false)
const resourceSaving = ref(false)
const resourceFormError = ref('')

const resourceForm = ref({
  name: '',
  resource_name: '',
  resource_type: '',
  resource_category: 'Venue',
  description: '',
  available: true,
  time_zone: 'Asia/Kolkata',
  capacity_mode: 'Exclusive',
  capacity: 1,
  default_booking_duration: 30,
  buffer_before_minutes: 0,
  buffer_after_minutes: 0,
  minimum_advance_hours: 0,
  maximum_advance_days: 365,
  cancellation_cutoff_hours: 0,
})


const availabilityModalOpen = ref(false)
const availabilityResource = ref(null)
const availabilityLoading = ref(false)
const availabilitySaving = ref(false)
const availabilityError = ref('')
const availabilityRecords = ref([])

const availabilityDays = [
  'Monday',
  'Tuesday',
  'Wednesday',
  'Thursday',
  'Friday',
  'Saturday',
  'Sunday',
]

const availabilityForm = ref({
  availability_type: 'Multiple Days',
  day_of_week: 'Monday',
  start_time: '09:00',
  end_time: '17:00',
  available: true,
  weekly_schedule: availabilityDays.map(day => ({
    day_of_week: day,
    start_time: '09:00',
    end_time: '17:00',
    available: !['Saturday', 'Sunday'].includes(day),
  })),
})




const userTimezone = ref('UTC')
const bookings = ref([])


const bookingsPageLoading = ref(false)
const bookingsPageError = ref('')
const bookingsPageRecords = ref([])
const bookingsPageSearch = ref('')
const bookingsPageStatus = ref('All statuses')

const resourceSchedules = ref({})
const scheduleLoading = ref(false)
const scheduleError = ref('')

const blackoutModalOpen = ref(false)
const blackoutSaving = ref(false)
const blackoutError = ref('')
const blackoutForm = ref({
  blackout_date: '',
  blackout_end_date: '',
  start_time: '',
  end_time: '',
  resource: 'All resources',
  applies_globally: true,
  reason: '',
})

 
async function loadResources() {
  resourcesLoading.value = true
  resourcesError.value = ''

  try {
    resources.value = await getResources()
  } catch (error) {
    console.error('Failed to load resources:', error)
    resourcesError.value = error.message
  } finally {
    resourcesLoading.value = false
  }
}


async function loadBookingsPage() {
  bookingsPageLoading.value = true
  bookingsPageError.value = ''

  try {
    bookingsPageRecords.value = await getBookings()
  } catch (error) {
    bookingsPageError.value =
      error.message || 'Could not load bookings.'
  } finally {
    bookingsPageLoading.value = false
  }
}



function openResourceCreate() {
  resourceFormError.value = ''
  resourceEditMode.value = false

  resourceForm.value = {
    name: '',
    resource_name: '',
    resource_type: '',
    resource_category: 'Venue',
    description: '',
    available: true,
    time_zone: 'Asia/Kolkata',
    capacity_mode: 'Exclusive',
    capacity: 1,
    default_booking_duration: 30,
    buffer_before_minutes: 0,
    buffer_after_minutes: 0,
    minimum_advance_hours: 0,
    maximum_advance_days: 365,
    cancellation_cutoff_hours: 0,
  }

  resourceFormOpen.value = true
}

async function openResourceEdit(resource) {
  resourceFormError.value = ''
  resourceEditMode.value = true

  try {
    const doc = await getResource(resource.name)

    resourceForm.value = {
      ...doc,
      resource_category: doc.resource_category || 'Other',
      available: Boolean(doc.available),
    }

    resourceFormOpen.value = true
  } catch (error) {
    resourceFormError.value =
      error.message || 'Could not load resource details.'
  }
}

async function saveResource() {
  resourceFormError.value = ''

  const form = resourceForm.value
  if (form.capacity_mode === 'Exclusive') form.capacity = 1

  if (!form.resource_name.trim() || !form.resource_type.trim() || !form.time_zone.trim()) {
    resourceFormError.value =
      'Resource name, resource type, and time zone are required.'
    return
  }

  resourceSaving.value = true

  try {
    if (resourceEditMode.value) {
      await updateResource({
        ...form,
        available: form.available ? 1 : 0,
      })
    } else {
      await createResource({
        resourceName: form.resource_name,
        resourceType: form.resource_type,
        resourceCategory: form.resource_category,
        description: form.description,
        available: form.available,
        timeZone: form.time_zone,
        capacityMode: form.capacity_mode,
        capacity: form.capacity,
        defaultBookingDuration: form.default_booking_duration,
        bufferBeforeMinutes: form.buffer_before_minutes,
        bufferAfterMinutes: form.buffer_after_minutes,
        minimumAdvanceHours: form.minimum_advance_hours,
        maximumAdvanceDays: form.maximum_advance_days,
        cancellationCutoffHours: form.cancellation_cutoff_hours,
      })
    }

    resourceFormOpen.value = false
    await loadResources()
    await loadSchedule()
  } catch (error) {
    resourceFormError.value =
      error.message || 'Could not save resource.'
  } finally {
    resourceSaving.value = false
  }
}


async function openResourceAvailability(resource) {
  availabilityResource.value = resource
  availabilityError.value = ''
  availabilityRecords.value = []
  availabilityLoading.value = true

  try {
    availabilityRecords.value = await getResourceAvailabilities(resource.name)

    const weeklyRecord = availabilityRecords.value.find(
      record => record.availability_type === 'Multiple Days'
    )

    if (weeklyRecord) {
      const fullRecord = await getAvailability(weeklyRecord.name)

      availabilityForm.value = {
        availability_type: 'Multiple Days',
        day_of_week: 'Monday',
        start_time: '09:00',
        end_time: '17:00',
        available: true,
        weekly_schedule: availabilityDays.map(day => {
          const savedDay = (fullRecord.weekly_schedule || []).find(
            item => item.day_of_week === day
          )

          return savedDay
            ? {
                ...savedDay,
                available: Boolean(savedDay.available),
                start_time: String(savedDay.start_time || '09:00').slice(0, 5),
                end_time: String(savedDay.end_time || '17:00').slice(0, 5),
              }
            : {
                day_of_week: day,
                start_time: '09:00',
                end_time: '17:00',
                available: false,
              }
        }),
      }
    } else {
      availabilityForm.value = {
        availability_type: 'Multiple Days',
        day_of_week: 'Monday',
        start_time: '09:00',
        end_time: '17:00',
        available: true,
        weekly_schedule: availabilityDays.map(day => ({
          day_of_week: day,
          start_time: '09:00',
          end_time: '17:00',
          available: !['Saturday', 'Sunday'].includes(day),
        })),
      }
    }

    availabilityModalOpen.value = true
  } catch (error) {
    availabilityError.value =
      error.message || 'Could not load resource availability.'
  } finally {
    availabilityLoading.value = false
  }
}

async function saveResourceAvailability() {
  availabilityError.value = ''

  const form = availabilityForm.value
  const resource = availabilityResource.value

  if (!resource) {
    availabilityError.value = 'Select a resource first.'
    return
  }

  for (const day of form.weekly_schedule) {
    if (
      day.available &&
      (!day.start_time || !day.end_time || day.start_time >= day.end_time)
    ) {
      availabilityError.value =
        `Set a valid start and end time for ${day.day_of_week}.`
      return
    }
  }

  availabilitySaving.value = true

  try {
    const existing = availabilityRecords.value.find(
      record => record.availability_type === 'Multiple Days'
    )

    const doc = {
      doctype: 'Availability',
      ...(existing ? { name: existing.name } : {}),
      resource: resource.name,
      availability_type: 'Multiple Days',
      weekly_schedule: form.weekly_schedule.map(day => ({
        doctype: 'Availability Day',
        day_of_week: day.day_of_week,
        start_time: `${day.start_time}:00`,
        end_time: `${day.end_time}:00`,
        available: day.available ? 1 : 0,
      })),
    }

    if (existing) {
      const fullRecord = await getAvailability(existing.name)
      await updateAvailability({
        ...fullRecord,
        ...doc,
        weekly_schedule: doc.weekly_schedule,
      })
    } else {
      await createAvailability(doc)
    }

    availabilityModalOpen.value = false
    await loadSchedule()
  } catch (error) {
    availabilityError.value =
      error.message || 'Could not save resource availability.'
  } finally {
    availabilitySaving.value = false
  }
}



function openBlackoutForm() {
  blackoutError.value = ''
  blackoutForm.value = {
    blackout_date: dateKey(selectedDate.value),
    blackout_end_date: dateKey(selectedDate.value),
    start_time: '',
    end_time: '',
    resource: resourceFilter.value !== 'All resources' ? resourceFilter.value : (resources.value[0]?.name || ''),
    applies_globally: resourceFilter.value === 'All resources',
    reason: '',
  }
  blackoutModalOpen.value = true
}

async function saveBlackoutDate() {
  blackoutError.value = ''
  if (!blackoutForm.value.blackout_date) {
    blackoutError.value = 'Choose a blackout date.'
    return
  }
  if (blackoutForm.value.blackout_end_date && blackoutForm.value.blackout_end_date < blackoutForm.value.blackout_date) {
    blackoutError.value = 'End date must be on or after the start date.'
    return
  }
  if (Boolean(blackoutForm.value.start_time) !== Boolean(blackoutForm.value.end_time)) {
    blackoutError.value = 'Enter both times for a partial-day blackout, or leave both blank for all day.'
    return
  }
  if (blackoutForm.value.start_time && blackoutForm.value.start_time >= blackoutForm.value.end_time) {
    blackoutError.value = 'End time must be after start time.'
    return
  }
  if (!blackoutForm.value.applies_globally && !blackoutForm.value.resource) {
    blackoutError.value = 'Choose a resource or apply the blackout globally.'
    return
  }

  blackoutSaving.value = true
  try {
    await createBlackoutDate({
      blackoutDate: blackoutForm.value.blackout_date,
      blackoutEndDate: blackoutForm.value.blackout_end_date,
      startTime: blackoutForm.value.start_time,
      endTime: blackoutForm.value.end_time,
      resource: blackoutForm.value.resource,
      appliesGlobally: blackoutForm.value.applies_globally,
      reason: blackoutForm.value.reason,
    })
    blackoutModalOpen.value = false
    await loadSchedule()
  } catch (error) {
    blackoutError.value = error.message || 'Could not save blackout date.'
  } finally {
    blackoutSaving.value = false
  }
}


async function loadSchedule() {
  if (!resources.value.length) return

  scheduleLoading.value = true
  scheduleError.value = ''

  try {
    const date = selectedDate.value
    const start = calendarView.value === 'Month'
      ? new Date(date.getFullYear(), date.getMonth(), 1)
      : startOfWeek(date)

    const end = calendarView.value === 'Month'
      ? new Date(date.getFullYear(), date.getMonth() + 1, 0)
      : addDays(start, 6)

    const results = await Promise.all(
      resources.value.map(async (resource) => {
        const schedule = calendarView.value === 'Day'
          ? await getUserDaySchedule(
              resource.name,
              dateKey(date),
              userTimezone.value,
            )
          : await getMultiDaySchedule(
              resource.name,
              dateKey(start),
              dateKey(end),
              userTimezone.value,
            )

        return { resource, schedule }
      }),
    )

    
resourceSchedules.value = Object.fromEntries(
  results.map(({ resource, schedule }) => [
    resource.name,
    schedule.schedules ?? [],
  ])
)

bookings.value = results.flatMap(({ resource, schedule }) => {
  const schedules = schedule.schedules ?? []

  return schedules.flatMap(daySchedule =>
    (daySchedule.bookings ?? []).map(booking => ({
      id: booking.booking_id ?? booking.name,
      docName:booking.name,
      title: booking.customer || 'Booked',
      resource: resource.name,
      resourceLabel: resource.resource_name || resource.name,
      date: daySchedule.date,
      start: booking.start_time_user_datetime
        ? new Date(booking.start_time_user_datetime)
        : new Date(`${daySchedule.date}T${booking.start_time}`),
      end: booking.end_time_user_datetime
        ? new Date(booking.end_time_user_datetime)
        : new Date(`${daySchedule.date}T${booking.end_time}`),
      status: booking.status || 'Booked',
      color: 'blue',
    }))
  )
})

  } catch (error) {
    console.error('Failed to load schedule:', error)
    scheduleError.value = error.message
  } finally {
    scheduleLoading.value = false
  }
  

}

watch([selectedDate, calendarView], () => {
  if (resources.value.length) {
    loadSchedule()
  }
})

onMounted(async () => {
  try {
    const roles = await getCurrentUserRoles()
    currentUserRoles.value = roles
    currentUser.value = await getCurrentUser()
    // Booking User is read-only unless the user also has a manager/admin role.
    canManageResources.value =
      !roles.includes('Booking User') ||
      roles.includes('Booking Manager') ||
      roles.includes('System Manager')
  } catch (error) {
    // Fail closed: keep configuration controls hidden if roles cannot be verified.
    console.error('Failed to load user roles:', error)
    canManageResources.value = false
  }

  try {
    userTimezone.value = await getUserTimezone()
  } catch (error) {
    console.error('Failed to load user timezone:', error)
  }

  await loadResources()
  await loadCustomerOptions()
  await loadSchedule()
  await loadOverview()
})


function dateKey(date) {
  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, '0')
  const d = String(date.getDate()).padStart(2, '0')
  return `${y}-${m}-${d}`
}
function blackoutResourcesOn(date) {
  const key = dateKey(date)

  return resources.value.filter(resource =>
    (resourceSchedules.value[resource.name] || []).some(
      daySchedule =>
        daySchedule.date === key && daySchedule.is_blackout
    )
  )
}
function timeToMinutes(value) {
  if (value instanceof Date) {
    return value.getHours() * 60 + value.getMinutes()
  }

  if (typeof value === 'string') {
    const time = value.includes('T')
      ? new Date(value)
      : null

    if (time && !Number.isNaN(time.getTime())) {
      return time.getHours() * 60 + time.getMinutes()
    }

    const [hours, minutes] = value.split(':').map(Number)
    return (hours || 0) * 60 + (minutes || 0)
  }

  return 0
}

function addDays(date, amount) {
  const result = new Date(date)
  result.setDate(result.getDate() + amount)
  return result
}

function startOfWeek(date) {
  const result = new Date(date)
  result.setHours(0, 0, 0, 0)
  result.setDate(result.getDate() - ((result.getDay() + 6) % 7))
  return result
}

function sameDay(a, b) {
  return dateKey(a) === dateKey(b)
}

function formatDate(date, options) {
  return new Intl.DateTimeFormat('en-IN', options).format(date)
}

function timeLabel(time) {
  if (time instanceof Date) {
    return time.toLocaleTimeString([], {
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
    })
  }

  if (typeof time !== 'string') {
    return ''
  }

  if (time.includes('T')) {
    const date = new Date(time)

    if (!Number.isNaN(date.getTime())) {
      return date.toLocaleTimeString([], {
        hour: '2-digit',
        minute: '2-digit',
        hour12: false,
      })
    }
  }

  const [hours, minutes] = time.split(':')
  return `${hours.padStart(2, '0')}:${(minutes || '00').padStart(2, '0')}`
}
function offsetDate(days) {
  return dateKey(addDays(new Date(), days))
}



const filteredBookings = computed(() => {
  return bookings.value.filter((booking) => {
    const matchesResource =
      resourceFilter.value === 'All resources' ||
      booking.resource === resourceFilter.value

    const matchesStatus =
      statusFilter.value === 'All statuses' ||
      booking.status === statusFilter.value

    const query = searchQuery.value.trim().toLowerCase()
    const matchesSearch =
      !query ||
      booking.title?.toLowerCase().includes(query) ||
      booking.resource?.toLowerCase().includes(query) ||
      booking.id?.toLowerCase().includes(query)

    return matchesResource && matchesStatus && matchesSearch
  })
})

const weekDays = computed(() => {
  const start = startOfWeek(selectedDate.value)
  return Array.from({ length: 7 }, (_, index) => addDays(start, index))
})

const monthDays = computed(() => {
  const first = new Date(
    selectedDate.value.getFullYear(),
    selectedDate.value.getMonth(),
    1,
  )
  const gridStart = startOfWeek(first)
  return Array.from({ length: 42 }, (_, index) => addDays(gridStart, index))
})

const viewTitle = computed(() => {
  const date = selectedDate.value
  if (calendarView.value === 'Month') {
    return formatDate(date, { month: 'long', year: 'numeric' })
  }
  if (calendarView.value === 'Week') {
    const start = weekDays.value[0]
    const end = weekDays.value[6]
    const sameMonth = start.getMonth() === end.getMonth()
    if (sameMonth) {
      return `${formatDate(start, { month: 'short' })} ${start.getDate()} – ${end.getDate()}, ${end.getFullYear()}`
    }
    return `${formatDate(start, { month: 'short', day: 'numeric' })} – ${formatDate(end, { month: 'short', day: 'numeric', year: 'numeric' })}`
  }
  return formatDate(date, {
    weekday: 'long', month: 'long', day: 'numeric', year: 'numeric',
  })
})

function bookingsOn(date) {
  const key = dateKey(date)
  return filteredBookings.value
    .filter((booking) => booking.date === key)
    .sort((a, b) => timeToMinutes(a.start)-timeToMinutes(b.start))

}

 


function bookingsForResource(resource, date = selectedDate.value) {
  return bookingsOn(date).filter((booking) => booking.resource === resource)
}

function chooseView(view) {
  calendarView.value = view
}

function goToday() {
  selectedDate.value = new Date()
}

function navigate(direction) {
  const date = new Date(selectedDate.value)
  if (calendarView.value === 'Month') {
    date.setDate(1)
    date.setMonth(date.getMonth() + direction)
  } else if (calendarView.value === 'Week') {
    date.setDate(date.getDate() + direction * 7)
  } else {
    date.setDate(date.getDate() + direction)
  }
  selectedDate.value = date
}

function selectDay(date) {
  selectedDate.value = new Date(date)
  calendarView.value = 'Day'
}

function bookingStyle(booking) {
  const startMinutes = timeToMinutes(booking.start)
  const endMinutes = timeToMinutes(booking.end)

  const top = ((startMinutes - 8 * 60) / 60) * 64
  const height = Math.max(
    ((endMinutes - startMinutes) / 60) * 64,
    24
  )

  return {
    top: `${Math.max(top, 0)}px`,
    height: `${height}px`,
    background: booking.color,
  }
}


const TIMELINE_START_MINUTES = 0
const TIMELINE_END_MINUTES = 24 * 60
const TIMELINE_HOUR_WIDTH = 100

function timelineBookingStyle(booking) {
  const startMinutes = timeToMinutes(booking.start)
  const endMinutes = timeToMinutes(booking.end)

  const visibleStart = Math.max(
    startMinutes,
    TIMELINE_START_MINUTES,
  )
  const visibleEnd = Math.min(
    endMinutes,
    TIMELINE_END_MINUTES,
  )

  if (visibleEnd <= visibleStart) {
    return { display: 'none' }
  }

  return {
    left: `${(visibleStart - TIMELINE_START_MINUTES) / 60 * TIMELINE_HOUR_WIDTH}px`,
    width: `${(visibleEnd - visibleStart) / 60 * TIMELINE_HOUR_WIDTH}px`,
    top: '12px',
    height: '72px',
  }
}


function timelineAvailabilityStyle(slot, selectedDay) {
  if (!slot.start_time_user_datetime || !slot.end_time_user_datetime) {
    return null
  }

  const start = new Date(slot.start_time_user_datetime)
  const end = new Date(slot.end_time_user_datetime)

  const dayStart = new Date(selectedDay)
  dayStart.setHours(0, 0, 0, 0)

  const dayEnd = new Date(dayStart)
  dayEnd.setDate(dayEnd.getDate() + 1)

  const visibleStart = Math.max(start.getTime(), dayStart.getTime())
  const visibleEnd = Math.min(end.getTime(), dayEnd.getTime())

  if (visibleEnd <= visibleStart) return null

  const startMinutes = (visibleStart - dayStart.getTime()) / 60000
  const endMinutes = (visibleEnd - dayStart.getTime()) / 60000

  return {
    left: `${startMinutes / 60 * TIMELINE_HOUR_WIDTH}px`,
    width: `${(endMinutes - startMinutes) / 60 * TIMELINE_HOUR_WIDTH}px`,
  }
}




const selectedBooking = ref(null)
const bookingEditMode = ref(false)
const bookingUpdateError = ref('')
const bookingUpdating = ref(false)
const bookingDetailsLoading = ref(false)
const bookingDetailsError = ref('')


async function saveBookingChanges() {
  bookingUpdateError.value = ''
  bookingUpdating.value = true

  try {
    const updatedRecord = await updateManagedBooking({
      name: selectedBooking.value.name || selectedBooking.value.docName,
      resource: selectedBooking.value.resource,
      booking_date: selectedBooking.value.booking_date || selectedBooking.value.date,
      start_time: selectedBooking.value.start_time || selectedBooking.value.start,
      end_time: selectedBooking.value.end_time || selectedBooking.value.end,
      remarks: selectedBooking.value.remarks || '',
      status: selectedBooking.value.status,
    })

    selectedBooking.value = {
      ...selectedBooking.value,
      ...updatedRecord,
    }

    bookingEditMode.value = false
    await loadSchedule()
  } catch (error) {
    bookingUpdateError.value =
      error.message || 'Could not save booking changes.'
  } finally {
    bookingUpdating.value = false
  }
}


const rescheduleOpen = ref(false)
const rescheduleSaving = ref(false)
const rescheduleError = ref('')
const rescheduleForm = ref({
  resource: '',
  bookingDate: '',
  startTime: '',
  endTime: '',
})

function openRescheduleForm() {
  if (!selectedBooking.value) return
  const booking = selectedBooking.value
  const asTime = value => String(value || '').slice(0, 5)
  rescheduleError.value = ''
  rescheduleForm.value = {
    resource: booking.resource || '',
    bookingDate: String(booking.booking_date || booking.date || '').slice(0, 10),
    startTime: asTime(booking.start_time || booking.start),
    endTime: asTime(booking.end_time || booking.end),
  }
  rescheduleOpen.value = true
}

async function saveReschedule() {
  if (!selectedBooking.value) return
  rescheduleError.value = ''
  rescheduleSaving.value = true
  try {
    await rescheduleCustomerBooking({
      name: selectedBooking.value.name || selectedBooking.value.docName,
      resource: rescheduleForm.value.resource,
      bookingDate: rescheduleForm.value.bookingDate,
      startTime: rescheduleForm.value.startTime.length === 5 ? `${rescheduleForm.value.startTime}:00` : rescheduleForm.value.startTime,
      endTime: rescheduleForm.value.endTime.length === 5 ? `${rescheduleForm.value.endTime}:00` : rescheduleForm.value.endTime,
    })
    rescheduleOpen.value = false
    await openBooking(selectedBooking.value)
    await loadSchedule()
    await loadBookingsPage()
    await loadOverview()
  } catch (error) {
    rescheduleError.value = error.message || 'Could not reschedule this booking.'
  } finally {
    rescheduleSaving.value = false
  }
}

const bookingCancelling = ref(false)
const bookingCancelError = ref('')
const bookingCancelSuccess = ref('')

const canCancelSelectedBooking = computed(() => {
  const booking = selectedBooking.value
  if (!booking || !booking.docName && !booking.name) return false
  if (!['Pending', 'Confirmed'].includes(booking.status)) return false
  const roles = currentUserRoles.value
  return booking.customer_user === currentUser.value
    || roles.includes('Booking Manager')
    || roles.includes('System Manager')
    || currentUser.value === 'Administrator'
})

async function cancelSelectedBooking() {
  if (!selectedBooking.value) return
  if (!window.confirm('Cancel this booking? The booking will remain in the system with Cancelled status.')) return
  bookingCancelError.value = ''
  bookingCancelSuccess.value = ''
  bookingCancelling.value = true
  try {
    const name = selectedBooking.value.docName || selectedBooking.value.name
    const result = await cancelBooking(name)
    const finalStatus = result.status || 'Cancelled'
    bookingCancelSuccess.value = result.message || (
      finalStatus === 'Completed'
        ? 'This booking has ended and is now marked Completed.'
        : 'Booking cancelled.'
    )
    selectedBooking.value = {
      ...selectedBooking.value,
      status: finalStatus,
    }
    await loadSchedule()
    await loadBookingsPage()
  } catch (error) {
    bookingCancelError.value = error.message || 'Could not cancel booking.'
  } finally {
    bookingCancelling.value = false
  }
}

async function openBooking(booking) {
  const documentName = booking?.docName || booking?.name
  if (!documentName || documentName === 'null' || documentName === 'undefined') {
    bookingDetailsError.value = 'Booking details are not available for this booking.'
    return
  }

  selectedBooking.value = {
    ...booking,
    docName: documentName,
  }
  bookingCancelError.value = ''
  bookingCancelSuccess.value = ''
  bookingDetailsError.value = ''
  bookingDetailsLoading.value = true

  try {
    const record = await getBooking(documentName)

    selectedBooking.value = {
      ...booking,
      ...record,
      id: record.booking_id || booking.id,
      resourceLabel: booking.resourceLabel || record.resource,
      title: record.customer || booking.title,
      date: record.booking_date || booking.date,
      start: record.start_time || booking.start,
      end: record.end_time || booking.end,
    }
  } catch (error) {
    bookingDetailsError.value =
      error.message || 'Could not load booking details.'
  } finally {
    bookingDetailsLoading.value = false
  }
}

const bookingSubmitting = ref(false)
const bookingError = ref('')
const bookingSuccess = ref('')

async function createBooking() {
  bookingError.value = ''
  bookingSuccess.value = ''

  if (!selectedBookingSlot.value) {
    bookingError.value = 'Select an available slot first.'
    return
  }

  bookingSubmitting.value = true

  try {
    const slot = selectedBookingSlot.value

    await submitBooking({
      resources: [slot.resource],
      bookingDate: slot.bookingDate,
      startTime: slot.startTime,
      endTime: slot.endTime,
    })

    bookingSuccess.value = 'Booking created successfully.'
    selectedBookingSlot.value = null
    await loadSchedule()
  } catch (error) {
    bookingError.value = error.message || 'Could not create booking.'
  } finally {
    bookingSubmitting.value = false
  }
}

const customerOptions = ref({ customers: [], contacts: [] })
async function loadCustomerOptions() {
  try {
    customerOptions.value = await getCustomerOptions()
  } catch (error) {
    console.warn('Customer and contact lookup is unavailable:', error)
  }
}

const bookingFormOpen = ref(false)

const formAvailability = ref({ loading: false, error: '', schedules: [] })
let formAvailabilityRequestId = 0

async function loadFormAvailability() {
  const requestId = ++formAvailabilityRequestId
  const selectedResources = [...bookingForm.value.resources]
  const bookingDate = bookingForm.value.bookingDate

  formAvailability.value = { loading: false, error: '', schedules: [] }
  if (!bookingFormOpen.value || !selectedResources.length || !bookingDate) return

  formAvailability.value.loading = true
  try {
    const results = await Promise.all(selectedResources.map(async resource => {
      const result = await getUserDaySchedule(resource, bookingDate, userTimezone.value)
      return { resource, schedules: result.schedules || [] }
    }))
    if (requestId !== formAvailabilityRequestId) return
    formAvailability.value = {
      loading: false,
      error: '',
      schedules: results.flatMap(item => item.schedules.map(schedule => ({
        ...schedule,
        resource: item.resource,
      }))),
    }
  } catch (error) {
    if (requestId !== formAvailabilityRequestId) return
    formAvailability.value = {
      loading: false,
      error: error.message || 'Could not load availability for this date.',
      schedules: [],
    }
  }
}

const formAvailabilitySlots = computed(() => formAvailability.value.schedules.flatMap(day => (
  (day.slots || []).map(slot => ({ ...slot, resource: day.resource, date: day.date, is_blackout: day.is_blackout, blackout_reason: day.blackout_reason }))
)))

const bookingForm = ref({
  resources: [],
  bookingDate: dateKey(selectedDate.value),
  startTime: '09:00:00',
  endTime: '09:30:00',
  bookingType: 'Single Slot',
  repeatUntil: '',
  customer: '',
  customerRecord: '',
  contact: '',
  customerPhone: '',
  customerEmail: '',
  remarks: '',
  attendeeCount: 1,
  bookingQuantity: 1,
})

const bookingResourceCategories = ['Venue', 'Staff', 'Equipment', 'Facility', 'Other']
const bookingResourceCategoryFilter = ref('All categories')
const filteredBookingResources = computed(() => resources.value.filter(resource =>
  bookingResourceCategoryFilter.value === 'All categories' ||
  (resource.resource_category || 'Other') === bookingResourceCategoryFilter.value
))

const selectedBookingResources = computed(() =>
  bookingForm.value.resources
    .map(name => resources.value.find(resource => resource.name === name))
    .filter(Boolean)
)

const bookingDurationHours = computed(() => {
  const [startHour, startMinute] = String(bookingForm.value.startTime || '0:0').split(':').map(Number)
  const [endHour, endMinute] = String(bookingForm.value.endTime || '0:0').split(':').map(Number)
  return Math.max(0, ((endHour * 60 + endMinute) - (startHour * 60 + startMinute)) / 60)
})

const selectedCapacityModes = computed(() => [
  ...new Set(selectedBookingResources.value.map(resource => resource.capacity_mode || 'Exclusive')),
])

const selectedResourcesAreSharedPool = computed(() =>
  selectedBookingResources.value.length > 0 &&
  selectedBookingResources.value.every(resource => resource.capacity_mode === 'Shared Pool')
)

function capacityModeDescription(mode) {
  if (mode === 'Shared Pool') return 'Multiple bookings can overlap within the resource’s total capacity.'
  if (mode === 'Per Booking') return 'Each booking has its own attendee limit; overlapping use is still restricted.'
  return 'Only one booking can use this resource at a time.'
}

watch(selectedBookingResources, (selected) => {
  if (!selected.length || !selected.every(resource => resource.capacity_mode === 'Shared Pool')) {
    bookingForm.value.bookingQuantity = 1
  }
}, { deep: true })

watch(
  () => [
    bookingFormOpen.value,
    [...bookingForm.value.resources],
    bookingForm.value.bookingDate,
    bookingForm.value.attendeeCount,
    bookingForm.value.bookingQuantity,
  ],
  loadFormAvailability,
  { deep: true },
)

function openNewBooking(resource = null) {
  bookingError.value = ''
  bookingSuccess.value = ''

  const slot = selectedBookingSlot.value
  const resourceName = typeof resource === 'string' ? resource : resource?.name

  bookingForm.value = {
    resources: slot?.resource
      ? [slot.resource]
      : resourceName
        ? [resourceName]
        : resources.value[0]?.name
          ? [resources.value[0].name]
          : [],
    bookingDate: slot?.bookingDate || dateKey(selectedDate.value),
    startTime: slot?.startTime || '09:00:00',
    endTime: slot?.endTime || '10:00:00',
    bookingType: 'Single Slot',
    repeatUntil: '',
    customer: '',
    customerRecord: '',
    contact: '',
    customerPhone: '',
    customerEmail: '',
    remarks: '',
    attendeeCount: 1,
    bookingQuantity: 1,
  }

  bookingFormOpen.value = true
}


const liveBookingValidation = ref({ checking: false, valid: false, errors: [], resources: [] })
let liveValidationTimer = null
let liveValidationRequestId = 0

watch(
  () => [
    bookingFormOpen.value,
    [...bookingForm.value.resources],
    bookingForm.value.bookingDate,
    bookingForm.value.attendeeCount,
    bookingForm.value.bookingQuantity,
    bookingForm.value.startTime,
    bookingForm.value.endTime,
    bookingForm.value.bookingType,
    bookingForm.value.repeatUntil,
  ],
  (values) => {
    if (liveValidationTimer) clearTimeout(liveValidationTimer)
    const requestId = ++liveValidationRequestId
    liveBookingValidation.value = { checking: false, valid: false, errors: [], resources: [] }

    const [isOpen, selectedResources, bookingDate, attendeeCount, bookingQuantity, startTime, endTime, bookingType, repeatUntil] = values
    if (!isOpen || !selectedResources.length || !bookingDate || !startTime || !endTime) return

    if (startTime >= endTime) {
      liveBookingValidation.value = {
        checking: false,
        valid: false,
        errors: ['End time must be after start time.'],
        resources: [],
      }
      return
    }

    if (bookingType === 'Recurring' && (!repeatUntil || repeatUntil < bookingDate)) {
      liveBookingValidation.value = {
        checking: false,
        valid: false,
        errors: ['Please select a valid repeat-until date.'],
        resources: [],
      }
      return
    }

    liveBookingValidation.value.checking = true
    liveValidationTimer = setTimeout(async () => {
      try {
        const result = await validateGroupBooking({
          resources: selectedResources,
          bookingDate,
          startTime: startTime.length === 5 ? `${startTime}:00` : startTime,
          endTime: endTime.length === 5 ? `${endTime}:00` : endTime,
          bookingType,
          repeatUntil: bookingType === 'Recurring' ? repeatUntil : null,
          attendeeCount,
          bookingQuantity,
        })
        if (requestId !== liveValidationRequestId) return
        liveBookingValidation.value = {
          checking: false,
          valid: Boolean(result?.valid),
          errors: result?.errors || [],
          resources: result?.resources || [],
        }
      } catch (error) {
        if (requestId !== liveValidationRequestId) return
        liveBookingValidation.value = {
          checking: false,
          valid: false,
          errors: [error.message || 'Could not validate this booking right now.'],
          resources: [],
        }
      }
    }, 350)
  },
)

async function submitManualBooking() {
  bookingError.value = ''
  bookingSuccess.value = ''

  const form = bookingForm.value

  if (!form.resources.length || !form.bookingDate || !form.startTime || !form.endTime) {
    bookingError.value = 'Select at least one resource and fill in all required fields.'
    return
  }

  if (form.startTime >= form.endTime) {
    bookingError.value = 'End time must be after start time.'
    return
  }

  if (
    form.bookingType === 'Recurring' &&
    (!form.repeatUntil || form.repeatUntil < form.bookingDate)
  ) {
    bookingError.value = 'Please select a valid repeat-until date.'
    return
  }

  if (liveBookingValidation.value.checking) {
    bookingError.value = 'Please wait while resource availability is checked.'
    return
  }

  if (!liveBookingValidation.value.valid) {
    bookingError.value = liveBookingValidation.value.errors.join(' ')
      || 'Please resolve the booking validation errors before submitting.'
    return
  }

  bookingSubmitting.value = true

  try {
    const result = await submitBooking({
      resources: form.resources,
      bookingDate: form.bookingDate,
      startTime: form.startTime.length === 5
        ? `${form.startTime}:00`
        : form.startTime,
      endTime: form.endTime.length === 5
        ? `${form.endTime}:00`
        : form.endTime,
      bookingType: form.bookingType,
      repeatUntil: form.bookingType === 'Recurring'
        ? form.repeatUntil
        : null,
      customer: form.customer.trim(),
      customerRecord: form.customerRecord || '',
      contact: form.contact || '',
      customerPhone: form.customerPhone.trim(),
      customerEmail: form.customerEmail.trim(),
      remarks: form.remarks.trim(),
      attendeeCount: form.attendeeCount,
      bookingQuantity: form.bookingQuantity,
    })

    bookingSuccess.value = form.resources.length > 1
      ? `Group booking created successfully (${result.count} resources). Reference: ${result.group_booking_id}`
      : 'Booking created successfully.'
    bookingFormOpen.value = false
    selectedBookingSlot.value = null
    await loadSchedule()
  } catch (error) {
    bookingError.value = error.message || 'Could not create booking.'
  } finally {
    bookingSubmitting.value = false
  }
}


const selectedBookingSlot = ref(null)



function selectSlot(resource, date, hour) {
  const bookingDate = dateKey(date)

  const daySchedule = (resourceSchedules.value[resource] || []).find(
    item => item.date === bookingDate
  )

  if (!daySchedule || daySchedule.is_blackout) {
    return
  }

  const hourStart = new Date(date)
  hourStart.setHours(hour, 0, 0, 0)

  const hourEnd = new Date(hourStart)
  hourEnd.setHours(hour + 1, 0, 0, 0)

  const intervals = (daySchedule.slots || [])
    .filter(slot =>
      slot.status === 'available' &&
      slot.start_time_user_datetime &&
      slot.end_time_user_datetime
    )
    .map(slot => ({
      start: new Date(slot.start_time_user_datetime).getTime(),
      end: new Date(slot.end_time_user_datetime).getTime(),
    }))
    .filter(slot =>
      slot.start < hourEnd.getTime() &&
      slot.end > hourStart.getTime()
    )
    .sort((a, b) => a.start - b.start)

  let coveredUntil = hourStart.getTime()

  for (const slot of intervals) {
    if (slot.start > coveredUntil) break
    coveredUntil = Math.max(coveredUntil, slot.end)
    if (coveredUntil >= hourEnd.getTime()) break
  }

  if (coveredUntil < hourEnd.getTime()) {
    return
  }

  selectedBookingSlot.value = {
    resource,
    bookingDate,
    startTime: `${String(hour).padStart(2, '0')}:00:00`,
    endTime: `${String(hour + 1).padStart(2, '0')}:00:00`,
  }

  openNewBooking()
}


</script>

<template>
  <div class="min-h-screen bg-slate-50 text-slate-800 md:flex">
    <aside class="z-10 flex w-full shrink-0 flex-col border-b border-slate-200 bg-white md:min-h-screen md:w-60 md:border-b-0 md:border-r">
      <div class="border-b border-slate-100 px-5 py-6">
        <div class="flex items-center gap-3">
          <div class="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-600 text-xl font-bold text-white">B</div>
          <div>
            <p class="text-base font-bold tracking-tight text-slate-900">Booking Diary</p>
            <p class="mt-0.5 text-xs text-slate-500">Resource management</p>
          </div>
        </div>
      </div>

      <nav class="flex gap-1 overflow-x-auto p-3 md:flex-1 md:flex-col">
        <p class="hidden px-3 pb-2 pt-3 text-[10px] font-bold uppercase tracking-[0.16em] text-slate-400 md:block">Workspace</p>
        <button
          v-for="item in navigation.filter(item => item.name !== 'Reports' || isBookingManager)"
          :key="item.name"
          @click="activeView = item.name; if (item.name === 'Bookings') loadBookingsPage(); if (item.name === 'Overview') loadOverview(); if (item.name === 'Reports') loadReports()"
          class="flex shrink-0 items-center gap-3 rounded-lg px-3 py-2.5 text-left text-sm font-medium transition"
          :class="activeView === item.name ? 'bg-indigo-50 text-indigo-700' : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'"
        >
          <span class="w-5 text-center text-lg">{{ item.icon }}</span>
          {{ item.name }}
        </button>
      </nav>

      <div class="m-4 hidden rounded-xl border border-slate-100 bg-slate-50 p-4 md:block">
        <div class="mb-2 flex items-center gap-2">
          <span class="h-2 w-2 rounded-full bg-amber-400"></span>
          <p class="text-xs font-semibold text-slate-700">Live booking data</p>
        </div>
        <p class="text-xs leading-5 text-slate-500">Calendar uses bookings from Frappe.</p>
      </div>
    </aside>

    <main class="min-w-0 flex-1">
      <header class="flex flex-wrap items-center justify-between gap-4 border-b border-slate-200 bg-white px-5 py-4 md:px-8">
        <div>
          <div class="text-xs text-slate-400">Workspace <span class="mx-1">/</span> <span class="text-slate-600">{{ activeView }}</span></div>
          <h1 class="font-bold tracking-tight text-slate-100">{{ activeView }}</h1>
        </div>
        <button @click="openNewBooking" class="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-indigo-700">
          <span class="text-lg leading-none">+</span> New Booking
        </button>
      </header>
      

<Teleport to="body">
  <div
    v-if="selectedBooking"
    class="fixed inset-0 z-[100] flex items-center justify-center bg-slate-950/50 p-4"
    @click.self="selectedBooking = null"
  >
    <div
      class="w-full max-w-lg rounded-2xl bg-white p-6 shadow-2xl"
      role="dialog"
      aria-modal="true"
      aria-labelledby="booking-details-title"
    >
      <div class="mb-6 flex items-center justify-between">
        <div>
          <p class="text-xs font-semibold uppercase tracking-wider text-indigo-600">
            Booking information
          </p>
          <h2
            id="booking-details-title"
            class="mt-1 text-xl font-bold text-slate-900"
          >
            Booking Details
          </h2>
        </div>

        <button
          type="button"
          @click="selectedBooking = null"
          aria-label="Close booking details"
          class="flex h-9 w-9 items-center justify-center rounded-full text-xl text-slate-500 hover:bg-slate-100"
        >
          ×
        </button>
        <button
  v-if="isBookingManager"
  type="button"
  @click="bookingEditMode = true"
  class="rounded-lg border border-indigo-200 px-5 py-2.5 text-sm font-semibold text-indigo-700 hover:bg-indigo-50"
>
  Edit Booking
</button>
      </div>

      <p v-if="bookingCancelError" class="mb-3 rounded-lg bg-rose-50 p-3 text-sm text-rose-700">{{ bookingCancelError }}</p>
      <p v-if="bookingCancelSuccess" class="mb-3 rounded-lg bg-emerald-50 p-3 text-sm text-emerald-700">{{ bookingCancelSuccess }}</p>
      <div class="space-y-4 text-sm">
        <div class="rounded-lg bg-slate-50 p-3">
          <p class="text-xs text-slate-500">Booking ID</p>
          <p class="mt-1 font-semibold text-slate-900">
            {{ selectedBooking.id }}
          </p>
        </div>

        <div class="grid grid-cols-2 gap-4">
          <div>
            <p class="text-slate-500">Resource</p>
            <select v-if="bookingEditMode && isBookingManager" v-model="selectedBooking.resource" class="mt-1 w-full rounded-lg border border-slate-300 p-2 text-sm"><option v-for="resource in resources" :key="resource.name" :value="resource.name">{{ resource.resource_name || resource.name }}</option></select><p v-else class="mt-1 font-medium text-slate-900">{{ selectedBooking.resourceLabel || selectedBooking.resource }}</p>
          </div>

          <div>
            <p class="text-slate-500">Status</p>
            <select v-if="bookingEditMode && isBookingManager" v-model="selectedBooking.status" class="mt-1 w-full rounded-lg border border-slate-300 p-2 text-sm"><option>Pending</option><option>Confirmed</option><option>Cancelled</option></select><p v-else class="mt-1 font-medium text-slate-900">{{ selectedBooking.status }}</p>
          </div>

          <div>
            <p class="text-slate-500">Date</p>
            <input v-if="bookingEditMode && isBookingManager" v-model="selectedBooking.date" type="date" class="mt-1 w-full rounded-lg border border-slate-300 p-2 text-sm" /><p v-else class="mt-1 font-medium text-slate-900">{{ selectedBooking.date }}</p>
          </div>

          <div>
            <p class="text-slate-500">Time</p>
            <div v-if="bookingEditMode && isBookingManager" class="mt-1 flex gap-2"><input v-model="selectedBooking.start" type="time" class="min-w-0 w-full rounded-lg border border-slate-300 p-2 text-sm" /><input v-model="selectedBooking.end" type="time" class="min-w-0 w-full rounded-lg border border-slate-300 p-2 text-sm" /></div><p v-else class="mt-1 font-medium text-slate-900">{{ timeLabel(selectedBooking.start) }} – {{ timeLabel(selectedBooking.end) }}</p>
          </div>

          <div class="col-span-2">
            <p class="text-slate-500">Customer</p>
            <p class="mt-1 font-medium text-slate-900">
              {{ selectedBooking.title }}
            </p>
          </div>
          <div class="col-span-2">
  <p class="text-slate-500">Booking Type</p>
  <p class="mt-1 font-medium text-slate-900">
    {{ selectedBooking.booking_type || '—' }}
  </p>
</div>


<div class="col-span-2">
  <p class="text-slate-500">Remarks</p>
  <textarea
    v-if="bookingEditMode"
    v-model="selectedBooking.remarks"
    rows="3"
    class="mt-1 w-full rounded-lg border border-slate-300 p-2 text-sm text-slate-900"
    placeholder="Add remarks"
  ></textarea>
  <p v-else class="mt-1 whitespace-pre-wrap font-medium text-slate-900">
    {{ selectedBooking.remarks || '—' }}
  </p>
</div>

        </div>
      </div>

 
<div class="mt-7 flex justify-end gap-3">
  <button
    v-if="bookingEditMode"
    type="button"
    @click="bookingEditMode = false"
    class="rounded-lg border border-slate-300 px-5 py-2.5 text-sm font-semibold text-slate-700 hover:bg-slate-50"
  >
    Cancel
  </button>

  <button
    v-else
    type="button"
    @click="selectedBooking = null"
    class="rounded-lg border border-slate-300 px-5 py-2.5 text-sm font-semibold text-slate-700 hover:bg-slate-50"
  >
    Close
  </button>

  <button
    v-if="canCancelSelectedBooking && !bookingEditMode"
    type="button"
    @click="cancelSelectedBooking"
    :disabled="bookingCancelling"
    class="rounded-lg border border-rose-200 bg-rose-50 px-5 py-2.5 text-sm font-semibold text-rose-700 hover:bg-rose-100 disabled:opacity-50"
  >
    {{ bookingCancelling ? 'Cancelling…' : 'Cancel booking' }}
  </button>
  <button
    v-if="bookingEditMode"
    type="button"
    @click="saveBookingChanges"
    :disabled="bookingUpdating"
    class="rounded-lg bg-indigo-600 px-5 py-2.5 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-50"
  >
    {{ bookingUpdating ? 'Saving...' : 'Save Changes' }}
  </button>
</div>

    </div>
  </div>
</Teleport>


<Teleport to="body">
  <div
    v-if="bookingFormOpen"
    class="fixed inset-0 z-[100] flex items-center justify-center bg-slate-950/50 p-4"
    @click.self="bookingFormOpen = false"
  >
    <div
      class="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-2xl bg-white p-6 shadow-2xl"
      role="dialog"
      aria-modal="true"
      aria-labelledby="new-booking-title"
    >

  <div class="mb-6 flex items-center justify-between border-b border-slate-100 pb-4">
    <div class="flex items-center gap-3">
      <span class="flex h-11 w-11 items-center justify-center rounded-xl bg-indigo-600 text-xl font-semibold text-white shadow-sm shadow-indigo-200" aria-hidden="true">＋</span>
      <div>
        <p class="text-xs font-semibold uppercase tracking-[0.16em] text-indigo-600">Booking Diary</p>
        <h2 id="new-booking-title" class="mt-0.5 text-xl font-bold tracking-tight text-slate-900">New Booking</h2>
      </div>
    </div>
    <button
      type="button"
      @click="bookingFormOpen = false"
      class="rounded-lg px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-100"
    >
      Cancel
    </button>
  </div>

  <div class="grid grid-cols-1 gap-4 md:grid-cols-2">
    <fieldset class="rounded-xl border border-slate-200 p-3 md:col-span-2">
      <legend class="px-1 text-sm font-semibold text-slate-700">
        Resources to book *
      </legend>
      <p class="mb-3 text-xs text-slate-500">
        Select one or more resources. All will be booked for the same date and time.
      </p>
      <label class="mb-3 block text-sm font-medium text-slate-700">
        Filter by category
        <select v-model="bookingResourceCategoryFilter" class="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 sm:max-w-xs">
          <option>All categories</option>
          <option v-for="category in bookingResourceCategories" :key="category" :value="category">{{ category }}</option>
        </select>
      </label>
      <div class="grid grid-cols-1 gap-2 sm:grid-cols-2">
        <label
          v-for="resource in filteredBookingResources"
          :key="resource.name"
          class="flex cursor-pointer items-center gap-3 rounded-lg border border-slate-200 px-3 py-2.5 text-sm hover:bg-slate-50"
          :class="bookingForm.resources.includes(resource.name) ? 'border-indigo-300 bg-indigo-50' : 'bg-white'"
        >
          <input
            v-model="bookingForm.resources"
            type="checkbox"
            :value="resource.name"
            :disabled="resource.available === 0 || resource.available === false"
            class="h-4 w-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
          />
          <span class="min-w-0 flex-1">
            <span class="block font-medium text-slate-800">
              {{ resource.resource_name || resource.name }}
            </span>
            <span class="block text-xs text-slate-500">
              {{ resource.resource_category || 'Other' }} · {{ resource.resource_type || 'Resource' }}
              <span v-if="resource.available === 0 || resource.available === false"> · Unavailable</span>
            </span>
            <span class="mt-1 inline-flex rounded-full px-2 py-0.5 text-[11px] font-semibold"
              :class="(resource.capacity_mode || 'Exclusive') === 'Shared Pool' ? 'bg-emerald-100 text-emerald-800' : (resource.capacity_mode === 'Per Booking' ? 'bg-amber-100 text-amber-800' : 'bg-slate-200 text-slate-700')">
              {{ resource.capacity_mode || 'Exclusive' }}
            </span>
          </span>
        </label>
      </div>
      <p class="mt-3 text-xs font-medium text-slate-600">
        Selected: {{ bookingForm.resources.length }} resource(s)
      </p>
      <div v-if="selectedBookingResources.length" class="mt-3 space-y-2">
        <div v-for="resource in selectedBookingResources" :key="'capacity-' + resource.name" class="rounded-lg border border-slate-200 bg-white p-3">
          <div class="flex flex-wrap items-center gap-2">
            <p class="text-sm font-semibold text-slate-800">{{ resource.resource_name || resource.name }}</p>
            <span class="rounded-full px-2 py-0.5 text-xs font-semibold"
              :class="(resource.capacity_mode || 'Exclusive') === 'Shared Pool' ? 'bg-emerald-100 text-emerald-800' : (resource.capacity_mode === 'Per Booking' ? 'bg-amber-100 text-amber-800' : 'bg-slate-200 text-slate-700')">
              {{ resource.capacity_mode || 'Exclusive' }}
            </span>
          </div>
          <p class="mt-1 text-xs text-slate-600">{{ capacityModeDescription(resource.capacity_mode || 'Exclusive') }}</p>
          <p v-if="resource.capacity_mode === 'Shared Pool'" class="mt-1 text-xs text-slate-600">
            Total pool capacity: {{ resource.capacity || 1 }} unit(s). Remaining capacity is checked when validating the booking.
          </p>
          <p v-else-if="resource.capacity_mode === 'Per Booking'" class="mt-1 text-xs text-slate-600">
            Maximum attendees per booking: {{ resource.capacity || 1 }}.
          </p>
        </div>
      </div>
      <div class="mt-4 rounded-lg border border-slate-200 bg-slate-50 p-3">
        <div class="flex flex-wrap items-center justify-between gap-2">
          <h3 class="text-sm font-semibold text-slate-800">Availability for selected date</h3>
          <span class="text-xs text-slate-500">{{ bookingForm.bookingDate || 'Choose a date' }}</span>
        </div>
        <p v-if="formAvailability.loading" class="mt-3 text-sm text-slate-500">Loading availability…</p>
        <p v-else-if="formAvailability.error" class="mt-3 text-sm text-rose-700">{{ formAvailability.error }}</p>
        <p v-else-if="!bookingForm.resources.length" class="mt-3 text-sm text-slate-500">Select a resource to see its available and booked slots.</p>
        <div v-else-if="!formAvailability.schedules.length" class="mt-3 text-sm text-slate-500">No schedule information is available for this selection.</div>
        <div v-else class="mt-3 space-y-3">
          <div v-for="day in formAvailability.schedules" :key="day.resource + '-' + day.date" class="rounded-lg border border-slate-200 bg-white p-3">
            <div class="flex flex-wrap items-center justify-between gap-2">
              <p class="text-sm font-semibold text-slate-800">{{ resources.find(r => r.name === day.resource)?.resource_name || day.resource }}</p>
              <span class="text-xs text-slate-500">{{ day.date }}</span>
            </div>
            <p v-if="day.is_blackout" class="mt-2 rounded-md bg-rose-50 px-2.5 py-2 text-sm text-rose-700">
              Blocked for this date<span v-if="day.blackout_reason">: {{ day.blackout_reason }}</span>
            </p>
            <p v-else-if="!day.slots?.length" class="mt-2 text-sm text-slate-500">No configured available slots.</p>
            <div v-else class="mt-2 flex flex-wrap gap-2">
              <button
                v-for="slot in day.slots"
                :key="day.resource + '-' + day.date + '-' + slot.start_time"
                type="button"
                @click="bookingForm.startTime = slot.start_time; bookingForm.endTime = slot.end_time"
                :disabled="slot.status !== 'available' || bookingForm.resources.length !== 1"
                :title="bookingForm.resources.length > 1 ? 'Choose one resource to select a slot' : slot.status === 'available' ? 'Use this slot' : 'Already booked'"
                class="rounded-md border px-2.5 py-1.5 text-xs font-semibold disabled:cursor-not-allowed"
                :class="slot.status === 'available' ? (bookingForm.startTime === slot.start_time && bookingForm.endTime === slot.end_time ? 'border-emerald-600 bg-emerald-600 text-white' : 'border-emerald-200 bg-emerald-50 text-emerald-800 hover:bg-emerald-100') : 'border-rose-200 bg-rose-50 text-rose-700 opacity-80'"
              >
                {{ slot.start_time?.slice(0, 5) }}–{{ slot.end_time?.slice(0, 5) }} · {{ slot.status === 'available' ? 'Free' : 'Booked' }}
              </button>
            </div>
            <p v-if="bookingForm.resources.length > 1" class="mt-2 text-xs text-slate-500">Select one resource to apply a slot directly; group bookings are validated across all selected resources.</p>
          </div>
        </div>
      </div>
    </fieldset>

    <label class="block text-sm font-medium text-slate-700">
      Booking date *
      <input
        v-model="bookingForm.bookingDate"
        type="date"
        required
        class="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2"
      />
    </label>

    <label class="block text-sm font-medium text-slate-700">
      Start time *
      <input
        v-model="bookingForm.startTime"
        type="time"
        required
        class="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2"
      />
    </label>

    <label class="block text-sm font-medium text-slate-700">
      End time *
      <input
        v-model="bookingForm.endTime"
        type="time"
        required
        class="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2"
      />
    </label>

    

    <label class="block text-sm font-medium text-slate-700">
      Booking type *
      <select
        v-model="bookingForm.bookingType"
        class="mt-1 block w-full rounded-lg border border-slate-300 bg-white px-3 py-2"
      >
        <option value="Single Slot">Single Slot</option>
        <option value="Recurring">Recurring</option>
      </select>
    </label>

    <label
      v-if="bookingForm.bookingType === 'Recurring'"
      class="block text-sm font-medium text-slate-700"
    >
      Repeat until *
      <input
        v-model="bookingForm.repeatUntil"
        type="date"
        required
        :min="bookingForm.bookingDate"
        class="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2"
      />
    </label>

    <label class="block text-sm font-medium text-slate-700">
      Attendees
      <input v-model.number="bookingForm.attendeeCount" type="number" min="1" required class="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2" />
    </label>

    <label v-if="selectedResourcesAreSharedPool" class="block text-sm font-medium text-slate-700">
      Shared-pool units
      <input v-model.number="bookingForm.bookingQuantity" type="number" min="1" :max="Math.min(...selectedBookingResources.map(resource => Number(resource.capacity) || 1))" required class="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2" />
      <span class="mt-1 block text-xs font-normal text-slate-500">Number of units requested from the selected shared pool(s). Live validation checks current availability.</span>
    </label>
    <div v-else class="rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm text-slate-600">
      Shared-pool units are not applicable to this selection. The booking quantity is kept at 1.
      <span v-if="selectedCapacityModes.length > 1"> Mixed capacity modes are selected, so shared-pool quantity cannot be applied consistently to every resource.</span>
    </div>

    <label class="block text-sm font-medium text-slate-700 md:col-span-2">
      Customer name
      <input
        v-model="bookingForm.customer"
        type="text"
        maxlength="140"
        placeholder="Optional"
        class="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2"
      />
    </label>

    <label class="block text-sm font-medium text-slate-700">
      Link Customer record
      <select v-model="bookingForm.customerRecord" class="mt-1 block w-full rounded-lg border border-slate-300 bg-white px-3 py-2">
        <option value="">No linked customer</option>
        <option v-for="customer in customerOptions.customers" :key="customer.name" :value="customer.name">{{ customer.customer_name || customer.name }}</option>
      </select>
    </label>

    <label class="block text-sm font-medium text-slate-700">
      Contact
      <select v-model="bookingForm.contact" class="mt-1 block w-full rounded-lg border border-slate-300 bg-white px-3 py-2">
        <option value="">No linked contact</option>
        <option v-for="contact in customerOptions.contacts" :key="contact.name" :value="contact.name">{{ [contact.first_name, contact.last_name].filter(Boolean).join(' ') || contact.name }}{{ contact.email_id ? ' — ' + contact.email_id : '' }}</option>
      </select>
    </label>

    <label class="block text-sm font-medium text-slate-700">
      Phone
      <input v-model="bookingForm.customerPhone" type="tel" maxlength="40" placeholder="Walk-in phone number" class="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2" />
    </label>

    <label class="block text-sm font-medium text-slate-700">
      Email
      <input v-model="bookingForm.customerEmail" type="email" maxlength="140" placeholder="Walk-in email address" class="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2" />
    </label>

    <label class="block text-sm font-medium text-slate-700 md:col-span-2">
      Remarks
      <textarea
        v-model="bookingForm.remarks"
        rows="3"
        placeholder="Optional notes"
        class="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2"
      ></textarea>
    </label>
  </div>

  <div
    v-if="liveBookingValidation.checking"
    class="mt-4 flex items-center gap-2 rounded-lg border border-sky-200 bg-sky-50 px-3 py-2.5 text-sm text-sky-800"
    role="status"
  >
    <span class="h-2 w-2 animate-pulse rounded-full bg-sky-500"></span>
    Checking resource availability…
  </div>

  <div
    v-else-if="liveBookingValidation.errors.length"
    class="mt-4 rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800"
    role="alert"
  >
    <p class="font-semibold">Please fix the following:</p>
    <ul class="mt-1 list-disc space-y-1 pl-5">
      <li v-for="(error, index) in liveBookingValidation.errors" :key="index">
        {{ error }}
      </li>
    </ul>
  </div>

  <div
    v-else-if="liveBookingValidation.valid"
    class="mt-4 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2.5 text-sm text-emerald-800"
    role="status"
  >
    <span class="font-semibold">Availability check passed.</span>
    All selected resources passed validation. The server will check again when submitted.
  </div>

  <p class="mt-3 text-xs text-slate-500">
    Availability is checked as you edit the form and verified again when you submit.
  </p>

  <div class="mt-5 flex justify-end gap-3">
    <button
      type="button"
      @click="bookingFormOpen = false"
      class="rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700"
    >
      Cancel
    </button>
    <button
      type="button"
      @click="submitManualBooking"
      :disabled="bookingSubmitting || liveBookingValidation.checking || !liveBookingValidation.valid"
      class="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
    >
      {{ bookingSubmitting ? 'Submitting…' : liveBookingValidation.checking ? 'Checking availability…' : 'Submit booking' }}
    </button>
  </div>
</div>
</div>
</Teleport>

<Teleport to="body">
  <div
    v-if="resourceFormOpen"
    class="fixed inset-0 z-[110] flex items-center justify-center bg-slate-950/50 p-4"
    @click.self="resourceFormOpen = false"
  >
    <form
      class="max-h-[90vh] w-full max-w-xl overflow-y-auto rounded-2xl bg-white p-6 shadow-2xl"
      role="dialog"
      aria-modal="true"
      @submit.prevent="saveResource"
    >
      <div class="mb-6 flex items-center justify-between border-b border-slate-100 pb-4">
        <div class="flex items-center gap-3">
          <span class="flex h-11 w-11 items-center justify-center rounded-xl bg-indigo-600 text-lg text-white shadow-sm shadow-indigo-200" aria-hidden="true">▦</span>
          <div>
            <p class="text-xs font-semibold uppercase tracking-[0.16em] text-indigo-600">Booking Diary</p>
            <h2 class="mt-0.5 text-xl font-bold tracking-tight text-slate-900">
              {{ resourceEditMode ? 'Edit Resource' : 'Create Resource' }}
            </h2>
          </div>
        </div>
        <button
          type="button"
          @click="resourceFormOpen = false"
          class="rounded-lg px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-100"
        >
          Cancel
        </button>
      </div>

      <div class="grid grid-cols-1 gap-4 md:grid-cols-2">
        <label class="text-sm font-medium text-slate-700">
          Resource Name *
          <input
            v-model="resourceForm.resource_name"
            required
            maxlength="140"
            class="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2"
          />
        </label>

        <label class="text-sm font-medium text-slate-700">
          Resource Type *
          <input
            v-model="resourceForm.resource_type"
            required
            maxlength="140"
            placeholder="e.g. Outdoor garden, MC, chef, DJ, face painter"
            class="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2"
          />
        </label>

        <label class="text-sm font-medium text-slate-700">
          Category *
          <select v-model="resourceForm.resource_category" required class="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2">
            <option>Venue</option>
            <option>Staff</option>
            <option>Equipment</option>
            <option>Facility</option>
            <option>Other</option>
          </select>
        </label>

<label class="text-sm font-medium text-slate-700 md:col-span-2">
          Description
          <textarea
            v-model="resourceForm.description"
            rows="3"
            class="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2"
          ></textarea>
        </label>

        <label class="text-sm font-medium text-slate-700">
          Capacity Mode *
          <select v-model="resourceForm.capacity_mode" required class="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2">
            <option value="Exclusive">Exclusive (one booking at a time)</option>
            <option value="Per Booking">People per booking</option>
            <option value="Shared Pool">Shared pool (multiple bookings)</option>
          </select>
        </label>

        <label class="text-sm font-medium text-slate-700">
          {{ resourceForm.capacity_mode === 'Per Booking' ? 'Maximum people per booking' : resourceForm.capacity_mode === 'Shared Pool' ? 'Total pool capacity' : 'Capacity' }}
          <input v-model.number="resourceForm.capacity" type="number" min="1" required :disabled="resourceForm.capacity_mode === 'Exclusive'" class="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 disabled:bg-slate-100" />
        </label>

        <label class="text-sm font-medium text-slate-700">
          Booking duration (minutes) *
          <input v-model.number="resourceForm.default_booking_duration" type="number" min="1" required class="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2" />
        </label>

        <label class="text-sm font-medium text-slate-700">
          Buffer before (minutes)
          <input v-model.number="resourceForm.buffer_before_minutes" type="number" min="0" class="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2" />
        </label>

        <label class="text-sm font-medium text-slate-700">
          Buffer after (minutes)
          <input v-model.number="resourceForm.buffer_after_minutes" type="number" min="0" class="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2" />
        </label>

        <label class="text-sm font-medium text-slate-700">
          Minimum advance (hours)
          <input v-model.number="resourceForm.minimum_advance_hours" type="number" min="0" class="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2" />
        </label>

        <label class="text-sm font-medium text-slate-700">
          Maximum advance (days)
          <input v-model.number="resourceForm.maximum_advance_days" type="number" min="0" class="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2" />
        </label>

        <label class="text-sm font-medium text-slate-700">
          Cancellation cutoff (hours)
          <input v-model.number="resourceForm.cancellation_cutoff_hours" type="number" min="0" class="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2" />
        </label>

        <label class="text-sm font-medium text-slate-700 md:col-span-2">
          Time Zone *
          <input
            v-model="resourceForm.time_zone"
            required
            placeholder="Asia/Kolkata"
            class="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2"
          />
          <span class="mt-1 block text-xs text-slate-500">
            Use an IANA timezone, such as Asia/Kolkata or America/New_York.
          </span>
        </label>

        <label class="flex items-center gap-2 text-sm text-slate-700 md:col-span-2">
          <input
            v-model="resourceForm.available"
            type="checkbox"
            class="h-4 w-4 rounded border-slate-300"
          />
          Resource is available for booking
        </label>
      </div>

      <p v-if="resourceFormError" class="mt-4 text-sm text-red-600">
        {{ resourceFormError }}
      </p>

      <div class="mt-6 flex justify-end gap-3">
        <button
          type="button"
          @click="resourceFormOpen = false"
          class="rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700"
        >
          Cancel
        </button>
        <button
          type="submit"
          :disabled="resourceSaving"
          class="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
        >
          {{ resourceSaving ? 'Saving…' : 'Save Resource' }}
        </button>
      </div>
    </form>
  </div>
</Teleport>

<Teleport to="body">
  <div
    v-if="availabilityModalOpen"
    class="fixed inset-0 z-[100] flex items-center justify-center bg-slate-950/50 p-4"
    @click.self="availabilityModalOpen = false"
  >
    <form
      class="max-h-[90vh] w-full max-w-3xl overflow-y-auto rounded-2xl bg-white p-6 shadow-2xl"
      role="dialog"
      aria-modal="true"
      @submit.prevent="saveResourceAvailability"
    >
      <div class="mb-6 flex items-center justify-between border-b border-slate-100 pb-4">
        <div class="flex items-center gap-3">
          <span class="flex h-11 w-11 items-center justify-center rounded-xl bg-emerald-600 text-lg text-white shadow-sm shadow-emerald-200" aria-hidden="true">◷</span>
          <div>
            <p class="text-xs font-semibold uppercase tracking-[0.16em] text-emerald-700">Resource settings</p>
            <h2 class="mt-0.5 text-xl font-bold tracking-tight text-slate-900">
              Resource Availability
            </h2>
          <p class="mt-1 text-sm text-slate-500">
            {{ availabilityResource?.resource_name || availabilityResource?.name }}
          </p>
        </div>
        </div>
        <button
          type="button"
          @click="availabilityModalOpen = false"
          class="rounded-lg px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-100"
        >
          Close
        </button>
      </div>

      <p v-if="availabilityLoading" class="py-6 text-center text-slate-500">
        Loading availability…
      </p>

      <div v-else>
        <p class="mb-4 text-sm text-slate-600">
          Set the working hours for each day. Uncheck a day when the resource
          is unavailable.
        </p>

        <div class="overflow-x-auto">
          <table class="w-full text-left text-sm">
            <thead class="bg-slate-50 text-slate-600">
              <tr>
                <th class="px-3 py-3">Day</th>
                <th class="px-3 py-3">Available</th>
                <th class="px-3 py-3">Start time</th>
                <th class="px-3 py-3">End time</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="(day, index) in availabilityForm.weekly_schedule"
                :key="day.day_of_week"
                class="border-t border-slate-100"
              >
                <td class="px-3 py-3 font-medium text-slate-800">
                  {{ day.day_of_week }}
                </td>
                <td class="px-3 py-3">
                  <input
                    v-model="day.available"
                    type="checkbox"
                    class="h-4 w-4 rounded border-slate-300"
                  />
                </td>
                <td class="px-3 py-3">
                  <input
                    v-model="day.start_time"
                    type="time"
                    :disabled="!day.available"
                    class="rounded-lg border border-slate-300 px-2 py-2 disabled:bg-slate-100"
                  />
                </td>
                <td class="px-3 py-3">
                  <input
                    v-model="day.end_time"
                    type="time"
                    :disabled="!day.available"
                    class="rounded-lg border border-slate-300 px-2 py-2 disabled:bg-slate-100"
                  />
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <p v-if="availabilityError" class="mt-4 text-sm text-red-600">
          {{ availabilityError }}
        </p>

        <div class="mt-6 flex justify-end gap-3">
          <button
            type="button"
            @click="availabilityModalOpen = false"
            class="rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700"
          >
            Cancel
          </button>
          <button
            type="submit"
            :disabled="availabilitySaving || availabilityLoading"
            class="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
          >
            {{ availabilitySaving ? 'Saving…' : 'Save Availability' }}
          </button>
        </div>
      </div>
    </form>
  </div>
</Teleport>

<div
  v-if="selectedBooking"
  class="mx-5 mt-4 rounded-xl border border-slate-200 bg-white p-5 md:mx-8"
>
  <div class="mb-5 flex items-center justify-between border-b border-slate-100 pb-4">
    <div class="flex items-center gap-3">
      <span class="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-50 text-lg text-indigo-700" aria-hidden="true">▤</span>
      <div>
        <p class="text-xs font-semibold uppercase tracking-[0.16em] text-indigo-600">Booking Diary</p>
        <h2 class="mt-0.5 text-lg font-bold tracking-tight text-slate-900">Booking Details</h2>
      </div>
    </div>
    <button
      type="button"
      @click="selectedBooking = null"
      class="rounded-lg px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-100"
    >
      Close
    </button>
  </div>

  <div class="grid grid-cols-1 gap-4 text-sm md:grid-cols-2">
    <p><span class="font-semibold">Booking ID:</span> {{ selectedBooking.id }}</p>
    <p><span class="font-semibold">Resource:</span> {{ selectedBooking.resourceLabel || selectedBooking.resource }}</p>
    <p><span class="font-semibold">Date:</span> {{ selectedBooking.date }}</p>
    <p><span class="font-semibold">Time:</span> {{ timeLabel(selectedBooking.start) }} – {{ timeLabel(selectedBooking.end) }}</p>
    <p><span class="font-semibold">Customer:</span> {{ selectedBooking.title }}</p>
    <p><span class="font-semibold">Status:</span> {{ selectedBooking.status }}</p>
  </div>

  <div class="mt-5 flex flex-wrap gap-2">
    <button
      v-if="['Pending', 'Confirmed'].includes(selectedBooking.status) && (selectedBooking.customer_user === currentUser || isBookingManager)"
      type="button"
      @click="openRescheduleForm"
      class="rounded-lg border border-indigo-200 bg-indigo-50 px-3 py-2 text-sm font-semibold text-indigo-700 hover:bg-indigo-100"
    >Reschedule booking</button>
  </div>

  <form v-if="rescheduleOpen" class="mt-4 grid grid-cols-1 gap-3 rounded-xl border border-indigo-100 bg-indigo-50/40 p-4 md:grid-cols-2" @submit.prevent="saveReschedule">
    <label class="text-sm font-medium text-slate-700 md:col-span-2">
      Resource
      <select v-model="rescheduleForm.resource" required class="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2">
        <option v-for="resource in resources.filter(r => r.available === 1 || r.available === true)" :key="resource.name" :value="resource.name">{{ resource.resource_name || resource.name }}</option>
      </select>
    </label>
    <label class="text-sm font-medium text-slate-700">
      New date
      <input v-model="rescheduleForm.bookingDate" type="date" required class="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2" />
    </label>
    <label class="text-sm font-medium text-slate-700">
      Start time
      <input v-model="rescheduleForm.startTime" type="time" required class="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2" />
    </label>
    <label class="text-sm font-medium text-slate-700">
      End time
      <input v-model="rescheduleForm.endTime" type="time" required class="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2" />
    </label>
    <p v-if="rescheduleError" class="rounded-lg bg-rose-50 p-3 text-sm text-rose-700 md:col-span-2">{{ rescheduleError }}</p>
    <div class="flex justify-end gap-2 md:col-span-2">
      <button type="button" @click="rescheduleOpen = false" class="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-semibold text-slate-700">Cancel</button>
      <button type="submit" :disabled="rescheduleSaving" class="rounded-lg bg-indigo-600 px-3 py-2 text-sm font-semibold text-white disabled:opacity-50">{{ rescheduleSaving ? 'Saving…' : 'Save new time' }}</button>
    </div>
  </form>
</div>

      <div v-if="activeView === 'Overview'" class="space-y-6 p-4 md:p-8">
        <div class="flex flex-wrap items-end justify-between gap-3">
          <div><h2 class="text-2xl font-bold tracking-tight text-slate-900">{{ isBookingManager ? 'Booking Operations' : 'My Booking Overview' }}</h2><p class="mt-1 text-sm text-slate-500">{{ isBookingManager ? 'Review all bookings and resolve pending confirmations.' : 'Your bookings, statuses, and upcoming schedule.' }}</p></div>
          <button type="button" @click="loadOverview" class="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50">Refresh</button>
        </div>
        <p v-if="overviewError" class="rounded-lg bg-rose-50 p-3 text-sm text-rose-700">{{ overviewError }}</p>
        <div class="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <div class="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"><p class="text-sm text-slate-500">{{ isBookingManager ? "Today's bookings (all users)" : "My bookings today" }}</p><p class="mt-2 text-3xl font-bold text-slate-900">{{ overviewTodayBookings.length }}</p></div>
          <div class="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"><p class="text-sm text-slate-500">{{ isBookingManager ? 'Pending confirmations' : 'My pending bookings' }}</p><p class="mt-2 text-3xl font-bold text-amber-600">{{ overviewRecords.filter(b => b.status === 'Pending').length }}</p></div>
          <div class="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"><p class="text-sm text-slate-500">Upcoming confirmed</p><p class="mt-2 text-3xl font-bold text-indigo-700">{{ overviewConfirmedCount }}</p></div>
          <div class="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"><p class="text-sm text-slate-500">{{ isBookingManager ? 'Available resources' : 'My total bookings' }}</p><p class="mt-2 text-3xl font-bold text-emerald-700">{{ isBookingManager ? resources.filter(r => r.available === 1 || r.available === true).length : overviewRecords.length }}</p></div>
        </div>
        <div v-if="overviewLoading" class="rounded-xl border border-slate-200 bg-white p-8 text-center text-sm text-slate-500">Loading overview…</div>
        <div v-else class="grid gap-6 xl:grid-cols-2">
          <section class="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
            <div class="flex items-center justify-between border-b border-slate-100 p-5"><div><h3 class="font-bold text-slate-900">{{ isBookingManager ? 'Needs confirmation' : 'My pending bookings' }}</h3><p class="mt-1 text-xs text-slate-500">{{ isBookingManager ? 'Confirm or reject requests.' : 'Waiting for a decision.' }}</p></div><span class="rounded-full bg-amber-50 px-2.5 py-1 text-xs font-semibold text-amber-800">{{ overviewRecords.filter(b => b.status === 'Pending').length }}</span></div>
            <div v-if="!overviewPending.length" class="p-6 text-sm text-slate-500">No pending bookings.</div>
            <div v-for="booking in overviewPending" :key="booking.name" class="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 p-4 last:border-b-0">
              <button type="button" @click="openBooking({ id: booking.booking_id || booking.name, docName: booking.name, title: booking.customer || 'Booking', resource: booking.resource, date: booking.booking_date, start: booking.start_time, end: booking.end_time, status: booking.status })" class="min-w-0 text-left"><span class="block font-semibold text-slate-800">{{ booking.customer || booking.booking_id || booking.name }}</span><span class="mt-1 block text-xs text-slate-500">{{ booking.resource }} · {{ booking.booking_date }} · {{ booking.start_time }}–{{ booking.end_time }}</span></button>
              <div v-if="isBookingManager" class="flex gap-2"><button type="button" @click="setBookingDecision(booking, 'Confirmed')" class="rounded-lg bg-emerald-600 px-3 py-2 text-xs font-semibold text-white hover:bg-emerald-700">Confirm</button><button type="button" @click="setBookingDecision(booking, 'Cancelled')" class="rounded-lg border border-rose-200 px-3 py-2 text-xs font-semibold text-rose-700 hover:bg-rose-50">Reject</button></div><span v-else class="rounded-full bg-amber-50 px-2.5 py-1 text-xs font-semibold text-amber-800">Pending</span>
            </div>
          </section>
          <section class="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
            <div class="border-b border-slate-100 p-5"><h3 class="font-bold text-slate-900">{{ isBookingManager ? 'Upcoming bookings' : 'My upcoming bookings' }}</h3><p class="mt-1 text-xs text-slate-500">Pending and confirmed bookings from today onward.</p></div>
            <div v-if="!overviewUpcoming.length" class="p-6 text-sm text-slate-500">No upcoming bookings found.</div>
            <button v-for="booking in overviewUpcoming" :key="booking.name" type="button" @click="openBooking({ id: booking.booking_id || booking.name, docName: booking.name, title: booking.customer || 'Booking', resource: booking.resource, date: booking.booking_date, start: booking.start_time, end: booking.end_time, status: booking.status })" class="flex w-full flex-wrap items-center justify-between gap-3 border-b border-slate-100 p-4 text-left last:border-b-0 hover:bg-slate-50"><span><span class="block font-semibold text-slate-800">{{ booking.customer || booking.booking_id || booking.name }}</span><span class="mt-1 block text-xs text-slate-500">{{ booking.resource }} · {{ booking.booking_date }} · {{ booking.start_time }}–{{ booking.end_time }}</span></span><span class="rounded-full px-2.5 py-1 text-xs font-semibold" :class="booking.status === 'Confirmed' ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-800'">{{ booking.status }}</span></button>
          </section>
        </div>
      </div>

      <div v-else-if="activeView === 'Resource Desk'" class="p-4 md:p-8">
        <div class="mb-5 flex flex-wrap items-end justify-between gap-4">
          <div>
            <h2 class="text-2xl font-bold tracking-tight text-slate-900">Resource calendar</h2>
            <p class="mt-1 text-sm text-slate-500">View availability and manage bookings across your resources.</p>
          </div>
          <div class="flex items-center gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs font-medium text-amber-800">
            <span class="h-2 w-2 rounded-full bg-amber-500"></span>
            BOOK NOW
          </div>
        </div>

        <section class="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
          <div class="flex flex-col gap-4 border-b border-slate-200 p-4 lg:flex-row lg:items-center lg:justify-between">
            <div class="inline-flex w-fit rounded-lg bg-slate-100 p-1">
              <button
                v-for="view in ['Month', 'Week', 'Day', 'Timeline']"
                :key="view"
                @click="chooseView(view)"
                class="rounded-md px-3 py-2 text-sm font-semibold transition"
                :class="calendarView === view ? 'bg-white text-indigo-700 shadow-sm' : 'text-slate-500 hover:text-slate-800'"
              >{{ view }}</button>
            </div>

            <div class="flex flex-wrap items-center gap-2">
              <div class="flex items-center rounded-lg border border-slate-200">
                <button @click="navigate(-1)" aria-label="Previous period" class="px-3 py-2 text-lg text-slate-600 hover:bg-slate-50">‹</button>
                <button @click="goToday" class="border-x border-slate-200 px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50">Today</button>
                <button @click="navigate(1)" aria-label="Next period" class="px-3 py-2 text-lg text-slate-600 hover:bg-slate-50">›</button>
              </div>
              <h3 class="min-w-40 text-sm font-bold text-slate-800">{{ viewTitle }}</h3>
              <button v-if="canManageResources" type="button" @click="openBlackoutForm" class="ml-auto inline-flex items-center gap-2 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm font-semibold text-rose-700 transition hover:bg-rose-100">
                <span aria-hidden="true">⛔</span> Manage blackout
              </button>
            </div>
          </div>

          <div class="grid gap-3 border-b border-slate-100 bg-slate-50/70 p-4 sm:grid-cols-2 xl:grid-cols-[1fr_1fr_1.5fr]">
            <label class="block">
              <span class="mb-1.5 block text-xs font-semibold text-slate-500">Resource</span>
              <select v-model="resourceFilter" class="w-full rounded-lg border border-slate-200 bg-white px-3 py-2.5 text-sm outline-none focus:border-indigo-400 focus:ring-2 focus:ring-indigo-100">
               <option value="All resources">All resources</option>
<option
  v-for="resource in resources"
  :key="resource.name"
  :value="resource.name"
>
  {{ resource.resource_name || resource.name }}
</option>
              </select>
            </label>
            <label class="block">
              <span class="mb-1.5 block text-xs font-semibold text-slate-500">Booking status</span>
              <select v-model="statusFilter" class="w-full rounded-lg border border-slate-200 bg-white px-3 py-2.5 text-sm outline-none focus:border-indigo-400 focus:ring-2 focus:ring-indigo-100">
                <option>All statuses</option>
                <option>Confirmed</option>
                <option>Pending</option>
                <option>Completed</option>
                <option>No Show</option>
                <option>Cancelled</option>
              </select>
            </label>
            <label class="block">
              <span class="mb-1.5 block text-xs font-semibold text-slate-500">Search</span>
              <div class="flex items-center rounded-lg border border-slate-200 bg-white px-3 focus-within:border-indigo-400 focus-within:ring-2 focus-within:ring-indigo-100">
                <span class="mr-2 text-slate-400">⌕</span>
                <input v-model="searchQuery" placeholder="Search bookings or resources..." class="min-w-0 flex-1 py-2.5 text-sm outline-none" />
                <button v-if="searchQuery" @click="searchQuery = ''" aria-label="Clear search" class="px-1 text-slate-400 hover:text-slate-700">×</button>
              </div>
            </label>
          </div>

          <div class="border-b border-slate-100 px-4 py-3">
            <div class="flex flex-wrap items-center gap-x-5 gap-y-2 text-xs text-slate-500">
              <span class="font-semibold text-slate-600">Legend</span>
              <span class="flex items-center gap-2"><i class="h-2.5 w-2.5 rounded-sm bg-blue-500"></i> Confirmed</span>
              <span class="flex items-center gap-2"><i class="h-2.5 w-2.5 rounded-sm bg-amber-400"></i> Pending</span>
              <span class="flex items-center gap-2"><i class="h-2.5 w-2.5 rounded-sm bg-rose-400"></i> Cancelled</span>
            </div>
          </div>

          <!-- MONTH VIEW -->
          <div v-if="calendarView === 'Month'" class="overflow-x-auto">
            <div class="min-w-[720px]">
              <div class="grid grid-cols-7 border-b border-slate-200 bg-slate-50">
                <div v-for="day in ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']" :key="day" class="px-3 py-3 text-center text-xs font-bold uppercase tracking-wide text-slate-500">{{ day }}</div>
              </div>
              <div class="grid grid-cols-7">
                <div
                 v-for="day in monthDays"
  :key="dateKey(day)"
  class="min-h-28 border-b border-r border-slate-100 p-2"
  :class="[
    day.getMonth() !== selectedDate.getMonth()
      ? 'bg-slate-50/70'
      : 'bg-white',
    blackoutResourcesOn(day).length
      ? 'ring-1 ring-inset ring-red-300 bg-red-50/70'
      : ''
  ]"
                >
                  <button
                    @click="selectDay(day)"
                    class="mb-2 flex h-7 w-7 items-center justify-center rounded-full text-xs font-semibold"
                    :class="sameDay(day, new Date()) ? 'bg-indigo-600 text-white' : day.getMonth() !== selectedDate.getMonth() ? 'text-slate-300 hover:bg-slate-200' : 'text-slate-700 hover:bg-indigo-50 hover:text-indigo-700'"
                  >{{ day.getDate() }}</button>
                  <span
  v-if="blackoutResourcesOn(day).length"
  class="mb-1 block rounded bg-red-100 px-1.5 py-0.5 text-[10px] font-semibold text-red-700"
>
  Blackout
</span>
                  <button
                    v-for="booking in bookingsOn(day).slice(0, 3)"
                    :key="booking.id"
                    @click="openBooking(booking)"
                    class="mb-1 block w-full truncate rounded px-1.5 py-1 text-left text-[10px] font-semibold"
                    :class="booking.status === 'Pending' ? 'bg-amber-50 text-amber-800' : booking.status === 'Completed' ? 'bg-emerald-50 text-emerald-800' : booking.status === 'No Show' ? 'bg-slate-100 text-slate-700' : booking.status === 'Cancelled' ? 'bg-rose-50 text-rose-800' : 'bg-blue-50 text-blue-800'"
                  >{{ booking.start }} {{ booking.title }}</button>
                  <button v-if="bookingsOn(day).length > 3" @click="selectDay(day)" class="text-[10px] font-semibold text-indigo-600 hover:text-indigo-800">+{{ bookingsOn(day).length - 3 }} more</button>
                </div>
              </div>
            </div>
          </div>

          <!-- WEEK VIEW -->
          <div v-else-if="calendarView === 'Week'" class="overflow-x-auto">
            <div class="min-w-[900px]">
              <div class="grid grid-cols-7 border-b border-slate-200">
                <button
                  v-for="day in weekDays"
                  :key="dateKey(day)"
                  @click="selectDay(day)"
                  class="border-r border-slate-100 px-2 py-4 text-center transition hover:bg-indigo-50/50"
                >
                  <span class="block text-xs font-semibold uppercase tracking-wide text-slate-500">{{ formatDate(day, { weekday: 'short' }) }}</span>
                  <span class="mx-auto mt-2 flex h-9 w-9 items-center justify-center rounded-full text-sm font-bold" :class="sameDay(day, new Date()) ? 'bg-indigo-600 text-white' : sameDay(day, selectedDate) ? 'bg-indigo-50 text-indigo-700' : 'text-slate-800'">{{ day.getDate() }}</span>
                  <span class="mt-1 block text-[10px] text-slate-400">{{ bookingsOn(day).length }} bookings</span>
                         <span
  v-if="blackoutResourcesOn(day).length"
  class="mb-1 block rounded bg-red-100 px-1.5 py-0.5 text-[10px] font-semibold text-red-700"
>
  Blackout
</span>
                </button>
         
              </div>
              <div class="grid grid-cols-7">
                <div v-for="day in weekDays" :key="dateKey(day)" class="min-h-[390px] border-r border-slate-100 p-2" :class="sameDay(day, new Date()) ? 'bg-indigo-50/30' : ''">

<button
  v-for="booking in bookingsOn(day)"
  :key="booking.id"
  @click="openBooking(booking)"
  class="group mb-2 block w-full overflow-hidden rounded-lg border border-slate-200 border-l-4 p-2.5 text-left shadow-sm transition hover:border-indigo-200 hover:shadow-md"
  :class="booking.status === 'Pending'
    ? 'border-l-amber-400 bg-amber-50/80'
    : booking.status === 'Cancelled'
      ? 'border-l-rose-400 bg-rose-50/80'
      : booking.status === 'Completed'
        ? 'border-l-emerald-500 bg-emerald-50/50'
        : booking.status === 'No Show'
          ? 'border-l-slate-400 bg-slate-50'
          : 'border-l-indigo-500 bg-white'"
>
  <div class="flex items-center justify-between gap-1">
    <span
      class="min-w-0 truncate text-[11px] font-bold tabular-nums"
      :class="booking.status === 'Pending'
        ? 'text-amber-800'
        : booking.status === 'Cancelled'
          ? 'text-rose-800'
          : booking.status === 'Completed'
            ? 'text-emerald-800'
            : booking.status === 'No Show'
              ? 'text-slate-700'
              : 'text-indigo-700'"
    >
      {{ timeLabel(booking.start) }}–{{ timeLabel(booking.end) }}
    </span>
    <span
      class="shrink-0 rounded-full px-1.5 py-0.5 text-[9px] font-semibold"
      :class="booking.status === 'Pending'
        ? 'bg-amber-100 text-amber-800'
        : booking.status === 'Cancelled'
          ? 'bg-rose-100 text-rose-800'
          : booking.status === 'Completed'
            ? 'bg-emerald-100 text-emerald-800'
            : booking.status === 'No Show'
              ? 'bg-slate-200 text-slate-700'
              : 'bg-indigo-100 text-indigo-700'"
    >
      {{ booking.status === 'Pending' ? 'Pending confirmation' : booking.status === 'Cancelled' ? 'Cancelled' : booking.status === 'Completed' ? 'Completed' : booking.status === 'No Show' ? 'No show' : booking.status === 'Confirmed' ? 'Confirmed' : booking.status }}
    </span>
  </div>

  <p class="mt-2 truncate text-xs font-semibold text-slate-800">
    {{ booking.title || 'Untitled booking' }}
  </p>

  <p class="mt-1 truncate text-[10px] text-slate-500">
    {{ booking.resourceLabel || booking.resource }}
  </p>

  <p class="mt-2 text-[10px] font-medium text-indigo-600 opacity-0 transition group-hover:opacity-100">
    View details →
  </p>
</button>

                  <p v-if="bookingsOn(day).length === 0" class="pt-3 text-center text-xs text-slate-300">No bookings</p>
                </div>
              </div>
            </div>
          </div>


          
          
<!-- DAY VIEW -->
<div v-else-if="calendarView === 'Day'" class="overflow-x-auto">
  <div class="min-w-[720px]">
    <div class="border-b border-slate-200 bg-slate-50 px-4 py-3">
      <p class="text-sm font-semibold text-slate-700">{{ formatDate(selectedDate, { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' }) }}</p>
      <p class="mt-1 text-xs text-slate-500">Bookings grouped by resource for the selected day.</p>
    </div>
    <div v-if="scheduleLoading" class="p-10 text-center text-sm text-slate-500">Loading day schedule…</div>
    <div v-else-if="!resources.filter(resource => resourceFilter === 'All resources' || resource.name === resourceFilter).some(resource => bookingsForResource(resource.name, selectedDate).length)" class="p-10 text-center">
      <p class="text-sm font-semibold text-slate-700">No bookings for this day</p>
      <p class="mt-1 text-xs text-slate-500">Try another date or change the resource and status filters.</p>
    </div>
    <div v-else class="divide-y divide-slate-100">
      <section v-for="resource in resources.filter(resource => resourceFilter === 'All resources' || resource.name === resourceFilter)" :key="resource.name" class="grid gap-3 p-4 md:grid-cols-[220px_1fr]">
        <div>
          <h4 class="text-sm font-semibold text-slate-800">{{ resource.resource_name || resource.name }}</h4>
          <p class="mt-1 text-xs text-slate-500">{{ resource.resource_type || resource.resource_category || 'Resource' }}</p>
          <p class="mt-1 text-xs text-slate-400">{{ bookingsForResource(resource.name, selectedDate).length }} bookings</p>
          <span v-if="blackoutResourcesOn(selectedDate).some(item => item.name === resource.name)" class="mt-2 inline-flex rounded bg-rose-100 px-2 py-1 text-[10px] font-semibold text-rose-700">Blackout</span>
        </div>
        <div class="space-y-2">
          <button v-for="booking in bookingsForResource(resource.name, selectedDate)" :key="booking.id" @click="openBooking(booking)" class="flex w-full items-start gap-3 rounded-lg border p-3 text-left transition hover:border-indigo-300 hover:bg-indigo-50/40" :class="booking.status === 'Pending' ? 'border-amber-200 bg-amber-50/60' : booking.status === 'Cancelled' ? 'border-rose-200 bg-rose-50/60' : booking.status === 'Completed' ? 'border-emerald-200 bg-emerald-50/60' : booking.status === 'No Show' ? 'border-slate-200 bg-slate-50' : 'border-slate-200 bg-white'">
            <span class="min-w-[108px] text-xs font-bold tabular-nums text-slate-700">{{ timeLabel(booking.start) }}–{{ timeLabel(booking.end) }}</span>
            <span class="min-w-0 flex-1">
              <span class="block truncate text-sm font-semibold text-slate-800">{{ booking.title || 'Untitled booking' }}</span>
              <span class="mt-1 block text-xs text-slate-500">{{ booking.status }}</span>
            </span>
            <span class="text-xs font-semibold text-indigo-600">Details →</span>
          </button>
          <p v-if="!bookingsForResource(resource.name, selectedDate).length" class="rounded-lg border border-dashed border-slate-200 px-3 py-4 text-xs text-slate-400">No bookings</p>
        </div>
      </section>
    </div>
  </div>
</div>

<!-- TIMELINE VIEW -->
<div v-else-if="calendarView === 'Timeline'" class="overflow-x-auto">
  <div class="min-w-[2590px]">
    <!-- Timeline header -->
    <div class="grid grid-cols-[190px_2400px] border-b border-slate-200 bg-slate-50">
      <div
        class="sticky left-0 z-[3] border-r border-slate-200 bg-slate-50 px-4 py-3 text-xs font-bold uppercase tracking-wide text-slate-500"
      >
        Resource
      </div>

      <div class="relative h-10">
        <div class="absolute inset-0 grid grid-cols-[repeat(24,100px)]">
          <div
            v-for="hour in 24"
            :key="hour"
            class="border-r border-slate-100 px-1 py-3 text-center text-[10px] font-semibold text-slate-500"
          >
            {{ String(hour - 1).padStart(2, '0') }}:00
          </div>
        </div>
      </div>
    </div>

    <!-- Resource rows -->
    <div
      v-for="resource in resources.filter(
        r => resourceFilter === 'All resources' || r.name === resourceFilter
      )"
      :key="resource.name"
      class="grid grid-cols-[190px_2400px] border-b border-slate-100"
    >
      <!-- Fixed resource column -->
      <div class="sticky left-0 z-[2] border-r border-slate-200 bg-white p-4">
        <p class="text-sm font-semibold text-slate-800">
          {{ resource.resource_name || resource.name }}
        </p>
        <p class="mt-1 text-xs text-slate-400">
          {{ resource.resource_type || resource.type || 'Resource' }}
        </p>
        <span
  v-if="blackoutResourcesOn(selectedDate).some(r => r.name === resource.name)"
  class="mt-2 inline-block rounded bg-red-100 px-1.5 py-0.5 text-[10px] font-semibold text-red-700"
>
  Blackout
</span>
      </div>

      <!-- 24-hour timeline track -->
      <div class="relative min-h-24 w-[2400px]">
      
<div
  v-if="(resourceSchedules[resource.name] || [])
    .some(daySchedule =>
      daySchedule.date === dateKey(selectedDate) &&
      daySchedule.is_blackout
    )"
  class="absolute inset-0 z-10 bg-red-500/10 pointer-events-none"
></div>

      

      
<div
  v-for="slot in (resourceSchedules[resource.name] || [])
    .filter(daySchedule => daySchedule.date === dateKey(selectedDate))
    .flatMap(daySchedule => daySchedule.slots || [])
    .filter(slot => slot.status === 'available')"
  :key="`${resource.name}-${slot.start_time_user_datetime}`"
  class="absolute top-0 h-full bg-gray-400/10 pointer-events-none"
  :style="timelineAvailabilityStyle(slot, selectedDate)"
></div>

        <!-- Hour grid and clickable empty slots -->
        <div class="absolute inset-0 grid grid-cols-[repeat(24,100px)]">
          <button
            v-for="hour in 24"
            :key="hour"
            @click="selectSlot(resource.name, selectedDate, hour - 1)"
            class="border-r border-slate-100 transition hover:bg-indigo-200/60"
            :aria-label="`Select ${String(hour - 1).padStart(2, '0')}:00 for ${resource.resource_name || resource.name}`"
          ></button>
        </div>

        <!-- Booking cards positioned by start and end time -->
        <button
          v-for="booking in bookingsForResource(resource.name).filter(
            b => b.status !== 'Cancelled'
          )"
          :key="booking.id"
          @click.stop="booking.docName ? openBooking(booking) : null"
          class="absolute z-[1] overflow-hidden rounded-md border-l-[3px] px-2 py-2 text-left text-xs shadow-sm transition hover:shadow-md"
          :class="booking.status === 'Pending'
            ? 'border-amber-400 bg-amber-50 text-amber-900'
            : 'border-blue-400 bg-blue-50 text-blue-900'"
          :style="timelineBookingStyle(booking)"
          :title="`${booking.title}: ${timeLabel(booking.start)} – ${timeLabel(booking.end)}`"
        >
          <span class="block truncate font-semibold">
            {{ booking.title }}
          </span>
          <span class="mt-1 block truncate text-[10px]">
            {{ timeLabel(booking.start) }} – {{ timeLabel(booking.end) }}
          </span>
        </button>
      </div>
    </div>

    <!-- Timeline footer -->
    <p class="border-t border-slate-100 px-4 py-3 text-xs text-slate-400">
      Select an empty time slot to choose a potential booking time.
    </p>
  </div>
</div>



          <div class="flex flex-wrap items-center justify-between gap-3 border-t border-slate-200 bg-slate-50/70 px-4 py-3">
            <p class="text-xs text-slate-500">{{ filteredBookings.length }} bookings match your filters.</p>
            <button @click="resourceFilter = 'All resources'; statusFilter = 'All statuses'; searchQuery = ''" class="text-xs font-semibold text-indigo-600 hover:text-indigo-800">Clear filters</button>
          </div>
        </section>
      </div>

<div v-else-if="activeView === 'Resources'" class="p-5 md:p-8">
  <section class="rounded-xl border border-slate-200 bg-white p-6">
    <div class="flex flex-wrap items-center justify-between gap-4">
      <div>
        <h2 class="text-xl font-bold text-slate-900">Resources</h2>
        <p class="mt-1 text-sm text-slate-500">
          {{ canManageResources ? 'Create and manage your bookable resources.' : 'View available resources and their schedules.' }}
        </p>
      </div>

      <button
        v-if="canManageResources"
        type="button"
        @click="openResourceCreate"
        class="rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-indigo-700"
      >
        + Create Resource
      </button>
    </div>

    <p v-if="resourcesError" class="mt-4 text-sm text-red-600">
      {{ resourcesError }}
    </p>

    <div v-if="resourcesLoading" class="py-8 text-center text-sm text-slate-500">
      Loading resources…
    </div>

    <div v-else-if="resources.length" class="mt-6 overflow-x-auto">
      <table class="w-full text-left text-sm">
        <thead>
          <tr class="border-b border-slate-200 text-slate-500">
            <th class="px-3 py-3 font-medium">Resource Name</th>
            <th class="px-3 py-3 font-medium">Category / Type</th>
            <th class="px-3 py-3 font-medium">Availability</th>
            <th class="px-3 py-3 font-medium">Time Zone</th>
            <th class="px-3 py-3 font-medium">Quick Check</th>
            <th v-if="canManageResources" class="px-3 py-3 font-medium">Action</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="resource in resources"
            :key="resource.name"
            class="border-b border-slate-100"
          >
            <td class="px-3 py-3 font-medium text-slate-900">
              {{ resource.resource_name || resource.name }}
            </td>
            <td class="px-3 py-3">
              <span class="block font-medium">{{ resource.resource_category || 'Other' }}</span>
              <span class="block text-xs text-slate-500">{{ resource.resource_type || '—' }}</span>
            </td>
<td class="px-3 py-3">
              {{ resource.available ? 'Available' : 'Unavailable' }}
            </td>
            <td class="px-3 py-3">{{ resource.time_zone || '—' }}</td>
            <td class="px-3 py-3">
              <button
                type="button"
                @click="openNewBooking(resource)"
                :disabled="resource.available === 0 || resource.available === false"
                class="rounded-lg border border-indigo-200 bg-indigo-50 px-3 py-1.5 text-sm font-semibold text-indigo-700 hover:bg-indigo-100 disabled:cursor-not-allowed disabled:opacity-50"
              >Check slots</button>
            </td>
            
            <td v-if="canManageResources" class="px-3 py-3">
              <div class="flex flex-wrap items-center gap-2">
              <button
                type="button"
                @click="openResourceEdit(resource)"
                class="inline-flex items-center rounded-lg border border-indigo-200 bg-indigo50 px-3 py-1.5 text-sm font-semibold text-indigo-700 transition hover:border-indigo-300 hover:bg-indigo-100"
              >
                Edit
              </button>
                <button
      type="button"
      @click="openResourceAvailability(resource)"
      class="inline-flex items-center rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-1.5 text-sm font-semibold text-emerald-700 transition hover:bg-emerald-100"
    >
      Availability
    </button>
  </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <p v-else class="py-8 text-center text-sm text-slate-500">
      No resources found. Create your first resource to get started.
    </p>
  </section>
</div>

     
<div v-else-if="activeView === 'Bookings'" class="p-4 md:p-8">
  <section class="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
    <div class="flex flex-col gap-4 border-b border-slate-200 p-5 md:flex-row md:items-center md:justify-between">
      <div>
        <h2 class="text-xl font-bold text-slate-900">All Bookings</h2>
        <p class="mt-1 text-sm text-slate-500">
          View and manage booking records.
        </p>
      </div>

      <button
        type="button"
        @click="loadBookingsPage"
        class="rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50"
      >
        Refresh
      </button>
    </div>

    <div class="grid gap-3 border-b border-slate-100 bg-slate-50 p-4 sm:grid-cols-2">
      <input
        v-model="bookingsPageSearch"
        type="search"
        placeholder="Search ID, customer, or resource..."
        class="w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-sm"
      />

      <select
        v-model="bookingsPageStatus"
        class="w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-sm"
      >
        <option>All statuses</option>
        <option>Pending</option>
        <option>Confirmed</option>
        <option>Cancelled</option>
      </select>
    </div>

    <p v-if="bookingsPageError" class="m-4 rounded-lg bg-red-50 p-3 text-sm text-red-700">
      {{ bookingsPageError }}
    </p>

    <div v-if="bookingsPageLoading" class="p-10 text-center text-sm text-slate-500">
      Loading bookings…
    </div>

    <div v-else class="overflow-x-auto">
      <table class="w-full min-w-[850px] text-left text-sm">
        <thead class="bg-white text-xs uppercase tracking-wide text-slate-500">
          <tr>
            <th class="px-4 py-3">Booking ID</th>
            <th class="px-4 py-3">Customer</th>
            <th class="px-4 py-3">Resource</th>
            <th class="px-4 py-3">Date</th>
            <th class="px-4 py-3">Time</th>
            <th class="px-4 py-3">Status</th>
            <th class="px-4 py-3">Action</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="booking in bookingsPageRecords.filter(b => {
              const query = bookingsPageSearch.trim().toLowerCase()
              const matchesSearch = !query ||
                (b.booking_id || b.name || '').toLowerCase().includes(query) ||
                (b.customer || '').toLowerCase().includes(query) ||
                (b.resource || '').toLowerCase().includes(query)
              const matchesStatus = bookingsPageStatus === 'All statuses' ||
                b.status === bookingsPageStatus
              return matchesSearch && matchesStatus
            })"
            :key="booking.name"
            class="border-t border-slate-100 hover:bg-slate-50"
          >
            <td class="px-4 py-3 font-semibold text-slate-800">
              {{ booking.booking_id || booking.name }}
            </td>
            <td class="px-4 py-3">{{ booking.customer || '—' }}</td>
            <td class="px-4 py-3">{{ booking.resource || '—' }}</td>
            <td class="px-4 py-3">{{ booking.booking_date || '—' }}</td>
            <td class="px-4 py-3">
              {{ booking.start_time || '—' }} – {{ booking.end_time || '—' }}
            </td>
            <td class="px-4 py-3">
              <span
                class="rounded-full px-2.5 py-1 text-xs font-semibold"
                :class="booking.status === 'Confirmed'
                  ? 'bg-blue-50 text-blue-700'
                  : booking.status === 'Cancelled'
                    ? 'bg-rose-50 text-rose-700'
                    : 'bg-amber-50 text-amber-800'"
              >
                {{ booking.status || 'Pending' }}
              </span>
            </td>
            <td class="px-4 py-3">
              <button
                type="button"
                @click="openBooking({
                  id: booking.booking_id || booking.name,
                  docName: booking.name,
                  title: booking.customer || 'Booking',
                  resource: booking.resource,
                  date: booking.booking_date,
                  start: new Date(`${booking.booking_date}T${booking.start_time}`),
                  end: new Date(`${booking.booking_date}T${booking.end_time}`),
                  status: booking.status || 'Pending'
                })"
                class="font-semibold text-indigo-600 hover:text-indigo-800"
              >
                View
              </button>
            </td>
          </tr>
        </tbody>
      </table>

      <p
        v-if="!bookingsPageRecords.length"
        class="p-10 text-center text-sm text-slate-500"
      >
        No bookings found.
      </p>
    </div>
  </section>
</div>

<div v-else-if="activeView === 'Reports'" class="space-y-6 p-4 md:p-8">
  <div class="flex flex-wrap items-end justify-between gap-4">
    <div>
      <h2 class="text-2xl font-bold tracking-tight text-slate-900">Booking Reports</h2>
      <p class="mt-1 text-sm text-slate-500">Operational summary by date range, status and resource.</p>
    </div>
    <button type="button" @click="exportBookingReport" :disabled="!reportLoaded || !reportRecords.length" class="rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-50">Export CSV</button>
  </div>
  <section class="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
    <form class="grid gap-3 sm:grid-cols-[1fr_1fr_auto]" @submit.prevent="loadReports">
      <label class="text-sm font-medium text-slate-700">From date<input v-model="reportStartDate" type="date" required class="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2.5" /></label>
      <label class="text-sm font-medium text-slate-700">To date<input v-model="reportEndDate" type="date" required :min="reportStartDate" class="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2.5" /></label>
      <button type="submit" :disabled="reportLoading" class="self-end rounded-lg bg-indigo-600 px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-50">{{ reportLoading ? 'Loading…' : 'Run report' }}</button>
    </form>
    <p class="mt-3 text-xs text-slate-500">Maximum range: 367 calendar days. Results are capped at 5,000 bookings.</p>
    <p v-if="reportError" class="mt-3 rounded-lg bg-rose-50 p-3 text-sm text-rose-700">{{ reportError }}</p>
  </section>
  <div v-if="reportLoading" class="rounded-xl border border-slate-200 bg-white p-10 text-center text-sm text-slate-500">Loading report data…</div>
  <template v-else-if="reportLoaded">
    <div class="grid gap-4 sm:grid-cols-2 xl:grid-cols-6">
      <div class="rounded-xl border border-slate-200 bg-white p-5"><p class="text-sm text-slate-500">Bookings</p><p class="mt-2 text-3xl font-bold text-slate-900">{{ reportRecords.length }}</p></div>
      <div class="rounded-xl border border-slate-200 bg-white p-5"><p class="text-sm text-slate-500">Confirmed</p><p class="mt-2 text-3xl font-bold text-emerald-700">{{ reportConfirmedCount }}</p></div>
      <div class="rounded-xl border border-slate-200 bg-white p-5"><p class="text-sm text-slate-500">Pending</p><p class="mt-2 text-3xl font-bold text-amber-700">{{ reportPendingCount }}</p></div>
      <div class="rounded-xl border border-slate-200 bg-white p-5"><p class="text-sm text-slate-500">Completed</p><p class="mt-2 text-3xl font-bold text-emerald-700">{{ reportCompletedCount }}</p></div>
      <div class="rounded-xl border border-slate-200 bg-white p-5"><p class="text-sm text-slate-500">No show</p><p class="mt-2 text-3xl font-bold text-slate-700">{{ reportNoShowCount }}</p></div>
      <div class="rounded-xl border border-slate-200 bg-white p-5"><p class="text-sm text-slate-500">Cancelled</p><p class="mt-2 text-3xl font-bold text-rose-700">{{ reportCancelledCount }}</p></div>
    </div>
    <section class="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
      <div class="border-b border-slate-100 p-5"><h3 class="font-bold text-slate-900">Bookings by resource</h3><p class="mt-1 text-xs text-slate-500">Includes cancelled bookings in volume counts.</p></div>
      <div v-if="!reportByResource.length" class="p-8 text-center text-sm text-slate-500">No bookings in this date range.</div>
      <div v-else class="overflow-x-auto"><table class="w-full min-w-[600px] text-left text-sm"><thead class="bg-slate-50 text-xs uppercase tracking-wide text-slate-500"><tr><th class="px-4 py-3">Resource</th><th class="px-4 py-3">Total</th><th class="px-4 py-3">Confirmed</th><th class="px-4 py-3">Pending</th><th class="px-4 py-3">Cancelled</th></tr></thead><tbody><tr v-for="item in reportByResource" :key="item.name" class="border-t border-slate-100"><td class="px-4 py-3 font-medium text-slate-800">{{ item.name }}</td><td class="px-4 py-3">{{ item.count }}</td><td class="px-4 py-3">{{ item.confirmed }}</td><td class="px-4 py-3">{{ item.pending }}</td><td class="px-4 py-3">{{ item.cancelled }}</td></tr></tbody></table></div>
    </section>
    <section class="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
      <div class="border-b border-slate-100 p-5"><h3 class="font-bold text-slate-900">Booking detail</h3></div>
      <div v-if="!reportRecords.length" class="p-8 text-center text-sm text-slate-500">No booking records found.</div>
      <div v-else class="overflow-x-auto"><table class="w-full min-w-[850px] text-left text-sm"><thead class="bg-slate-50 text-xs uppercase tracking-wide text-slate-500"><tr><th class="px-4 py-3">Booking ID</th><th class="px-4 py-3">Customer</th><th class="px-4 py-3">Resource</th><th class="px-4 py-3">Date</th><th class="px-4 py-3">Time</th><th class="px-4 py-3">Status</th></tr></thead><tbody><tr v-for="row in reportRecords" :key="row.name" class="border-t border-slate-100"><td class="px-4 py-3 font-semibold">{{ row.booking_id || row.name }}</td><td class="px-4 py-3">{{ row.customer || '—' }}</td><td class="px-4 py-3">{{ row.resource_name || row.resource }}</td><td class="px-4 py-3">{{ row.booking_date }}</td><td class="px-4 py-3">{{ row.start_time }}–{{ row.end_time }}</td><td class="px-4 py-3">{{ row.status }}</td></tr></tbody></table></div>
    </section>
  </template>
</div>

<div v-else class="p-5 md:p-8">
  <section class="rounded-xl border border-slate-200 bg-white p-8">
    <p class="text-sm font-semibold text-indigo-600">Booking Diary workspace</p>
    <h2 class="mt-2 text-xl font-bold text-slate-900">{{ activeView }}</h2>
    <p class="mt-2 max-w-xl text-sm leading-6 text-slate-500">
      This section will be connected to your existing Frappe data after the
      Resource Desk calendar is in place.
    </p>
    <button
      @click="activeView = 'Resource Desk'"
      class="mt-5 rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-indigo-700"
    >
      Open Resource Desk
    </button>
  </section>
</div>


      <div v-if="blackoutModalOpen" class="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/40 p-4" @click.self="blackoutModalOpen = false">
        <section role="dialog" aria-modal="true" aria-labelledby="blackout-title" class="w-full max-w-lg overflow-hidden rounded-2xl bg-white shadow-xl">
          <div class="flex items-start justify-between border-b border-slate-100 bg-gradient-to-r from-rose-50 via-white to-white p-5">
            <div class="flex items-start gap-3">
              <span class="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-rose-600 text-lg text-white shadow-sm shadow-rose-200" aria-hidden="true">⛔</span>
              <div>
                <p class="text-xs font-semibold uppercase tracking-[0.16em] text-rose-700">Booking Diary</p>
                <h2 id="blackout-title" class="mt-0.5 text-lg font-bold tracking-tight text-slate-900">Add blackout date</h2>
                <p class="mt-1 text-sm text-slate-500">Block bookings for a selected date.</p>
              </div>
            </div>
            <button type="button" aria-label="Close" @click="blackoutModalOpen = false" class="rounded-lg px-2 py-1 text-xl text-slate-400 hover:bg-slate-100">×</button>
          </div>
          <form class="space-y-4 p-5" @submit.prevent="saveBlackoutDate">
            <label class="block">
              <span class="mb-1.5 block text-sm font-semibold text-slate-700">Date</span>
              <input v-model="blackoutForm.blackout_date" type="date" required class="w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-100" />
            </label>
            <label class="block">
              <span class="mb-1.5 block text-sm font-semibold text-slate-700">End date</span>
              <input v-model="blackoutForm.blackout_end_date" type="date" required :min="blackoutForm.blackout_date" class="w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm" />
            </label>
            <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <label class="block">
                <span class="mb-1.5 block text-sm font-semibold text-slate-700">Start time (optional)</span>
                <input v-model="blackoutForm.start_time" type="time" class="w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm" />
              </label>
              <label class="block">
                <span class="mb-1.5 block text-sm font-semibold text-slate-700">End time (optional)</span>
                <input v-model="blackoutForm.end_time" type="time" class="w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm" />
              </label>
            </div>
            <p class="text-xs text-slate-500">Leave both times blank to block the full day. Times apply on each date in the range.</p>
            <label class="flex items-start gap-3 rounded-lg border border-slate-200 p-3">
              <input v-model="blackoutForm.applies_globally" type="checkbox" class="mt-1 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500" />
              <span><span class="block text-sm font-semibold text-slate-800">Apply to all resources</span><span class="mt-0.5 block text-xs text-slate-500">No resource can be booked on this date.</span></span>
            </label>
            <label v-if="!blackoutForm.applies_globally" class="block">
              <span class="mb-1.5 block text-sm font-semibold text-slate-700">Resource</span>
              <select v-model="blackoutForm.resource" required class="w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-sm">
                <option disabled value="">Choose a resource</option>
                <option v-for="resource in resources" :key="resource.name" :value="resource.name">{{ resource.resource_name || resource.name }}</option>
              </select>
            </label>
            <label class="block">
              <span class="mb-1.5 block text-sm font-semibold text-slate-700">Reason <span class="font-normal text-slate-400">(optional)</span></span>
              <textarea v-model="blackoutForm.reason" rows="3" placeholder="e.g. Public holiday, maintenance, private event" class="w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-100"></textarea>
            </label>
            <p v-if="blackoutError" class="rounded-lg bg-rose-50 p-3 text-sm text-rose-700">{{ blackoutError }}</p>
            <div class="flex justify-end gap-3 border-t border-slate-100 pt-4">
              <button type="button" @click="blackoutModalOpen = false" class="rounded-lg border border-slate-300 px-4 py-2.5 text-sm font-semibold text-slate-700 hover:bg-slate-50">Cancel</button>
              <button type="submit" :disabled="blackoutSaving" class="rounded-lg bg-rose-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-rose-700 disabled:cursor-not-allowed disabled:opacity-60">{{ blackoutSaving ? 'Saving…' : 'Save blackout' }}</button>
            </div>
          </form>
        </section>
      </div>
    </main>
  </div>
</template>
