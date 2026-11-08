# API for https://personal.utdallas.edu/~John.cole/

Designed by Nemotron (`nvidia/nemotron-3-nano-omni-30b-a3b-reasoning`) from 29 extracted records. Reads come from the database (SpacetimeDB); writes are performed live on the legacy site by the Operator and verified.

The checker found 19 problem(s) in the first design; Nemotron fixed them in one round (19 left, 6 endpoint(s) dropped).

| Method | Path | Source | What it does |
|---|---|---|---|
| GET | `/professors/{id}` | database | Retrieve a single professor by its legacy ID. |
| GET | `/facultymembers/{id}` | database | Retrieve a single faculty member by its legacy ID. |
| GET | `/programmingtips/{id}` | database | Retrieve a single programming tip by its legacy ID. |
| GET | `/databaseconnections` | database | List database connection records (currently none). |
| GET | `/databaseconnections/{id}` | database | Retrieve a single database connection by its legacy ID. |
| GET | `/fibonacci` | database | List Fibonacci records (currently none). |
| GET | `/fibonacci/{id}` | database | Retrieve a single Fibonacci record by its legacy ID. |
| GET | `/professors` | database | List Professor records, with filters |
| GET | `/faculty_members` | database | List FacultyMember records, with filters |
| GET | `/programming_tips` | database | List ProgrammingTip records, with filters |

## Professor

18 records. Fields: `class_list` (string), `welcome_message` (string), `professor_name` (string), `professor_title` (string), `photo_url` (string), `department_url` (string), `university_url` (string), `note` (string), `note_detail` (string)

_No form was seen for this entity on the legacy site, so it has no write endpoints._

### `GET /professors/{id}`

Retrieve a single professor by its legacy ID.

| Name | In | Type | Meaning | Required |
|---|---|---|---|---|
| `id` | path | string | legacy id | yes |

Example request:

```http
GET /professors/~John.cole
```

Response (real data):

```json
{
  "legacy_id": "~John.cole",
  "class_list": "Classes Office Notes for Students Links Announcements Projects Reading List Teaching Philosophy ACM at UTD *",
  "welcome_message": "John Cole Welcome to my online home. I'm a Professor of Instruction in the Computer Science Department here at the University of Texas at Dallas. I taught part-time at Collin County Community College "
}
```

### `GET /professors`

List Professor records, with filters

| Name | In | Type | Meaning | Required |
|---|---|---|---|---|
| `class_list` | query | string | `class_list` equals: `Classes Office Notes for Students Links Announcements Projects Reading List Teaching Philosophy ACM at UTD *` |  |
| `welcome_message` | query | string | `welcome_message` equals: `John Cole Welcome to my online home. I'm a Professor of Instruction in the Computer Science Department here at the University of Texas at Dallas. I taught part-time at Collin County Community College ` |  |
| `note_detail` | query | string | `note_detail` equals: `Academic Integrity. All assignments, unless explicitly stated in writing in the assignment, are individual. That is, you are to turn in your own work. You are not to work in a group, then each of you `, `Robot built for the workshop at PES University.`, `Home Monitoring and Control system running at my house. This uses a combination of Arduino and Raspberry Pi boards.`, `Android Pong Game. This is the first app I have released to the Google Play Store. It's available free, and was done in part as a UTD project. You can find it using my name and "Pong."`, `Section 052: Tuesday/Thursday from 8:00 AM to 8:50 AM 8-week session from January 20 to March 9, 2026 Section 051: Tuesday/Thursday from 9:00 AM to 9:50 AM 8-week session from January 20 to March 9, 2`, `Room: SCI 1.220`, `Last update: 5/15/2026`, `Schedule for Section 051 & 052 Schedule for Section 091 & 092` |  |
| `limit` | query | integer | max rows (default 50) |  |
| `offset` | query | integer | skip rows |  |

Example request:

```http
GET /professors?class_list=Classes+Office+Notes+for+Students+Links+Announcements+Projects+Reading+List+Teaching+Philosophy+ACM+at+UTD+%2A&limit=3
```

Response (real data):

```json
{
  "total": 1,
  "limit": 3,
  "offset": 0,
  "items": [
    {
      "legacy_id": "~John.cole",
      "class_list": "Classes Office Notes for Students Links Announcements Projects Reading List Teaching Philosophy ACM at UTD *",
      "welcome_message": "John Cole Welcome to my online home. I'm a Professor of Instruction in the Computer Science Department here at the University of Texas at Dallas. I taught part-time at Collin County Community College "
    }
  ]
}
```


## FacultyMember

1 records. Fields: `navigation_items` (string), `welcome_message` (string)

_No form was seen for this entity on the legacy site, so it has no write endpoints._

### `GET /facultymembers/{id}`

Retrieve a single faculty member by its legacy ID.

| Name | In | Type | Meaning | Required |
|---|---|---|---|---|
| `id` | path | string | legacy id | yes |

