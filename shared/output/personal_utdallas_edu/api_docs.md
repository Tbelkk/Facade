# API for https://personal.utdallas.edu/~John.cole/

Designed by Nemotron (`nvidia/nemotron-3-nano-omni-30b-a3b-reasoning`) from 132 extracted records. Reads come from the database (SpacetimeDB); writes are performed live on the legacy site by the Operator and verified.

The checker found 6 problem(s) in the first design; Nemotron fixed them in one round (6 left, 6 endpoint(s) dropped).

| Method | Path | Source | What it does |
|---|---|---|---|
| GET | `/teaching_philosophy` | database | Retrieve teaching philosophy statements with optional filtering and pagination. |
| GET | `/teaching_philosophy/{id}` | database | Retrieve a single teaching philosophy by its legacy ID. |
| GET | `/useful_link` | database | Retrieve useful link resources with optional filtering and pagination. |
| GET | `/useful_link/{id}` | database | Retrieve a single useful link by its legacy ID. |
| GET | `/course` | database | List courses with optional filtering on term, title, details, and course info. |
| GET | `/course/{id}` | database | Retrieve a single course by its legacy ID. |
| GET | `/guideline` | database | List guidelines with optional filtering on the guideline text. |
| GET | `/guideline/{id}` | database | Retrieve a single guideline by its legacy ID. |
| GET | `/schedule` | database | List schedule entries with optional filtering on week, date, topic, or assignments. |
| GET | `/schedule/{id}` | database | Retrieve a single schedule entry by its legacy ID. |
| GET | `/project` | database | List project entries with optional filtering on title or description. |
| GET | `/project/{id}` | database | Retrieve a single project by its legacy ID. |

## TeachingPhilosophy

1 records. Fields: `description` (string)

_No form was seen for this entity on the legacy site, so it has no write endpoints._

### `GET /teaching_philosophy`

Retrieve teaching philosophy statements with optional filtering and pagination.

| Name | In | Type | Meaning | Required |
|---|---|---|---|---|
| `limit` | query | integer | max rows (default 50) |  |
| `offset` | query | integer | skip rows |  |
| `description_contains` | query | string | `description` contains (case-insensitive) |  |
| `description_eq` | query | string | `description` equals |  |
| `sort` | query | string | sort field, `-` = descending |  |

Example request:

```http
GET /teaching_philosophy?description_eq=Nearly+every+course+I+teach+with+the+exception+of+CS1200+will+involve+lots+of+programming.+There+is+an+ancient+saying+attributed+to+Confucius+that+goes+like+this%3A+%22I+hear+and+I+forget.+I+see+and+I+remember.+I+do+and+I+understand.%22+In+my+classes%2C+I+use+a+combination+of+PowerPoint+slides%2C+lecture%2C+examples%2C+and+in-class+exercises+so+you+can+both+see+and+hear%2C+and+sometimes+do%2C+as+well.+More...&limit=3
```

Response (real data):

```json
{
  "total": 1,
  "limit": 3,
  "offset": 0,
  "items": [
    {
      "legacy_id": "75e0160ac56a",
      "description": "Nearly every course I teach with the exception of CS1200 will involve lots of programming. There is an ancient saying attributed to Confucius that goes like this: \"I hear and I forget. I see and I remember. I do and I understand.\" In my classes, I use a combination of PowerPoint slides, lecture, examples, and in-class exercises so you can both see and hear, and sometimes do, as well. More..."
    }
  ]
}
```

### `GET /teaching_philosophy/{id}`

Retrieve a single teaching philosophy by its legacy ID.

| Name | In | Type | Meaning | Required |
|---|---|---|---|---|
| `id` | path | string | legacy id | yes |

Example request:

```http
GET /teaching_philosophy/75e0160ac56a
```

Response (real data):

```json
{
  "legacy_id": "75e0160ac56a",
  "description": "Nearly every course I teach with the exception of CS1200 will involve lots of programming. There is an ancient saying attributed to Confucius that goes like this: \"I hear and I forget. I see and I remember. I do and I understand.\" In my classes, I use a combination of PowerPoint slides, lecture, examples, and in-class exercises so you can both see and hear, and sometimes do, as well. More..."
}
```


## UsefulLink

1 records. Fields: `description` (string)

