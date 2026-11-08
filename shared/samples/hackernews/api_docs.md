# API for https://news.ycombinator.com

Designed by Nemotron (`nvidia/nemotron-3.5-super-vl-120b-a12b`) from 2582 extracted records. Reads come from the database (SpacetimeDB); writes are performed live on the legacy site by the Operator and verified.

| Method | Path | Source | What it does |
|---|---|---|---|
| GET | `/posts` | database | Returns a paginated list of posts with optional filters by title, author, points, comments, and time. |
| GET | `/posts/{id}` | database | Returns a single post by its legacy ID. |
| GET | `/posts/search` | database | Searches posts by free-text query across title and author. |

## Post

2582 records. Fields: `title` (string), `points` (integer), `author` (string), `time` (string), `rank` (integer), `hide` (boolean), `comments` (integer), `text` (string)

_No form was seen for this entity on the legacy site, so it has no write endpoints._

### `GET /posts`

Returns a paginated list of posts with optional filters by title, author, points, comments, and time.

| Name | In | Type | Meaning | Required |
|---|---|---|---|---|
| `title` | query | string | `title` contains (case-insensitive) |  |
| `author` | query | string | `author` contains (case-insensitive) |  |
| `min_points` | query | integer | `points` ≥ |  |
| `max_points` | query | integer | `points` ≤ |  |
| `min_comments` | query | integer | `comments` ≥ |  |
| `max_comments` | query | integer | `comments` ≤ |  |
| `time` | query | string | `time` equals |  |
| `limit` | query | integer | max rows (default 50) |  |
| `offset` | query | integer | skip rows |  |
| `sort` | query | string | sort field, `-` = descending |  |

Example request:

```http
GET /posts?min_points=3&time=13+hours+ago&limit=3
```

Response (real data):

```json
{
  "total": 29,
  "limit": 3,
  "offset": 0,
  "items": [
    {
      "legacy_id": "50405782",
      "title": "Every processor die anyone has photographed and given away (sheets.works)",
      "points": 99,
      "author": "user_7832",
      "time": "13 hours ago"
    },
    {
      "legacy_id": "50405674",
      "title": "Terry Pratchett's Study (sussi.dk)",
      "points": 118,
      "author": "ColinWright",
      "time": "13 hours ago"
    },
    "... 1 more"
  ]
}
```

### `GET /posts/{id}`

Returns a single post by its legacy ID.

| Name | In | Type | Meaning | Required |
|---|---|---|---|---|
| `id` | path | string | legacy id | yes |

Example request:

```http
GET /posts/50410107
```

Response (real data):

```json
{
  "legacy_id": "50410107",
  "title": "Goodbye Claude, Hello Pi (caleb.software)",
  "points": 62,
  "author": "karagenit",
  "time": "2 hours ago"
}
```

### `GET /posts/search`

Searches posts by free-text query across title and author.

| Name | In | Type | Meaning | Required |
|---|---|---|---|---|
| `q` | query | string | searches `title`, `author` |  |
| `limit` | query | integer | max rows (default 50) |  |
| `offset` | query | integer | skip rows |  |

Example request:

```http
GET /posts/search?q=%28github.com%2Fcrmne%29&limit=3
```

Response (real data):

```json
{
  "total": 1,
  "limit": 3,
  "offset": 0,
  "items": [
    {
      "legacy_id": "50409855",
      "title": "ZapFast: A fast, native WhatsApp client in Rust and egui (github.com/crmne)",
      "points": 30,
      "author": "handfuloflight",
      "time": "3 hours ago"
    }
  ]
}
```