Example request:

```http
GET /facultymembers/d2f00fffdcc2
```

Response (real data):

```json
{
  "legacy_id": "d2f00fffdcc2",
  "navigation_items": "Classes Office Notes for Students Links Announcements Projects Reading List Teaching Philosophy ACM at UTD *",
  "welcome_message": "John Cole Welcome to my online home. I'm a Professor of Instruction in the Computer Science Department here at the University of Texas at Dallas. I taught part-time at Collin County Community College "
}
```

### `GET /faculty_members`

List FacultyMember records, with filters

| Name | In | Type | Meaning | Required |
|---|---|---|---|---|
| `limit` | query | integer | max rows (default 50) |  |
| `offset` | query | integer | skip rows |  |

Example request:

```http
GET /faculty_members?limit=3
```

Response (real data):

```json
{
  "total": 1,
  "limit": 3,
  "offset": 0,
  "items": [
    {
      "legacy_id": "d2f00fffdcc2",
      "navigation_items": "Classes Office Notes for Students Links Announcements Projects Reading List Teaching Philosophy ACM at UTD *",
      "welcome_message": "John Cole Welcome to my online home. I'm a Professor of Instruction in the Computer Science Department here at the University of Texas at Dallas. I taught part-time at Collin County Community College "
    }
  ]
}
```


## ProgrammingTip

10 records. Fields: `title` (string), `description` (string), `author` (string), `university` (string), `date` (date)

_No form was seen for this entity on the legacy site, so it has no write endpoints._

### `GET /programmingtips/{id}`

Retrieve a single programming tip by its legacy ID.

| Name | In | Type | Meaning | Required |
|---|---|---|---|---|
| `id` | path | string | legacy id | yes |

Example request:

```http
GET /programmingtips/AndroidFileIO.html
```

Response (real data):

```json
{
  "legacy_id": "AndroidFileIO.html",
  "title": "Android Programming Android File I/O examples Android File I/O problem and solution Code snippets for animation using a thread on a timer Low-Pass Filter Array Adapter for ListView"
}
```

### `GET /programming_tips`

List ProgrammingTip records, with filters

| Name | In | Type | Meaning | Required |
|---|---|---|---|---|
| `limit` | query | integer | max rows (default 50) |  |
| `offset` | query | integer | skip rows |  |
| `sort` | query | string | sort field, `-` = descending: `date`, `-date` |  |

Example request:

```http
GET /programming_tips?limit=3
```

Response (real data):

```json
{
  "total": 10,
  "limit": 3,
  "offset": 0,
  "items": [
    {
      "legacy_id": "AndroidFileIO.html",
      "title": "Android Programming Android File I/O examples Android File I/O problem and solution Code snippets for animation using a thread on a timer Low-Pass Filter Array Adapter for ListView"
    },
    {
      "legacy_id": "BinaryIO-CPP.html",
      "title": "Database Programming C++ Binary File I/O Sample C++ Random-Access File I/O Sample Java Random-Access I/O Sample Connect to a MS SQL Server database from Java Connect to a MySQL database from Java"
    },
    "... 1 more"
  ]
}
```


## DatabaseConnection

0 records. Fields: 

_No form was seen for this entity on the legacy site, so it has no write endpoints._

### `GET /databaseconnections`

List database connection records (currently none).

| Name | In | Type | Meaning | Required |
|---|---|---|---|---|
| `limit` | query | integer | max rows (default 50) |  |
| `offset` | query | integer | skip rows |  |

Example request:

```http
GET /databaseconnections?limit=3
```

Response (real data):

```json
{
  "total": 0,
  "limit": 3,
  "offset": 0,
  "items": []
}
```

### `GET /databaseconnections/{id}`

Retrieve a single database connection by its legacy ID.

| Name | In | Type | Meaning | Required |
|---|---|---|---|---|
| `id` | path | string | legacy id | yes |

Example request:

```http
GET /databaseconnections/
```

Response (real data):

```json
{
  "error": "not found"
}
```


## Fibonacci

0 records. Fields: 

_No form was seen for this entity on the legacy site, so it has no write endpoints._

### `GET /fibonacci`

List Fibonacci records (currently none).

| Name | In | Type | Meaning | Required |
|---|---|---|---|---|
| `limit` | query | integer | max rows (default 50) |  |
| `offset` | query | integer | skip rows |  |

Example request:

```http
GET /fibonacci?limit=3
```

Response (real data):

```json
{
  "total": 0,
  "limit": 3,
  "offset": 0,
  "items": []
}
```

### `GET /fibonacci/{id}`

Retrieve a single Fibonacci record by its legacy ID.

| Name | In | Type | Meaning | Required |
|---|---|---|---|---|
| `id` | path | string | legacy id | yes |

Example request:

```http
GET /fibonacci/
```

Response (real data):

```json
{
  "error": "not found"
}
```

