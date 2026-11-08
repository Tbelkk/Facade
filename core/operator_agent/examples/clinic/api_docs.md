# API for http://127.0.0.1:65355

Designed by Nemotron (`nvidia/nemotron-3.5-super-vl-120b-a12b`) from 62 extracted records. Reads come from the database (SpacetimeDB); writes are performed live on the legacy site by the Operator and verified.

| Method | Path | Source | What it does |
|---|---|---|---|
| GET | `/patients` | database | List patients with optional filters by name, phone, insurance ID, date of birth range, pagination, and sort. |
| GET | `/patients/{id}` | database | Get a single patient by legacy ID. |
| GET | `/patients/search` | database | Search patients by free-text query across name fields. |
| POST | `/patients` | legacy | Create a new patient using the patient new form. |
| PATCH | `/patients/{id}` | legacy | Update an existing patient using the patient edit form. |
| GET | `/appointments` | database | List appointments with optional filters by date range, time, patient, provider, status, reason, pagination, and sort. |
| GET | `/appointments/{id}` | database | Get a single appointment by legacy ID. |
| POST | `/appointments` | legacy | Create a new appointment using the appointment new form. |
| PATCH | `/appointments/{id}` | legacy | Update an existing appointment using the appointment edit form. |

## Patient

35 records. Fields: `last_name` (string), `first_name` (string), `dob` (date), `phone` (string), `insurance_id` (string)

### `GET /patients`

List patients with optional filters by name, phone, insurance ID, date of birth range, pagination, and sort.

| Name | In | Type | Meaning | Required |
|---|---|---|---|---|
| `last_name` | query | string | `last_name` contains (case-insensitive) |  |
| `first_name` | query | string | `first_name` contains (case-insensitive) |  |
| `phone` | query | string | `phone` contains (case-insensitive) |  |
| `insurance_id` | query | string | `insurance_id` contains (case-insensitive) |  |
| `min_dob` | query | date | `dob` ≥ |  |
| `max_dob` | query | date | `dob` ≤ |  |
| `limit` | query | integer | max rows (default 50) |  |
| `offset` | query | integer | skip rows |  |
| `sort` | query | string | sort field, `-` = descending: `dob`, `-dob` |  |

Example request:

```http
GET /patients?min_dob=1966-03-25&limit=3
```

Response (real data):

```json
{
  "total": 18,
  "limit": 3,
  "offset": 0,
  "items": [
    {
      "legacy_id": "2",
      "last_name": "Johnson",
      "first_name": "Raj",
      "dob": "1981-01-03",
      "phone": "(214) 555-1037",
      "insurance_id": "INS-80239"
    },
    {
      "legacy_id": "4",
      "last_name": "Garcia",
      "first_name": "Wei",
      "dob": "1998-09-07",
      "phone": "(214) 555-1111",
      "insurance_id": "INS-14914"
    },
    "... 1 more"
  ]
}
```

### `GET /patients/{id}`

Get a single patient by legacy ID.

| Name | In | Type | Meaning | Required |
|---|---|---|---|---|
| `id` | path | string | legacy id | yes |

Example request:

```http
GET /patients/1
```

Response (real data):

```json
{
  "legacy_id": "1",
  "last_name": "Smith",
  "first_name": "John",
  "dob": "1960-03-13",
  "phone": null,
  "insurance_id": null
}
```

### `GET /patients/search`

Search patients by free-text query across name fields.

| Name | In | Type | Meaning | Required |
|---|---|---|---|---|
| `q` | query | string | searches `last_name`, `first_name` | yes |
| `limit` | query | integer | max rows (default 50) |  |
| `offset` | query | integer | skip rows |  |

Example request:

```http
GET /patients/search?q=johnson&limit=3
```

Response (real data):

```json
{
  "total": 2,
  "limit": 3,
  "offset": 0,
  "items": [
    {
      "legacy_id": "2",
      "last_name": "Johnson",
      "first_name": "Raj",
      "dob": "1981-01-03",
      "phone": "(214) 555-1037",
      "insurance_id": "INS-80239"
    },
    {
      "legacy_id": "32",
      "last_name": "Johnson",
      "first_name": "Bob",
      "dob": "1957-08-23",
      "phone": "(214) 555-2147",
      "insurance_id": "INS-97051"
    }
  ]
}
```

### `POST /patients`

Create a new patient using the patient new form.

Performed on the legacy site through form `patient_new`: 

| Name | In | Type | Meaning | Required |
|---|---|---|---|---|
| `last_name` | body | string | sets `last_name` | yes |
| `first_name` | body | string | sets `first_name` |  |
| `dob` | body | date | sets `dob` |  |
| `phone` | body | string | sets `phone` |  |
| `insurance_id` | body | string | sets `insurance_id` |  |

Example request:

```http
POST /patients
```
```json
{
  "last_name": "Smith",
  "first_name": "John",
  "dob": "1960-03-13"
}
```

Response (illustration):

```json
{
  "status": "done",
  "verified": true,
  "result": {
    "entity": "Patient",
    "legacy_id": "1",
    "data": {
      "last_name": "Smith",
      "first_name": "John",
      "dob": "1960-03-13"
    }
  },
  "error": null
}
```

### `PATCH /patients/{id}`

Update an existing patient using the patient edit form.

Performed on the legacy site through form `patient_edit`: 

| Name | In | Type | Meaning | Required |
|---|---|---|---|---|
| `id` | path | string | legacy id | yes |
| `last_name` | body | string | sets `last_name` | yes |
| `first_name` | body | string | sets `first_name` |  |
| `dob` | body | date | sets `dob` |  |
| `phone` | body | string | sets `phone` |  |
| `insurance_id` | body | string | sets `insurance_id` |  |

