 
<script setup>
import { computed, onMounted,ref } from 'vue'
import { getResources } from './api'

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

onMounted(async () => {
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
})

function dateKey(date) {
  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, '0')
  const d = String(date.getDate()).padStart(2, '0')
  return `${y}-${m}-${d}`
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
  const [hour, minute] = time.split(':').map(Number)
  const date = new Date()
  date.setHours(hour, minute, 0, 0)
  return formatDate(date, { hour: 'numeric', minute: '2-digit' })
}

function offsetDate(days) {
  return dateKey(addDays(new Date(), days))
}

// Temporary UI data only. Replace with Frappe API data in the next stage.
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
  const query = searchQuery.value.trim().toLowerCase()
  return demoBookings.value.filter((booking) => {
    const matchesResource =
      resourceFilter.value === 'All resources' ||
      booking.resource === resourceFilter.value
    const matchesStatus =
      statusFilter.value === 'All statuses' ||
      booking.status === statusFilter.value
    const matchesSearch =
      !query ||
      [booking.title, booking.resource, booking.id, booking.status]
        .some((value) => value.toLowerCase().includes(query))
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
    .sort((a, b) => a.start.localeCompare(b.start))
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
  const [startHour, startMinute] = booking.start.split(':').map(Number)
  const [endHour, endMinute] = booking.end.split(':').map(Number)
  const start = startHour * 60 + startMinute
  const end = endHour * 60 + endMinute
  return {
    top: `${((start - 8 * 60) / 60) * 56}px`,
    height: `${Math.max(((end - start) / 60) * 56 - 3, 25)}px`,
  }
}

function openBooking(booking) {
  window.alert(
    `${booking.title}\n${booking.resource}\n${booking.date}\n${timeLabel(booking.start)} – ${timeLabel(booking.end)}\n\nDemo booking only. Booking details will connect to Frappe in the next step.`,
  )
}

function createBooking() {
  window.alert('Booking creation will be connected to the existing Frappe booking form in the next step.')
}

function selectSlot(resource, date, hour) {
  window.alert(
    `Selected slot: ${resource}\n${dateKey(date)} at ${timeLabel(`${String(hour).padStart(2, '0')}:00`)}\n\nAvailability validation will connect to Frappe in the next step.`,
  )
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
          <p class="text-xs font-semibold text-slate-700">Prototype mode</p>
        </div>
        <p class="text-xs leading-5 text-slate-500">Calendar uses sample bookings. Live Frappe data will be connected next.</p>
      </div>
    </aside>

    <main class="min-w-0 flex-1">
      <header class="flex flex-wrap items-center justify-between gap-4 border-b border-slate-200 bg-white px-5 py-4 md:px-8">
        <div>
          <div class="text-xs text-slate-400">Workspace <span class="mx-1">/</span> <span class="text-slate-600">{{ activeView }}</span></div>
          <h1 class="mt-1 text-xl font-bold tracking-tight text-slate-900">{{ activeView }}</h1>
        </div>
        <button @click="createBooking" class="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-indigo-700">
          <span class="text-lg leading-none">+</span> New Booking
        </button>
      </header>

      <div v-if="activeView === 'Resource Desk'" class="p-4 md:p-8">
        <div class="mb-5 flex flex-wrap items-end justify-between gap-4">
          <div>
            <h2 class="text-2xl font-bold tracking-tight text-slate-900">Resource calendar</h2>
            <p class="mt-1 text-sm text-slate-500">View availability and manage bookings across your resources.</p>
          </div>
          <div class="flex items-center gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs font-medium text-amber-800">
            <span class="h-2 w-2 rounded-full bg-amber-500"></span>
            Sample data
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
                  :class="day.getMonth() !== selectedDate.getMonth() ? 'bg-slate-50/70' : 'bg-white'"
                >
                  <button
                    @click="selectDay(day)"
                    class="mb-2 flex h-7 w-7 items-center justify-center rounded-full text-xs font-semibold"
                    :class="sameDay(day, new Date()) ? 'bg-indigo-600 text-white' : day.getMonth() !== selectedDate.getMonth() ? 'text-slate-300 hover:bg-slate-200' : 'text-slate-700 hover:bg-indigo-50 hover:text-indigo-700'"
                  >{{ day.getDate() }}</button>
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

          <!-- DAY VIEW -->
          <div v-else-if="calendarView === 'Day'" class="overflow-x-auto">
            <div class="min-w-[680px]">
              <div class="grid grid-cols-[190px_1fr] border-b border-slate-200 bg-slate-50">
                <div class="border-r border-slate-200 px-4 py-3 text-xs font-bold uppercase tracking-wide text-slate-500">Resource</div>
                <div class="px-4 py-3 text-sm font-semibold text-slate-700">{{ formatDate(selectedDate, { weekday: 'long', month: 'short', day: 'numeric' }) }}</div>
              </div>
              <div v-for="resource in resources.filter(r => resourceFilter === 'All resources' || r.name === resourceFilter)" :key="resource.name" class="grid grid-cols-[190px_1fr] border-b border-slate-100">
                <div class="border-r border-slate-200 p-4">
                  <p class="text-sm font-semibold text-slate-800">{{ resource.name }}</p>
                  <p class="mt-1 text-xs text-slate-400">{{ resource.type }}</p>
                  <p class="mt-2 text-xs text-slate-500">{{ bookingsForResource(resource.name).length }} bookings</p>
                </div>
                <div class="relative">
                  <div class="grid h-[896px] grid-rows-16">
                    <button v-for="hour in 16" :key="hour" @click="selectSlot(resource.name, selectedDate, hour + 6)" class="relative border-b border-slate-100 text-left hover:bg-indigo-50/60">
                      <span class="absolute left-2 top-1 text-[10px] text-slate-300">{{ String(hour + 6).padStart(2, '0') }}:00</span>
                    </button>
                  </div>
                  <button
                    v-for="booking in bookingsForResource(resource.name)"
                    :key="booking.id"
                    @click="openBooking(booking)"
                    class="absolute left-16 right-3 z-[1] overflow-hidden rounded-lg border-l-4 p-2 text-left shadow-sm"
                    :class="booking.status === 'Pending' ? 'border-amber-400 bg-amber-50 text-amber-950' : booking.color === 'violet' ? 'border-violet-400 bg-violet-50 text-violet-950' : booking.color === 'emerald' ? 'border-emerald-400 bg-emerald-50 text-emerald-950' : 'border-blue-400 bg-blue-50 text-blue-950'"
                    :style="bookingStyle(booking)"
                  >
                    <span class="block truncate text-xs font-bold">{{ booking.title }}</span>
                    <span class="mt-1 block text-[10px]">{{ timeLabel(booking.start) }} – {{ timeLabel(booking.end) }}</span>
                  </button>
                </div>
              </div>
            </div>
          </div>

          <!-- TIMELINE VIEW -->
          <div v-else class="overflow-x-auto">
            <div class="min-w-[850px]">
              <div class="grid grid-cols-[190px_repeat(12,minmax(48px,1fr))] border-b border-slate-200 bg-slate-50">
                <div class="sticky left-0 z-[2] border-r border-slate-200 bg-slate-50 px-4 py-3 text-xs font-bold uppercase tracking-wide text-slate-500">Resource</div>
                <div v-for="hour in 12" :key="hour" class="border-r border-slate-100 px-1 py-3 text-center text-[10px] font-semibold text-slate-500">{{ String(hour + 7).padStart(2, '0') }}:00</div>
              </div>
              <div v-for="resource in resources.filter(r => resourceFilter === 'All resources' || r.name === resourceFilter)" :key="resource.name" class="grid grid-cols-[190px_repeat(12,minmax(48px,1fr))] border-b border-slate-100">
                <div class="sticky left-0 z-[2] border-r border-slate-200 bg-white p-4">
                  <p class="text-sm font-semibold text-slate-800">{{ resource.name }}</p>
                  <p class="mt-1 text-xs text-slate-400">{{ resource.type }}</p>
                </div>
                <button v-for="hour in 12" :key="hour" @click="selectSlot(resource.name, selectedDate, hour + 7)" class="relative min-h-24 border-r border-slate-100 hover:bg-indigo-50/60">
                  <span class="absolute inset-x-0 top-0 border-t border-dashed border-slate-100"></span>
                  <span
                    v-for="booking in bookingsForResource(resource.name).filter(b => Number(b.start.slice(0, 2)) === hour + 7)"
                    :key="booking.id"
                    @click.stop="openBooking(booking)"
                    class="absolute inset-x-0.5 top-3 z-[1] overflow-hidden rounded border-l-[3px] px-1 py-2 text-left text-[10px] font-semibold"
                    :class="booking.status === 'Pending' ? 'border-amber-400 bg-amber-50 text-amber-900' : booking.color === 'violet' ? 'border-violet-400 bg-violet-50 text-violet-900' : booking.color === 'emerald' ? 'border-emerald-400 bg-emerald-50 text-emerald-900' : 'border-blue-400 bg-blue-50 text-blue-900'"
                  >{{ booking.title }}</span>
                </button>
              </div>
              <p class="px-4 py-3 text-xs text-slate-400">Timeline prototype: select an empty cell to choose a potential booking slot.</p>
            </div>
          </div>

          <div class="flex flex-wrap items-center justify-between gap-3 border-t border-slate-200 bg-slate-50/70 px-4 py-3">
            <p class="text-xs text-slate-500">{{ filteredBookings.length }} sample bookings match your filters.</p>
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