_No form was seen for this entity on the legacy site, so it has no write endpoints._

### `GET /useful_link`

Retrieve useful link resources with optional filtering and pagination.

| Name | In | Type | Meaning | Required |
|---|---|---|---|---|
| `limit` | query | integer | max rows (default 50) |  |
| `offset` | query | integer | skip rows |  |
| `description_contains` | query | string | `description` contains (case-insensitive) |  |
| `description_eq` | query | string | `description` equals |  |
| `sort` | query | string | sort field, `-` = descending |  |

Example request:

```http
GET /useful_link?description_eq=Programming+Tips%2C+including+Android%2C+C%2B%2B%2C+etc.+These+are+code+samples+you+can+use+for+some+of+my+classes.+Some+useful+Software+Engineering+Basics+to+help+you+create+better+programs.+Uncommented+code+is+bad+and+wrong.+Learn+How+to+comment+your+code.+%28You+should+comment+it+before+you+write+it.+That%27s+why+this+section+is+first.%29+This+is+critical+if+you+are+taking+one+of+my+programming+classes+where+at+least+10%25+of+your+grade+is+based+on+the+code+comments.+Spending+far+too+much+time+writing+programs%3F+Learn+How+to+write+code.+A+succinct+explanation+of+a+technique+that+will+save+you+time+and+give+you+good+results.+ScanTron+form%2C+correctly+filled+out.+%28Only+for+tests+in+the+classroom.%29+The+entire+form%2C+including+your+name+and+course%2C+must+be+completed+in+number+2+pencil+only.+Pen+does+not+scan+and+you+will+lose+10+points+for+any+corrections+I+must+make+to+your+form%2C+including+using+the+wrong+one%2C+using+pen%2C+etc.+The+%22ID%22+field+is+a+number+that+will+be+assigned+to+you+as+a+%22grade%22+in+eLearning.+Ideally%2C+you+should+have+filled+in+the+information+other+than+the+answers+%28I+have+shown+a+few+sample+answers%2C+but+ignore+those%29+before+you+come+to+class.+Grader+Guidelines+for+graders+to+follow+and+students+to+understand.+You+will+find+assignments%2C+grades%2C+and+other+class+material+on+eLearning%2C+also+called+Blackboard.+The+Computer+Science+Department+main+page+contains+recent+events+and+other+information.+It%27s+also+pretty+cool.+UTD+International+Student+Services+Organization.+Given+the+importance+of+writing+in+most+of+my+classes%2C+if+English+is+not+your+first+language+you+will+find+useful+events%2C+such+as+conversation+workshops%2C+writing+help%2C+and+other+help+here.+You+can+also+get+writing+help+from+the+Student+Success+Center%27s+Writing+Center.+I+cannot+stress+enough+the+importance+of+good+writing.+The+Computer+Science+Mentor+Center+can+help+you+with+CS1336%2C+CS1337%2C+CS2340%2C+and+CS2336%2C+among+other+classes.+Click+here+to+go+to+the+Center%27s+official+page.+Many+books+and+journals+that+are+useful+in+my+classes+are+online+at+the+UTD+Library.&limit=3
```

Response (real data):

```json
{
  "total": 1,
  "limit": 3,
  "offset": 0,
  "items": [
    {
      "legacy_id": "6e1b9bfb19be",
      "description": "Programming Tips, including Android, C++, etc. These are code samples you can use for some of my classes. Some useful Software Engineering Basics to help you create better programs. Uncommented code is bad and wrong. Learn How to comment your code. (You should comment it before you write it. That's why this section is first.) This is critical if you are taking one of my programming classes where at least 10% of your grade is based on the code comments. Spending far too much time writing programs? Learn How to write code. A succinct explanation of a technique that will save you time and give you good results. ScanTron form, correctly filled out. (Only for tests in the classroom.) The entire form, including your name and course, must be completed in number 2 pencil only. Pen does not scan and you will lose 10 points for any corrections I must make to your form, including using the wrong one, using pen, etc. The \"ID\" field is a number that will be assigned to you as a \"grade\" in eLearning. Ideally, you should have filled in the information other than the answers (I have shown a few sample answers, but ignore those) before you come to class. Grader Guidelines for graders to follow and students to understand. You will find assignments, grades, and other class material on eLearning, also called Blackboard. The Computer Science Department main page contains recent events and other information. It's also pretty cool. UTD International Student Services Organization. Given the importance of writing in most of my classes, if English is not your first language you will find useful events, such as conversation workshops, writing help, and other help here. You can also get writing help from the Student Success Center's Writing Center. I cannot stress enough the importance of good writing. The Computer Science Mentor Center can help you with CS1336, CS1337, CS2340, and CS2336, among other classes. Click here to go to the Center's official page. Many books and journals that are useful in my classes are online at the UTD Library."
    }
  ]
}
```

