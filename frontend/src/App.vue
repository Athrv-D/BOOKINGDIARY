 
<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import {
  getResources,
  getUserTimezone,
  getMultiDaySchedule,
  getUserDaySchedule,
  createBooking as submitBooking,
} from './api'

const activeView = ref('Resource Desk')
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
]

const resources = ref([])
const resourcesLoading = ref(false)
const resourcesError = ref('')


const userTimezone = ref('UTC')
const bookings = ref([])
const resourceSchedules = ref({})
const scheduleLoading = ref(false)
const scheduleError = ref('')

 
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
    userTimezone.value = await getUserTimezone()
  } catch (error) {
    console.error('Failed to load user timezone:', error)
  }

  await loadResources()
  await loadSchedule()
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

const demoBookings = ref([
  { id: 'DEMO-001', title: 'Team Meeting', resource: 'Conference Room A', date: offsetDate(0), start: '09:00', end: '10:00', status: 'Confirmed', color: 'blue' },
  { id: 'DEMO-002', title: 'Client Presentation', resource: 'Conference Room A', date: offsetDate(0), start: '11:00', end: '12:30', status: 'Confirmed', color: 'violet' },
  { id: 'DEMO-003', title: 'Project Review', resource: 'Conference Room B', date: offsetDate(0), start: '10:00', end: '11:00', status: 'Pending', color: 'amber' },
  { id: 'DEMO-004', title: 'Workshop', resource: 'Training Hall', date: offsetDate(1), start: '09:30', end: '12:00', status: 'Confirmed', color: 'emerald' },
  { id: 'DEMO-005', title: 'Design Session', resource: 'Studio 1', date: offsetDate(2), start: '13:00', end: '15:00', status: 'Confirmed', color: 'violet' },
  { id: 'DEMO-006', title: 'Planning Meeting', resource: 'Conference Room B', date: offsetDate(-1), start: '14:00', end: '15:00', status: 'Cancelled', color: 'rose' },
  { id: 'DEMO-007', title: 'Department Sync', resource: 'Conference Room A', date: offsetDate(3), start: '10:00', end: '11:30', status: 'Pending', color: 'amber' },
  { id: 'DEMO-008', title: 'Training Session', resource: 'Training Hall', date: offsetDate(5), start: '11:00', end: '13:00', status: 'Confirmed', color: 'emerald' },
])

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
    .filter((booking) => booking.date === key && booking.status !== 'Cancelled')
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