Example request:

```http
PATCH /patients/1
```
```json
{
  "last_name": "Smith",
  "first_name": "John",
  "dob": "1960-03-13"
}
```

Response (illustration):

```json
{
  "status": "done",
  "verified": true,
  "result": {
    "entity": "Patient",
    "legacy_id": "1",
    "data": {
      "last_name": "Smith",
      "first_name": "John",
      "dob": "1960-03-13"
    }
  },
  "error": null
}
```


## Appointment

27 records. Fields: `date` (date), `time` (string), `patient` (string), `patient_id` (ref → Patient), `provider` (enum), `status` (enum), `reason` (string)

### `GET /appointments`

List appointments with optional filters by date range, time, patient, provider, status, reason, pagination, and sort.

| Name | In | Type | Meaning | Required |
|---|---|---|---|---|
| `min_date` | query | date | `date` ≥ |  |
| `max_date` | query | date | `date` ≤ |  |
| `time` | query | string | `time` equals: `8:00`, `9:00`, `10:00`, `10:30`, `11:00`, `11:30`, `13:00`, `13:30` … |  |
| `patient_id` | query | string | `patient_id` equals |  |
| `provider` | query | string | `provider` equals: `Dr. Lee`, `Dr. Patel`, `Hyg. Kim` |  |
| `status` | query | string | `status` equals: `Booked`, `Completed`, `No-show`, `Cancelled` |  |
| `reason` | query | string | `reason` equals: `Crown fitting`, `Checkup`, `X-rays`, `Cleaning`, `Filling` |  |
| `limit` | query | integer | max rows (default 50) |  |
| `offset` | query | integer | skip rows |  |
| `sort` | query | string | sort field, `-` = descending: `date`, `-date` |  |

Example request:

```http
GET /appointments?min_date=2026-03-05&time=13%3A00&limit=3
```

Response (real data):

```json
{
  "total": 3,
  "limit": 3,
  "offset": 0,
  "items": [
    {
      "legacy_id": "1006",
      "date": "2026-03-20",
      "time": "13:00",
      "patient": "Lee, Zoe",
      "patient_id": "33",
      "provider": "Hyg. Kim",
      "status": "Booked",
      "reason": "Crown fitting"
    },
    {
      "legacy_id": "1015",
      "date": "2026-03-06",
      "time": "13:00",
      "patient": "Smith, John",
      "patient_id": "35",
      "provider": "Hyg. Kim",
      "status": "No-show",
      "reason": null
    },
    "... 1 more"
  ]
}
```

### `GET /appointments/{id}`

Get a single appointment by legacy ID.

| Name | In | Type | Meaning | Required |
|---|---|---|---|---|
| `id` | path | string | legacy id | yes |

Example request:

```http
GET /appointments/1000
```

Response (real data):

```json
{
  "legacy_id": "1000",
  "date": "2026-04-10",
  "time": "14:30",
  "patient": "Johnson, Raj",
  "patient_id": "2",
  "provider": "Dr. Patel",
  "status": "No-show",
  "reason": "Checkup"
}
```

### `POST /appointments`

Create a new appointment using the appointment new form.

Performed on the legacy site through form `appointment_new`: 

| Name | In | Type | Meaning | Required |
|---|---|---|---|---|
| `date` | body | date | sets `date` | yes |
| `time` | body | string | sets `time` | yes |
| `patient_id` | body | string | sets `patient_id` | yes |
| `provider` | body | string | sets `provider` |  |
| `status` | body | string | sets `status` |  |
| `reason` | body | string | sets `reason` |  |

Example request:

```http
POST /appointments
```
```json
{
  "date": "2026-04-10",
  "time": "14:30",
  "patient_id": "2",
  "provider": "Dr. Patel",
  "status": "No-show",
  "reason": "Checkup"
}
```

Response (illustration):

```json
{
  "status": "done",
  "verified": true,
  "result": {
    "entity": "Appointment",
    "legacy_id": "1000",
    "data": {
      "date": "2026-04-10",
      "time": "14:30",
      "patient_id": "2",
      "provider": "Dr. Patel",
      "status": "No-show",
      "reason": "Checkup"
    }
  },
  "error": null
}
```

### `PATCH /appointments/{id}`

Update an existing appointment using the appointment edit form.

Performed on the legacy site through form `appointment_edit`: 

| Name | In | Type | Meaning | Required |
|---|---|---|---|---|
| `id` | path | string | legacy id | yes |
| `date` | body | date | sets `date` | yes |
| `time` | body | string | sets `time` | yes |
| `patient_id` | body | string | sets `patient_id` | yes |
| `provider` | body | string | sets `provider` |  |
| `status` | body | string | sets `status` |  |
| `reason` | body | string | sets `reason` |  |

Example request:

```http
PATCH /appointments/1000
```
```json
{
  "date": "2026-04-10",
  "time": "14:30",
  "patient_id": "2",
  "provider": "Dr. Patel",
  "status": "No-show",
  "reason": "Checkup"
}
```

Response (illustration):

```json
{
  "status": "done",
  "verified": true,
  "result": {
    "entity": "Appointment",
    "legacy_id": "1000",
    "data": {
      "date": "2026-04-10",
      "time": "14:30",
      "patient_id": "2",
      "provider": "Dr. Patel",
      "status": "No-show",
      "reason": "Checkup"
    }
  },
  "error": null
}
```