### `GET /useful_link/{id}`

Retrieve a single useful link by its legacy ID.

| Name | In | Type | Meaning | Required |
|---|---|---|---|---|
| `id` | path | string | legacy id | yes |

Example request:

```http
GET /useful_link/6e1b9bfb19be
```

Response (real data):

```json
{
  "legacy_id": "6e1b9bfb19be",
  "description": "Programming Tips, including Android, C++, etc. These are code samples you can use for some of my classes. Some useful Software Engineering Basics to help you create better programs. Uncommented code is bad and wrong. Learn How to comment your code. (You should comment it before you write it. That's why this section is first.) This is critical if you are taking one of my programming classes where at least 10% of your grade is based on the code comments. Spending far too much time writing programs? Learn How to write code. A succinct explanation of a technique that will save you time and give you good results. ScanTron form, correctly filled out. (Only for tests in the classroom.) The entire form, including your name and course, must be completed in number 2 pencil only. Pen does not scan and you will lose 10 points for any corrections I must make to your form, including using the wrong one, using pen, etc. The \"ID\" field is a number that will be assigned to you as a \"grade\" in eLearning. Ideally, you should have filled in the information other than the answers (I have shown a few sample answers, but ignore those) before you come to class. Grader Guidelines for graders to follow and students to understand. You will find assignments, grades, and other class material on eLearning, also called Blackboard. The Computer Science Department main page contains recent events and other information. It's also pretty cool. UTD International Student Services Organization. Given the importance of writing in most of my classes, if English is not your first language you will find useful events, such as conversation workshops, writing help, and other help here. You can also get writing help from the Student Success Center's Writing Center. I cannot stress enough the importance of good writing. The Computer Science Mentor Center can help you with CS1336, CS1337, CS2340, and CS2336, among other classes. Click here to go to the Center's official page. Many books and journals that are useful in my classes are online at the UTD Library."
}
```


## Course

89 records. Fields: `term` (string), `course_info` (string), `title` (string), `details` (string)

_No form was seen for this entity on the legacy site, so it has no write endpoints._

### `GET /course`

List courses with optional filtering on term, title, details, and course info.

| Name | In | Type | Meaning | Required |
|---|---|---|---|---|
| `limit` | query | integer | max rows (default 50) |  |
| `offset` | query | integer | skip rows |  |
| `term_contains` | query | string | `term` contains (case-insensitive) |  |
| `term_eq` | query | string | `term` equals |  |
| `title_contains` | query | string | `title` contains (case-insensitive) |  |
| `title_eq` | query | string | `title` equals |  |
| `details_contains` | query | string | `details` contains (case-insensitive) |  |
| `details_eq` | query | string | `details` equals |  |
| `sort` | query | string | sort field, `-` = descending |  |

Example request:

```http
GET /course?term_eq=Courses+Fall+2017&limit=3
```

Response (real data):

```json
{
  "total": 6,
  "limit": 3,
  "offset": 0,
  "items": [
    {
      "legacy_id": "30dde88d901f",
      "term": "Courses Fall 2017",
      "course_info": "CS6360.004 Database Design on Monday/Wednesday from 8:30 to 9:45 AM in JSOM 11.206"
    },
    {
      "legacy_id": "05c2abd43264",
      "term": "Courses Fall 2017",
      "course_info": "CS6326.001 Human-Computer Interaction on Monday/Wednesday from 11:30 AM to 12:45 PM in GR 3.302"
    },
    "... 1 more"
  ]
}
```

### `GET /course/{id}`

Retrieve a single course by its legacy ID.

| Name | In | Type | Meaning | Required |
|---|---|---|---|---|
| `id` | path | string | legacy id | yes |

