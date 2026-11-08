# API for http://127.0.0.1:65294

Designed by Nemotron (`nvidia/nemotron-3.5-super-vl-120b-a12b`) from 38 extracted records. Reads come from the database (SpacetimeDB); writes are performed live on the legacy site by the Operator and verified.

| Method | Path | Source | What it does |
|---|---|---|---|
| GET | `/posts` | database | List posts with optional filters on points, time, comments, domain, and author. |
| GET | `/posts/{id}` | database | Get a single post by its legacy ID. |
| GET | `/posts/search` | database | Search posts by free-text query against the title field. |
| GET | `/users` | database | List users with optional filters on username, karma, and joined date. |
| GET | `/users/{id}` | database | Get a single user by its legacy ID. |

## Post

26 records. Fields: `title` (string), `points` (integer), `author` (string), `author_id` (ref → User), `time` (date), `comments` (integer), `domain` (string)

_No form was seen for this entity on the legacy site, so it has no write endpoints._

### `GET /posts`

List posts with optional filters on points, time, comments, domain, and author.

| Name | In | Type | Meaning | Required |
|---|---|---|---|---|
| `min_points` | query | integer | `points` ≥ |  |
| `max_points` | query | integer | `points` ≤ |  |
| `min_time` | query | string | `time` ≥ |  |
| `max_time` | query | string | `time` ≤ |  |
| `min_comments` | query | integer | `comments` ≥ |  |
| `max_comments` | query | integer | `comments` ≤ |  |
| `domain` | query | string | `domain` equals: `nytimes.com`, `blog.dev`, `example.org`, `github.com`, `arxiv.org` |  |
| `author_id` | query | string | `author_id` equals: `u101`, `u109`, `u102`, `u112`, `u104`, `u107`, `u105`, `u108` … |  |
| `limit` | query | integer | max rows (default 50) |  |
| `offset` | query | integer | skip rows |  |
| `sort` | query | string | sort field, `-` = descending: `points`, `-points`, `time`, `-time`, `comments`, `-comments` |  |

Example request:

```http
GET /posts?min_points=161&domain=nytimes.com&limit=3
```

Response (real data):

```json
{
  "total": 5,
  "limit": 3,
  "offset": 0,
  "items": [
    {
      "legacy_id": "40103",
      "title": "Why legacy COBOL still runs the banks",
      "points": 177,
      "author": "alice",
      "author_id": "u101",
      "time": "2026-09-19",
      "comments": 110,
      "domain": "nytimes.com"
    },
    {
      "legacy_id": "40112",
      "title": "Rust in the Linux kernel: one year later",
      "points": 161,
      "author": "bob",
      "author_id": "u102",
      "time": "2026-10-11",
      "comments": 15,
      "domain": "nytimes.com"
    },
    "... 1 more"
  ]
}
```

### `GET /posts/{id}`

Get a single post by its legacy ID.

| Name | In | Type | Meaning | Required |
|---|---|---|---|---|
| `id` | path | string | legacy id | yes |

Example request:

```http
GET /posts/40100
```

Response (real data):

```json
{
  "legacy_id": "40100",
  "title": "Show HN: A Postgres extension for vector search",
  "points": 294,
  "author": "ines",
  "author_id": "u109",
  "time": "2026-09-23",
  "comments": 260,
  "domain": "blog.dev"
}
```

### `GET /posts/search`

Search posts by free-text query against the title field.

| Name | In | Type | Meaning | Required |
|---|---|---|---|---|
| `q` | query | string | searches `title` | yes |
| `limit` | query | integer | max rows (default 50) |  |
| `offset` | query | integer | skip rows |  |

Example request:

```http
GET /posts/search?q=extension&limit=3
```

Response (real data):

```json
{
  "total": 1,
  "limit": 3,
  "offset": 0,
  "items": [
    {
      "legacy_id": "40100",
      "title": "Show HN: A Postgres extension for vector search",
      "points": 294,
      "author": "ines",
      "author_id": "u109",
      "time": "2026-09-23",
      "comments": 260,
      "domain": "blog.dev"
    }
  ]
}
```


## User

12 records. Fields: `username` (string), `karma` (integer), `joined` (date)

_No form was seen for this entity on the legacy site, so it has no write endpoints._

### `GET /users`

List users with optional filters on username, karma, and joined date.

| Name | In | Type | Meaning | Required |
|---|---|---|---|---|
| `username` | query | string | `username` contains (case-insensitive) |  |
| `min_karma` | query | integer | `karma` ≥ |  |
| `max_karma` | query | integer | `karma` ≤ |  |
| `min_joined` | query | string | `joined` ≥ |  |
| `max_joined` | query | string | `joined` ≤ |  |
| `limit` | query | integer | max rows (default 50) |  |
| `offset` | query | integer | skip rows |  |
| `sort` | query | string | sort field, `-` = descending: `karma`, `-karma`, `joined`, `-joined` |  |

Example request:

```http
GET /users?min_karma=14833&limit=3
```

Response (real data):

```json
{
  "total": 7,
  "limit": 3,
  "offset": 0,
  "items": [
    {
      "legacy_id": "u101",
      "username": "alice",
      "karma": 14833,
      "joined": "2022-08-17"
    },
    {
      "legacy_id": "u102",
      "username": "bob",
      "karma": 19257,
      "joined": "2014-03-26"
    },
    "... 1 more"
  ]
}
```

### `GET /users/{id}`

Get a single user by its legacy ID.

| Name | In | Type | Meaning | Required |
|---|---|---|---|---|
| `id` | path | string | legacy id | yes |

Example request:

```http
GET /users/u101
```

Response (real data):

```json
{
  "legacy_id": "u101",
  "username": "alice",
  "karma": 14833,
  "joined": "2022-08-17"
}
```

