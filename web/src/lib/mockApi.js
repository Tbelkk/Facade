// MOCK API: the endpoint list and fake data generators shown on the API page.
// When the back end can generate a real API, replace SPEC (or load it from the generated OpenAPI)
// and swap each `run` for a real request. Data is seeded from the parameters, so the same request
// always returns the same mock data, and /astra/{date}/{building} is a subset of /astra/{date}.
export const mockApi = (function () {
  /* ---------------- seeded randomness ---------------- */
  function hash(s) { let h = 2166136261; for (const ch of String(s)) { h ^= ch.charCodeAt(0); h = Math.imul(h, 16777619); } return h >>> 0; }
  function rng(seed) {
    let a = typeof seed === 'number' ? seed : hash(seed);
    return function () {
      a = (a + 0x6d2b79f5) | 0;
      let t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }
  const pick = (r, arr) => arr[Math.floor(r() * arr.length)];
  const int = (r, a, b) => a + Math.floor(r() * (b - a + 1));
  const pad = (n) => String(n).padStart(2, '0');

  /* ---------------- campus data ---------------- */
  const BUILDINGS = {
    ECSS: { name: 'Engineering & Computer Science South', rooms: ['2.306', '2.410', '2.412', '3.910', '4.619'] },
    JSOM: { name: 'Naveen Jindal School of Management', rooms: ['1.118', '2.106', '11.210', '12.202'] },
    SCI: { name: 'Science Building', rooms: ['1.210', '2.235', '3.250'] },
    GR: { name: 'Green Hall', rooms: ['2.530', '3.302', '4.301'] },
    FN: { name: 'Founders North', rooms: ['2.102', '2.104'] },
  };
  const COURSES = [
    ['CS 3345', 'Data Structures and Algorithmic Analysis'], ['CS 4337', 'Programming Language Paradigms'], ['SE 3354', 'Software Engineering'],
    ['MATH 2418', 'Linear Algebra'], ['PHYS 2325', 'Mechanics'], ['STAT 3360', 'Probability and Statistics'],
    ['ACCT 2301', 'Introductory Financial Accounting'], ['ECON 2301', 'Principles of Macroeconomics'], ['CS 4349', 'Advanced Algorithm Design'],
  ];
  const INSTRUCTORS = ['Dr. A. Patel', 'Dr. M. Chen', 'Dr. L. Okafor', 'Prof. R. Alvarez', 'Dr. S. Kim', 'Dr. J. Novak', 'Prof. E. Brooks'];
  const EVENTS = [
    ['Hackathon Kickoff', 'Student Life'], ['Career Fair Prep Workshop', 'Career'], ['Research Seminar: Graph Neural Networks', 'Research'],
    ['Student Government Meeting', 'Student Life'], ['Guest Lecture: Cloud Security', 'Academic'], ['Study Group: Calculus II', 'Academic'],
    ['Thesis Defense', 'Research'], ['Alumni Networking Night', 'Career'], ['Jazz Ensemble Rehearsal', 'Arts'], ['Intramural Basketball Signups', 'Athletics'],
  ];
  const EVENT_TITLES = EVENTS.map((e) => e[0]);
  const ORGS = ['Career Center', 'Computer Science Dept.', 'Student Government', 'Graduate School', 'ACM Student Chapter', 'Office of Research'];

  /* ---------------- dates ---------------- */
  function today() { const d = new Date(); return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`; }
  // default for {date}: today, or the next Monday on a weekend, so the first click shows a full day
  function schoolDay() {
    const d = new Date();
    while ([0, 6].includes(d.getDay())) d.setDate(d.getDate() + 1);
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
  }
  function validDate(s) {
    const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(s || '');
    if (!m) return false;
    const d = new Date(Date.UTC(+m[1], +m[2] - 1, +m[3]));
    return d.getUTCMonth() === +m[2] - 1;
  }
  const iso = (y, m, d) => `${y}-${pad(m)}-${pad(d)}`;
  const at = (date, mins) => `${date}T${pad(Math.floor(mins / 60))}:${pad(mins % 60)}:00-06:00`;
  const clock = (mins) => `${pad(Math.floor(mins / 60))}:${pad(mins % 60)}`;
  function nthWeekday(y, m, weekday, n) { // n = -1 → last
    if (n > 0) { const first = new Date(Date.UTC(y, m - 1, 1)).getUTCDay(); return 1 + ((weekday - first + 7) % 7) + (n - 1) * 7; }
    const last = new Date(Date.UTC(y, m, 0)); return last.getUTCDate() - ((last.getUTCDay() - weekday + 7) % 7);
  }
  const weekday = (date) => new Date(date + 'T12:00:00Z').getUTCDay();

  /* ---------------- errors ---------------- */
  const err = (status, message, extra) => ({ status, body: { error: message, ...extra } });
  function checkDate(date) { return validDate(date) ? null : err(400, 'date must be a real date in YYYY-MM-DD format', { example: today() }); }
  function checkBuilding(b) {
    if (!b) return null;
    return BUILDINGS[b.toUpperCase()] ? null : err(404, `Unknown building "${b}"`, { buildings: Object.keys(BUILDINGS) });
  }

  /* ---------------- academic calendars ---------------- */
  function termIdFor(date) {
    const [y, m] = date.split('-').map(Number);
    return `${y}-${m <= 5 ? 'spring' : m <= 7 ? 'summer' : 'fall'}`;
  }
  function academicCalendar(id) {
    const m = /^(\d{4})-(spring|summer|fall)$/.exec(String(id || '').toLowerCase());
    if (!m) return err(404, `No academic calendar "${id}"`, { format: 'YYYY-spring | YYYY-summer | YYYY-fall', example: termIdFor(today()) });
    const y = +m[1], term = m[2];
    let body;
    if (term === 'fall') {
      const thanksgiving = nthWeekday(y, 11, 4, 4);
      body = {
        starts_on: iso(y, 8, nthWeekday(y, 8, 1, 4)), ends_on: iso(y, 12, 17), census_date: iso(y, 9, 9), last_day_to_withdraw: iso(y, 10, 28),
        holidays: [{ name: 'Labor Day', date: iso(y, 9, nthWeekday(y, 9, 1, 1)) }, { name: 'Thanksgiving Break', starts_on: iso(y, 11, thanksgiving - 3), ends_on: iso(y, 11, thanksgiving + 2) }],
        final_exams: { starts_on: iso(y, 12, 10), ends_on: iso(y, 12, 17) },
      };
    } else if (term === 'spring') {
      body = {
        starts_on: iso(y, 1, nthWeekday(y, 1, 1, 3) + 1), ends_on: iso(y, 5, 14), census_date: iso(y, 2, 5), last_day_to_withdraw: iso(y, 4, 2),
        holidays: [{ name: 'Martin Luther King Jr. Day', date: iso(y, 1, nthWeekday(y, 1, 1, 3)) }, { name: 'Spring Break', starts_on: iso(y, 3, nthWeekday(y, 3, 1, 2)), ends_on: iso(y, 3, nthWeekday(y, 3, 1, 2) + 6) }],
        final_exams: { starts_on: iso(y, 5, 7), ends_on: iso(y, 5, 14) },
      };
    } else {
      body = {
        starts_on: iso(y, 5, nthWeekday(y, 5, 1, -1) + 1), ends_on: iso(y, 8, 8), census_date: iso(y, 6, 3), last_day_to_withdraw: iso(y, 7, 10),
        holidays: [{ name: 'Memorial Day', date: iso(y, 5, nthWeekday(y, 5, 1, -1)) }, { name: 'Independence Day', date: iso(y, 7, 4) }],
        final_exams: { starts_on: iso(y, 8, 4), ends_on: iso(y, 8, 8) },
      };
    }
    return { status: 200, body: { id: `${y}-${term}`, name: `${term[0].toUpperCase()}${term.slice(1)} ${y}`, ...body, is_current: termIdFor(today()) === `${y}-${term}` } };
  }

  /* ---------------- generators ---------------- */
  function rooms(r, building, room) {
    const b = building ? building.toUpperCase() : pick(r, Object.keys(BUILDINGS));
    return { b, room: room || pick(r, BUILDINGS[b].rooms) };
  }

  function reservation(r, date, building, room, i) {
    const loc = rooms(r, building, room);
    const type = pick(r, ['Class', 'Class', 'Class', 'Exam', 'Meeting', 'Event']);
    const start = 8 * 60 + int(r, 0, 22) * 30, len = pick(r, [50, 75, 90, 120]);
    const course = pick(r, COURSES);
    return {
      id: `AST-${date.replace(/-/g, '')}-${String(hash(date + loc.b + loc.room + i) % 9000 + 1000)}`,
      building: loc.b, room: loc.room,
      title: type === 'Class' || type === 'Exam' ? `${course[0]}.${pad(int(r, 1, 6))}0 ${course[1]}${type === 'Exam' ? ' (Exam)' : ''}` : pick(r, EVENT_TITLES),
      type, start: at(date, start), end: at(date, start + len),
      capacity: int(r, 3, 12) * 10, status: pick(r, ['Confirmed', 'Confirmed', 'Confirmed', 'Tentative']),
    };
  }

  // Generate the day's list once, then filter, so narrower endpoints return a subset of wider ones.
  function astraDay(date) {
    const r = rng('astra' + date), n = weekday(date) === 0 ? int(r, 1, 3) : int(r, 10, 16);
    return Array.from({ length: n }, (_, i) => reservation(r, date, null, null, i)).sort((a, b) => a.start.localeCompare(b.start));
  }
  function narrow(list, date, building, room, make) {
    let out = list;
    if (building) out = out.filter((x) => x.building === building.toUpperCase());
    if (room) out = out.filter((x) => x.room === room);
    if (!out.length && (building || room) && weekday(date) !== 0) {
      const r = rng(`${date}|${building}|${room}`);
      out = Array.from({ length: int(r, 1, 3) }, (_, i) => make(r, date, building, room, 100 + i)).sort((a, b) => a.start.localeCompare(b.start));
    }
    return out;
  }

  function calendarEvent(r, date, building, room, i) {
    const loc = rooms(r, building, room);
    const start = 9 * 60 + int(r, 0, 20) * 30, len = pick(r, [60, 90, 120, 180]);
    const id = `EVT-${String(hash(date + loc.b + loc.room + i) % 90000 + 10000)}`;
    return {
      ...(([title, category]) => ({ id, title, category }))(pick(r, EVENTS)),
      start: at(date, start), end: at(date, start + len), all_day: false,
      location: { building: loc.b, room: loc.room, building_name: BUILDINGS[loc.b].name },
      organizer: pick(r, ORGS), rsvp_required: r() < 0.4,
      url: `https://calendar.example.edu/event/${id.toLowerCase()}`,
    };
  }
  function calendarDay(date) {
    const r = rng('calendar' + date), n = int(r, 4, 9);
    return Array.from({ length: n }, (_, i) => calendarEvent(r, date, null, null, i)).sort((a, b) => a.start.localeCompare(b.start));
  }

  function mergedEvents(date, building, room) {
    const fromAstra = narrow(astraDay(date), date, building, room, reservation).filter((x) => x.type !== 'Class')
      .map((x) => ({ id: x.id, title: x.title, source: 'astra', type: x.type, start: x.start, end: x.end, building: x.building, room: x.room }));
    const fromCal = narrow(calendarDay(date), date, building, null, calendarEvent)
      .filter((x) => !room || x.location.room === room)
      .map((x) => ({ id: x.id, title: x.title, source: 'calendar', type: x.category, start: x.start, end: x.end, building: x.location.building, room: x.location.room }));
    return [...fromAstra, ...fromCal].sort((a, b) => a.start.localeCompare(b.start));
  }

  function sections(date, building, room) {
    const r = rng(`sections|${date}|${building}|${room}`);
    const days = [1, 3].includes(weekday(date)) ? 'MW' : [2, 4].includes(weekday(date)) ? 'TR' : weekday(date) === 5 ? 'F' : null;
    if (!days) return [];
    return Array.from({ length: int(r, 2, 4) }, (_, i) => {
      const [code, title] = pick(r, COURSES), start = 8 * 60 + 30 + i * 150 + int(r, 0, 1) * 15, cap = int(r, 4, 12) * 10;
      return {
        section: `${code}.${pad(int(r, 0, 5))}${int(r, 1, 9)}`, course_title: title, instructor: pick(r, INSTRUCTORS),
        days, start_time: clock(start), end_time: clock(start + (days === 'MW' || days === 'F' ? 75 : 75)),
        enrolled: int(r, Math.floor(cap * 0.5), cap), capacity: cap, modality: 'In person',
        term: termIdFor(date), building: building.toUpperCase(), room,
      };
    });
  }

  /* ---------------- endpoint spec ---------------- */
  const P = {
    date: { name: 'date', example: schoolDay, description: 'Day to look up (YYYY-MM-DD)' },
    building: { name: 'building', example: () => 'ECSS', description: `Building code: ${Object.keys(BUILDINGS).join(', ')}` },
    room: { name: 'room', example: () => '2.410', description: 'Room number, e.g. 2.410' },
    id: { name: 'id', example: () => termIdFor(today()), description: 'Term id, e.g. 2026-fall or 2027-spring' },
  };
  const ok = (body) => ({ status: 200, body });
  const guard = (p, fn) => checkDate(p.date) || checkBuilding(p.building) || fn();

  const SPEC = [
    {
      tag: 'Academic Calendars', description: 'Term dates, holidays and deadlines',
      endpoints: [
        { method: 'GET', path: '/academicCalendars/current', summary: 'The current academic term', params: [], run: () => academicCalendar(termIdFor(today())) },
        { method: 'GET', path: '/academicCalendars/{id}', summary: 'One academic term by id', params: [P.id], run: (p) => academicCalendar(p.id) },
      ],
    },
    {
      tag: 'Events', description: 'Room reservations (Astra), the campus calendar, and both combined',
      endpoints: [
        ...[['', []], ['/{building}', [P.building]], ['/{building}/{room}', [P.building, P.room]]].map(([suffix, extra]) => ({
          method: 'GET', path: `/astra/{date}${suffix}`, summary: `Room reservations${extra.length === 2 ? ' for a room' : extra.length ? ' in a building' : ''} from Astra`, params: [P.date, ...extra],
          run: (p) => guard(p, () => { const data = narrow(astraDay(p.date), p.date, p.building, p.room, reservation); return ok({ date: p.date, source: 'astra', count: data.length, reservations: data }); }),
        })),
        ...[['', []], ['/{building}', [P.building]], ['/{building}/{room}', [P.building, P.room]]].map(([suffix, extra]) => ({
          method: 'GET', path: `/calendar/{date}${suffix}`, summary: `Campus calendar events${extra.length === 2 ? ' in a room' : extra.length ? ' in a building' : ''}`, params: [P.date, ...extra],
          run: (p) => guard(p, () => {
            let data = narrow(calendarDay(p.date), p.date, null, null, calendarEvent);
            if (p.building) data = data.filter((x) => x.location.building === p.building.toUpperCase());
            if (p.room) data = data.filter((x) => x.location.room === p.room);
            if (!data.length && p.building && weekday(p.date) !== 0) { const r = rng(`cal|${p.date}|${p.building}|${p.room}`); data = [calendarEvent(r, p.date, p.building, p.room, 1)]; }
            return ok({ date: p.date, count: data.length, events: data });
          }),
        })),
        ...[['', []], ['/{building}', [P.building]], ['/{building}/{room}', [P.building, P.room]]].map(([suffix, extra]) => ({
          method: 'GET', path: `/events/{date}${suffix}`, summary: `Everything happening${extra.length === 2 ? ' in a room' : extra.length ? ' in a building' : ''} (Astra + calendar)`, params: [P.date, ...extra],
          run: (p) => guard(p, () => { const data = mergedEvents(p.date, p.building, p.room); return ok({ date: p.date, count: data.length, events: data }); }),
        })),
        {
          method: 'GET', path: '/events/{date}/{building}/{room}/sections', summary: 'Class sections meeting in a room that day', params: [P.date, P.building, P.room],
          run: (p) => guard(p, () => { const data = sections(p.date, p.building, p.room); return ok({ date: p.date, building: p.building.toUpperCase(), room: p.room, count: data.length, sections: data }); }),
        },
      ],
    },
  ];

  return {
    base: 'https://api.facade.local/v1',
    spec: SPEC,
    // Fake a network round trip so the page behaves like a real API.
    call(endpoint, params) {
      const result = endpoint.run(params);
      const ms = 40 + (hash(endpoint.path + JSON.stringify(params)) % 180);
      return new Promise((resolve) => setTimeout(() => resolve({ ...result, ms }), 250 + ms));
    },
  };
})();