Example request:

```http
GET /course/CS3162Fall2026.htm
```

Response (real data):

```json
{
  "legacy_id": "CS3162Fall2026.htm",
  "term": "Courses Fall 2026",
  "course_info": "CS3162 Professional Responsibility in CS and SE on Tuesday/Thursday from 8:00 AM to 8:50 (Section 052) and 9:00 to 9:50 (Section 051) in SCI 1.220"
}
```


## Guideline

20 records. Fields: `guideline` (string)

_No form was seen for this entity on the legacy site, so it has no write endpoints._

### `GET /guideline`

List guidelines with optional filtering on the guideline text.

| Name | In | Type | Meaning | Required |
|---|---|---|---|---|
| `limit` | query | integer | max rows (default 50) |  |
| `offset` | query | integer | skip rows |  |
| `guideline_contains` | query | string | `guideline` contains (case-insensitive) |  |
| `guideline_eq` | query | string | `guideline` equals |  |
| `sort` | query | string | sort field, `-` = descending |  |

Example request:

```http
GET /guideline?guideline_eq=Assembly+Code+Assembler+is+different.+It+requires+far+better+documentation+than+high-level+language.+See+the+examples+below+for+what+good+code+and+documentation+look+like.+Here+are+some+rules%3A+1.+Nearly+every+line+should+have+a+comment.+Without+this%2C+many+assembly+language+programs+are+nearly+impossible+to+read+and+understand%2C+even+if+you+are+the+one+who+wrote+it.+Make+the+comments+useful%2C+same+as+for+a+high-level+language.+Not+%22Add+one+to+%24a0%22+but+%22Move+pointer+to+next+byte.%22+See+the+difference%3F+Keep+line+comments+short+and+to+the+point.+2.+Since+register+names+are+not+particularly+descriptive%2C+it+helps+to+have+comments+above+a+block+of+code+describing+the+register+contents+when+you+enter+that+block+along+with+what+the+block+accomplishes.+Use+margins.+Do+not+type+past+column+80+or+90+so+I+don%27t+have+to+side-scroll+to+read+your+code.+3.+Every+assembly+language+has+a+directive+that+lets+you+set+a+symbol+equal+to+a+value.+In+MIPS+this+is+the+.eqv+directive%2C+which+sets+the+symbol%2C+the+first+argument%2C+equal+to+the+second+thing.+%28This+is+very+similar+to+the+C%2FC%2B%2B+%23define+directive.%29+This+can+be+especially+helpful+for+local+variables+that+are+at+some+offset+from+the+stack+pointer.+See+the+example+below.+You+can+also+use+this+to+make+your+register+names+mean+something.+This+helps+you+avoid+what+I+call+%22magic+numbers%2C%22+numerical+constants+whose+meaning+you+will+forget+within+10+minutes+of+using+them+and+the+meaning+of+which+is+completely+opaque+to+anyone+else+reading+your+code.+4.+Use+labels+where+you+need+them.+While+many+of+us+have+a+tendency+to+use+short+labels+and+put+them+on+the+same+line+as+code%2C+this+is+not+necessary%2C+and+a+longer%2C+more+descriptive+label+above+a+section+of+code+may+be+much+better.+Speaking+of+labels%2C+if+you+have+a+function+named%2C+for+example%2C+strcpy%2C+if+you+have+labels+within+it%2C+use+the+name+of+the+function+and+a+number%2C+for+example%2C+strcpy5.+You+will+find+that+you+need+many+more+labels+in+assembly+language+because+there+are+no+looping+constructs%2C+just+branch+or+jump+instructions+that+require+a+label.+Convention+is+that+labels+start+in+column+1.+Do+not+use+labels+that+you+never+reference.+5.+Do+not+indent+assembly+code+the+way+you+would+C%2B%2B+or+other+high-level+languages.+Line+up+your+instruction+menemonics+in+colum+10+or+11%2C+tab+to+the+next+column%2C+and+align+the+operands.+To+clarify%3A+Labels+in+column+1.+Instructions+and+pseudo-operations+in+column+10+or+11.+Operands+in+column+19+or+20.+Comments+in+30+or+so.+Line+up+everything+neatly+to+the+extent+that+this+is+possible.+6.+As+you+would+with+a+high-level+language%2C+modularize.+Put+your+simple+utility+functions+such+as+copying+strings%2C+searches%2C+and+the+like+into+a+separately-assembled+module.+Once+you+have+those+working%2C+you+never+need+to+look+at+them+again.+Do+not+use+the+.include+directive+for+this+code.+7.+This+is+not+strictly+about+documentation%2C+but+readability.+Unless+you+have+a+loop%2C+the+control+flow+in+your+program+should+be+generally+from+top+to+bottom.+Since+assembly+code+has+no+inherent+structure%2C+you+must+provide+one.+For+example%2C+testing+something+and+branching+if+equal+to+a+place+further+down+in+the+code+is+fine.+Branching+from+that+place+to+someplace+further+up+in+the+code+is+usually+not%3B+the+technical+term+for+this+is+%22spaghetti+code%2C%22+because+it+goes+everywhere.+Similarly%2C+don%27t+put+your+subroutines+in+the+middle+and+branch+around+them.+Don%27t+branch+to+a+label+that+your+code+would+fall+through+to+anyway.+See+the+bad+example+below.+See+the+good+example+in+Fibonacci.asm.&limit=3
```

