# API for http://127.0.0.1:65355

Designed by Nemotron (`nvidia/nemotron-3.5-super-vl-120b-a12b`) from 62 extracted records. Reads come from the database (SpacetimeDB); writes are performed live on the legacy site by the Operator and verified.

| Method | Path | Source | What it does |
|---|---|---|---|
| GET | `/patients` | database | Returns a paginated list of patients with optional filters by name, date of birth, phone, and insurance ID. |
| GET | `/patients/{id}` | database | Returns a single patient by its legacy identifier. |
| GET | `/patients/search` | database | Searches patients by free-text query across name, phone, and insurance ID. |
| POST | `/patients` | legacy | Creates a new patient record using the legacy patient new form. |
| PATCH | `/patients/{id}` | legacy | Updates an existing patient record using the legacy patient edit form. |
| GET | `/appointments` | database | Returns a paginated list of appointments with optional filters by date, time, patient, provider, status, and reason. |
| GET | `/appointments/{id}` | database | Returns a single appointment by its legacy identifier. |
| GET | `/appointments/search` | database | Searches appointments by free-text query across reason. |
| POST | `/appointments` | legacy | Creates a new appointment record using the legacy appointment new form. |
| PATCH | `/appointments/{id}` | legacy | Updates an existing appointment record using the legacy appointment edit form. |

## Patient

35 records. Fields: `last_name` (string), `first_name` (string), `dob` (date), `phone` (string), `insurance_id` (string)

### `GET /patients`

Returns a paginated list of patients with optional filters by name, date of birth, phone, and insurance ID.

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

Returns a single patient by its legacy identifier.

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

Searches patients by free-text query across name, phone, and insurance ID.

| Name | In | Type | Meaning | Required |
|---|---|---|---|---|
| `q` | query | string | searches `last_name`, `first_name`, `phone`, `insurance_id` |  |
| `limit` | query | integer | max rows (default 50) |  |
| `offset` | query | integer | skip rows |  |

Example request:

```http
GET /patients/search?q=ins-80239&limit=3
```

Response (real data):

```json
{
  "total": 1,
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
    }
  ]
}
```

### `POST /patients`

Creates a new patient record using the legacy patient new form.

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

Updates an existing patient record using the legacy patient edit form.

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

Returns a paginated list of appointments with optional filters by date, time, patient, provider, status, and reason.

| Name | In | Type | Meaning | Required |
|---|---|---|---|---|
| `min_date` | query | date | `date` ≥ |  |
| `max_date` | query | date | `date` ≤ |  |
| `time` | query | string | `time` equals: `8:00`, `9:00`, `10:00`, `10:30`, `11:00`, `11:30`, `12:00`, `13:00` … |  |
| `patient_id` | query | string | `patient_id` equals |  |
| `provider` | query | string | `provider` equals: `Dr. Lee`, `Dr. Patel`, `Hyg. Kim` |  |
| `status` | query | string | `status` equals: `Booked`, `Completed`, `No-show`, `Cancelled` |  |
| `reason` | query | string | `reason` equals: `Crown fitting`, `Checkup`, `X-rays`, `Cleaning`, `Filling` |  |
| `limit` | query | integer | max rows (default 50) |  |
| `offset` | query | integer | skip rows |  |
| `sort` | query | string | sort field, `-` = descending: `date`, `-date` |  |

Example request:

```http
GET /appointments?min_date=2026-03-05&time=8%3A00&limit=3
```

Response (real data):

```json
{
  "total": 1,
  "limit": 3,
  "offset": 0,
  "items": [
    {
      "legacy_id": "1017",
      "date": "2026-04-12",
      "time": "8:00",
      "patient": "Lopez, Omar",
      "patient_id": "18",
      "provider": "Dr. Patel",
      "status": "No-show",
      "reason": "Checkup"
    }
  ]
}
```

### `GET /appointments/{id}`

Returns a single appointment by its legacy identifier.

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

### `GET /appointments/search`

Searches appointments by free-text query across reason.

| Name | In | Type | Meaning | Required |
|---|---|---|---|---|
| `q` | query | string | searches `reason` |  |
| `limit` | query | integer | max rows (default 50) |  |
| `offset` | query | integer | skip rows |  |

Example request:

```http
GET /appointments/search?q=cleaning&limit=3
```

Response (real data):

```json
{
  "total": 4,
  "limit": 3,
  "offset": 0,
  "items": [
    {
      "legacy_id": "1004",
      "date": "2026-02-03",
      "time": "10:00",
      "patient": "Young, Zoe",
      "patient_id": "15",
      "provider": "Hyg. Kim",
      "status": "Completed",
      "reason": "Cleaning"
    },
    {
      "legacy_id": "1007",
      "date": "2026-04-13",
      "time": "14:30",
      "patient": "Miller, Joy",
      "patient_id": "7",
      "provider": "Dr. Patel",
      "status": "Cancelled",
      "reason": "Cleaning"
    },
    "... 1 more"
  ]
}
```

### `POST /appointments`

Creates a new appointment record using the legacy appointment new form.

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

Updates an existing appointment record using the legacy appointment edit form.

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