function openBooking(booking) {
  window.alert(
    `${booking.title}\n${booking.resource}\n${booking.date}\n${timeLabel(booking.start)} – ${timeLabel(booking.end)}\n\nDemo booking only. Booking details will connect to Frappe in the next step.`,
  )
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
      resource: slot.resource,
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

const bookingFormOpen = ref(false)

const bookingForm = ref({
  resource: '',
  bookingDate: dateKey(selectedDate.value),
  startTime: '09:00:00',
  endTime: '10:00:00',
  bookingType: 'Single Slot',
  repeatUntil: '',
  customer: '',
  remarks: '',
})

function openNewBooking() {
  bookingError.value = ''
  bookingSuccess.value = ''

  const slot = selectedBookingSlot.value

  bookingForm.value = {
    resource: slot?.resource || resources.value[0]?.name || '',
    bookingDate: slot?.bookingDate || dateKey(selectedDate.value),
    startTime: slot?.startTime || '09:00:00',
    endTime: slot?.endTime || '10:00:00',
    bookingType: 'Single Slot',
    repeatUntil: '',
    customer: '',
    remarks: '',
  }

  bookingFormOpen.value = true
}

async function submitManualBooking() {
  bookingError.value = ''
  bookingSuccess.value = ''

  const form = bookingForm.value

  if (!form.resource || !form.bookingDate || !form.startTime || !form.endTime) {
    bookingError.value = 'Please fill in all required fields.'
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

  bookingSubmitting.value = true

  try {
    await submitBooking({
      resource: form.resource,
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
      remarks: form.remarks.trim(),
    })

    bookingSuccess.value = 'Booking created successfully.'
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
  selectedBookingSlot.value = {
    resource,
    bookingDate: dateKey(date),
    startTime: `${String(hour).padStart(2, '0')}:00:00`,
    endTime: `${String(hour + 1).padStart(2, '0')}:00:00`,
  }
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
          v-for="item in navigation"
          :key="item.name"
          @click="activeView = item.name"
          class="flex shrink-0 items-center gap-3 rounded-lg px-3 py-2.5 text-left text-sm font-medium transition"
          :class="activeView === item.name ? 'bg-indigo-50 text-indigo-700' : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'"
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
          <h1 class="mt-1 text-xl font-bold tracking-tight text-slate-900">{{ activeView }}</h1>
        </div>
        <button @click="openNewBooking" class="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-indigo-700">
          <span class="text-lg leading-none">+</span> New Booking
        </button>
      </header>
      
<div
  v-if="selectedBookingSlot || bookingError || bookingSuccess"
  class="mx-5 mt-4 rounded-lg border border-slate-200 bg-white p-4 md:mx-8"
>
  <p v-if="selectedBookingSlot" class="text-sm text-slate-700">
    Selected: {{ selectedBookingSlot.resource }} ·
    {{ selectedBookingSlot.bookingDate }} ·
    {{ selectedBookingSlot.startTime }}–{{ selectedBookingSlot.endTime }}
  </p>

  <p v-if="bookingError" class="mt-2 text-sm text-red-700">
    {{ bookingError }}
  </p>

  <p v-if="bookingSuccess" class="mt-2 text-sm text-green-700">
    {{ bookingSuccess }}
  </p>
  

  <button
    v-if="selectedBookingSlot"
    @click="createBooking"
    :disabled="bookingSubmitting"
    class="mt-3 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
  >
    {{ bookingSubmitting ? 'Creating booking…' : 'Confirm booking' }}
  </button>
</div>
<div
  v-if="bookingFormOpen"
  class="mx-5 mt-4 rounded-xl border border-slate-200 bg-white p-5 md:mx-8"
>
  <div class="mb-5 flex items-center justify-between">
    <h2 class="text-lg font-bold text-slate-900">New Booking</h2>
    <button
      type="button"
      @click="bookingFormOpen = false"
      class="rounded-lg px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-100"
    >
      Cancel
    </button>
  </div>

  <div class="grid grid-cols-1 gap-4 md:grid-cols-2">
    <label class="block text-sm font-medium text-slate-700">
      Resource *
      <select
        v-model="bookingForm.resource"
        required
        class="mt-1 block w-full rounded-lg border border-slate-300 bg-white px-3 py-2"
      >
        <option value="" disabled>Select resource</option>
        <option
          v-for="resource in resources"
          :key="resource.name"
          :value="resource.name"
        >
          {{ resource.resource_name || resource.name }}
        </option>
      </select>
    </label>

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

  <p class="mt-3 text-xs text-slate-500">
    Booking requests are checked against resource availability and booking rules when submitted.
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
      :disabled="bookingSubmitting"
      class="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
    >
      {{ bookingSubmitting ? 'Submitting…' : 'Submit booking' }}
    </button>
  </div>
</div>

      <div v-if="activeView === 'Resource Desk'" class="p-4 md:p-8">
        <div class="mb-5 flex flex-wrap items-end justify-between gap-4">
          <div>
            <h2 class="text-2xl font-bold tracking-tight text-slate-900">Resource calendar</h2>
            <p class="mt-1 text-sm text-slate-500">View availability and manage bookings across your resources.</p>
          </div>
          <div class="flex items-center gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs font-medium text-amber-800">
            <span class="h-2 w-2 rounded-full bg-amber-500"></span>
            Live data.
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
                    :class="booking.status === 'Pending' ? 'bg-amber-50 text-amber-800' : booking.color === 'violet' ? 'bg-violet-50 text-violet-800' : booking.color === 'emerald' ? 'bg-emerald-50 text-emerald-800' : 'bg-blue-50 text-blue-800'"
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
                    class="mb-2 block w-full rounded-md border-l-[3px] p-2 text-left"
                    :class="booking.status === 'Pending' ? 'border-amber-400 bg-amber-50' : booking.color === 'violet' ? 'border-violet-400 bg-violet-50' : booking.color === 'emerald' ? 'border-emerald-400 bg-emerald-50' : 'border-blue-400 bg-blue-50'"
                  >
                    <span class="block text-[10px] font-bold" :class="booking.status === 'Pending' ? 'text-amber-800' : booking.color === 'violet' ? 'text-violet-800' : booking.color === 'emerald' ? 'text-emerald-800' : 'text-blue-800'">{{ booking.start }}–{{ booking.end }}</span>
                    <span class="mt-1 block text-xs font-semibold leading-4 text-slate-800">{{ booking.title }}</span>
                    <span class="mt-1 block text-[10px] leading-4 text-slate-500">{{ booking.resource }}</span>
                  </button>
                  <p v-if="bookingsOn(day).length === 0" class="pt-3 text-center text-xs text-slate-300">No bookings</p>
                </div>
              </div>
            </div>
          </div>


          
          
<!-- TIMELINE VIEW -->
<div v-else class="overflow-x-auto">
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
          @click.stop="openBooking(booking)"
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

      <div v-else class="p-5 md:p-8">
        <section class="rounded-xl border border-slate-200 bg-white p-8">
          <p class="text-sm font-semibold text-indigo-600">Booking Diary workspace</p>
          <h2 class="mt-2 text-xl font-bold text-slate-900">{{ activeView }}</h2>
          <p class="mt-2 max-w-xl text-sm leading-6 text-slate-500">This section will be connected to your existing Frappe data after the Resource Desk calendar is in place.</p>
          <button v-if="activeView !== 'Resource Desk'" @click="activeView = 'Resource Desk'" class="mt-5 rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-indigo-700">Open Resource Desk</button>
        </section>
      </div>
    </main>
  </div>
</template>