Response (real data):

```json
{
  "total": 1,
  "limit": 3,
  "offset": 0,
  "items": [
    {
      "legacy_id": "c2c1975c9950",
      "guideline": "Assembly Code Assembler is different. It requires far better documentation than high-level language. See the examples below for what good code and documentation look like. Here are some rules: 1. Nearly every line should have a comment. Without this, many assembly language programs are nearly impossible to read and understand, even if you are the one who wrote it. Make the comments useful, same as for a high-level language. Not \"Add one to $a0\" but \"Move pointer to next byte.\" See the difference? Keep line comments short and to the point. 2. Since register names are not particularly descriptive, it helps to have comments above a block of code describing the register contents when you enter that block along with what the block accomplishes. Use margins. Do not type past column 80 or 90 so I don't have to side-scroll to read your code. 3. Every assembly language has a directive that lets you set a symbol equal to a value. In MIPS this is the .eqv directive, which sets the symbol, the first argument, equal to the second thing. (This is very similar to the C/C++ #define directive.) This can be especially helpful for local variables that are at some offset from the stack pointer. See the example below. You can also use this to make your register names mean something. This helps you avoid what I call \"magic numbers,\" numerical constants whose meaning you will forget within 10 minutes of using them and the meaning of which is completely opaque to anyone else reading your code. 4. Use labels where you need them. While many of us have a tendency to use short labels and put them on the same line as code, this is not necessary, and a longer, more descriptive label above a section of code may be much better. Speaking of labels, if you have a function named, for example, strcpy, if you have labels within it, use the name of the function and a number, for example, strcpy5. You will find that you need many more labels in assembly language because there are no looping constructs, just branch or jump instructions that require a label. Convention is that labels start in column 1. Do not use labels that you never reference. 5. Do not indent assembly code the way you would C++ or other high-level languages. Line up your instruction menemonics in colum 10 or 11, tab to the next column, and align the operands. To clarify: Labels in column 1. Instructions and pseudo-operations in column 10 or 11. Operands in column 19 or 20. Comments in 30 or so. Line up everything neatly to the extent that this is possible. 6. As you would with a high-level language, modularize. Put your simple utility functions such as copying strings, searches, and the like into a separately-assembled module. Once you have those working, you never need to look at them again. Do not use the .include directive for this code. 7. This is not strictly about documentation, but readability. Unless you have a loop, the control flow in your program should be generally from top to bottom. Since assembly code has no inherent structure, you must provide one. For example, testing something and branching if equal to a place further down in the code is fine. Branching from that place to someplace further up in the code is usually not; the technical term for this is \"spaghetti code,\" because it goes everywhere. Similarly, don't put your subroutines in the middle and branch around them. Don't branch to a label that your code would fall through to anyway. See the bad example below. See the good example in Fibonacci.asm."
    }
  ]
}
```

### `GET /guideline/{id}`

Retrieve a single guideline by its legacy ID.

| Name | In | Type | Meaning | Required |
|---|---|---|---|---|
| `id` | path | string | legacy id | yes |

Example request:

```http
GET /guideline/fddd10e3c9d1
```

