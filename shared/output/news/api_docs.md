# API for http://127.0.0.1:49524

Designed by Nemotron (`nvidia/nemotron-3.5-super-vl-120b-a12b`) from 38 extracted records. Reads come from the database (SpacetimeDB); writes are performed live on the legacy site by the Operator and verified.

| Method | Path | Source | What it does |
|---|---|---|---|
| GET | `/users` | database | List users with optional filters on username, karma, and join date, plus pagination and sorting. |
| GET | `/users/{id}` | database | Get a single user by legacy id. |
| GET | `/posts` | database | List posts with optional filters on author, domain, points, time, and comments, plus pagination and sorting. |
| GET | `/posts/{id}` | database | Get a single post by legacy id. |
| GET | `/posts/search` | database | Search posts by free-text query across the title field. |

## User

12 records. Fields: `username` (string), `karma` (integer), `joined` (date)

_No form was seen for this entity on the legacy site, so it has no write endpoints._

### `GET /users`

List users with optional filters on username, karma, and join date, plus pagination and sorting.

| Name | In | Type | Meaning | Required |
|---|---|---|---|---|
| `username` | query | string | `username` contains (case-insensitive) |  |
| `min_karma` | query | integer | `karma` ≥ |  |
| `max_karma` | query | integer | `karma` ≤ |  |
| `min_joined` | query | string | `joined` ≥ |  |
| `max_joined` | query | string | `joined` ≤ |  |
| `limit` | query | integer | max rows (default 50) |  |
| `offset` | query | integer | skip rows |  |
| `sort` | query | string | sort field, `-` = descending |  |

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

Get a single user by legacy id.

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


## Post

26 records. Fields: `title` (string), `points` (integer), `author` (string), `author_id` (ref → User), `time` (date), `comments` (integer), `domain` (string)

_No form was seen for this entity on the legacy site, so it has no write endpoints._

### `GET /posts`

List posts with optional filters on author, domain, points, time, and comments, plus pagination and sorting.

| Name | In | Type | Meaning | Required |
|---|---|---|---|---|
| `author_id` | query | string | `author_id` equals |  |
| `domain` | query | string | `domain` equals: `nytimes.com`, `blog.dev`, `example.org`, `github.com`, `arxiv.org` |  |
| `min_points` | query | integer | `points` ≥ |  |
| `max_points` | query | integer | `points` ≤ |  |
| `min_time` | query | string | `time` ≥ |  |
| `max_time` | query | string | `time` ≤ |  |
| `min_comments` | query | integer | `comments` ≥ |  |
| `max_comments` | query | integer | `comments` ≤ |  |
| `limit` | query | integer | max rows (default 50) |  |
| `offset` | query | integer | skip rows |  |
| `sort` | query | string | sort field, `-` = descending |  |

Example request:

```http
GET /posts?min_points=161&author_id=u101&limit=3
```

Response (real data):

```json
{
  "total": 3,
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
      "legacy_id": "40157",
      "title": "The art of the boring database",
      "points": 687,
      "author": "alice",
      "author_id": "u101",
      "time": "2026-09-16",
      "comments": 366,
      "domain": null
    },
    "... 1 more"
  ]
}
```

### `GET /posts/{id}`

Get a single post by legacy id.

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

Search posts by free-text query across the title field.

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