Response (real data):

```json
{
  "legacy_id": "fddd10e3c9d1",
  "guideline": "1. Always give feedback in the comments section on eLearning. If you take off points, the student must know why, so explain clearly. For example, \"No header comments: -5. Program doesn't check for invalid input: -10\" If the student does well, praise is in order. This also helps me track student progress. Remember that the point of having them write programs is so they can learn, and your feedback is an important part of that process."
}
```


## Schedule

17 records. Fields: `week` (string), `date` (string), `topic` (string), `assignments` (string)

_No form was seen for this entity on the legacy site, so it has no write endpoints._

### `GET /schedule`

List schedule entries with optional filtering on week, date, topic, or assignments.

| Name | In | Type | Meaning | Required |
|---|---|---|---|---|
| `limit` | query | integer | max rows (default 50) |  |
| `offset` | query | integer | skip rows |  |
| `week_contains` | query | string | `week` contains (case-insensitive) |  |
| `week_eq` | query | string | `week` equals |  |
| `date_contains` | query | string | `date` contains (case-insensitive) |  |
| `topic_contains` | query | string | `topic` contains (case-insensitive) |  |
| `assignments_contains` | query | string | `assignments` contains (case-insensitive) |  |
| `sort` | query | string | sort field, `-` = descending |  |

Example request:

```http
GET /schedule?week_eq=7&limit=3
```

Response (real data):

```json
{
  "total": 2,
  "limit": 3,
  "offset": 0,
  "items": [
    {
      "legacy_id": "8d9f2dfbb7b5",
      "week": 7,
      "date": "Dec 1",
      "topic": "Chapter 9 -- Professional Ethics and Responsibilities"
    },
    {
      "legacy_id": "7f8c4147f489",
      "week": 7,
      "date": "Dec 8",
      "topic": "Test Review"
    }
  ]
}
```

### `GET /schedule/{id}`

Retrieve a single schedule entry by its legacy ID.

| Name | In | Type | Meaning | Required |
|---|---|---|---|---|
| `id` | path | string | legacy id | yes |

Example request:

```http
GET /schedule/404b4ac5cf1c
```

Response (real data):

```json
{
  "legacy_id": "404b4ac5cf1c",
  "week": "Week",
  "date": "Date",
  "topic": "Topic",
  "assignments": "Assignments"
}
```


## Project

4 records. Fields: `description` (string), `title` (string)

_No form was seen for this entity on the legacy site, so it has no write endpoints._

### `GET /project`

List project entries with optional filtering on title or description.

| Name | In | Type | Meaning | Required |
|---|---|---|---|---|
| `limit` | query | integer | max rows (default 50) |  |
| `offset` | query | integer | skip rows |  |
| `description_contains` | query | string | `description` contains (case-insensitive) |  |
| `description_eq` | query | string | `description` equals |  |
| `title_contains` | query | string | `title` contains (case-insensitive) |  |
| `title_eq` | query | string | `title` equals |  |
| `sort` | query | string | sort field, `-` = descending |  |

Example request:

```http
GET /project?description_eq=Personal+Projects+Below+are+some+of+the+things+I+have+done+in+my+spare+time%2C+not+always+directly+affiliated+with+UTD.+I%27m+a+tinkerer%2C+and+I+really+like+embedded+programming+as+well+as+Android+projects+in+Java.&limit=3
```

Response (real data):

```json
{
  "total": 1,
  "limit": 3,
  "offset": 0,
  "items": [
    {
      "legacy_id": "a3c192c2f158",
      "description": "Personal Projects Below are some of the things I have done in my spare time, not always directly affiliated with UTD. I'm a tinkerer, and I really like embedded programming as well as Android projects in Java."
    }
  ]
}
```

### `GET /project/{id}`

Retrieve a single project by its legacy ID.

| Name | In | Type | Meaning | Required |
|---|---|---|---|---|
| `id` | path | string | legacy id | yes |

Example request:

```http
GET /project/a3c192c2f158
```

Response (real data):

```json
{
  "legacy_id": "a3c192c2f158",
  "description": "Personal Projects Below are some of the things I have done in my spare time, not always directly affiliated with UTD. I'm a tinkerer, and I really like embedded programming as well as Android projects in Java."
}
```

