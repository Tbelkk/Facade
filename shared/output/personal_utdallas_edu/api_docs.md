# API for https://personal.utdallas.edu/~John.cole/

Designed by Nemotron (`nvidia/nemotron-3-nano-omni-30b-a3b-reasoning`) from 101 extracted records. Reads come from the database (SpacetimeDB); writes are performed live on the legacy site by the Operator and verified.

The checker found 3 problem(s) in the first design; Nemotron fixed them in one round (1 left, 0 endpoint(s) dropped).

| Method | Path | Source | What it does |
|---|---|---|---|
| GET | `/announcements` | database | List Announcement records, with filters |
| GET | `/announcements/{id}` | database | One Announcement by its legacy id |
| GET | `/courses` | database | List Course records, with filters |
| GET | `/courses/{id}` | database | One Course by its legacy id |
| GET | `/course_infos` | database | List CourseInfo records, with filters |
| GET | `/course_infos/{id}` | database | One CourseInfo by its legacy id |

## Announcement

17 records. Fields: `date_posted` (string), `announcement` (string), `title` (string)

_No form was seen for this entity on the legacy site, so it has no write endpoints._

### `GET /announcements`

List Announcement records, with filters

| Name | In | Type | Meaning | Required |
|---|---|---|---|---|
| `date_posted` | query | string | `date_posted` contains (case-insensitive) |  |
| `title` | query | string | `title` equals: `The following rules pertain to this exam:`, `I give many exams in the Testing Center, in the basement of the McDermott Library. For such exams, you will follow Testing Center rules, including not being permitted to bring in anything, such as notes, a calculator, or a cell phone. The test will auto-submit at the end of the allotted time and your work will be saved. However, you will be unable to work on the test past the time allowed. Rules for Paper Exams: 1. This exam is timed. You may turn the page and start when I announce the start and you will put your pencils or pens down and stop writing when I announce the stop time. I may extend the stop time, but nominally you have 1 hour 15 minutes. You will lose 20 points if you are still writing after time is called. 2. When time is called, pass your paper to your left and remain seated until I have collected all papers. 3. If you finish before 3 minutes prior to the stop time you may hand in your paper and leave. If it is after 3 minutes before the end, please remain seated until time is called. 4. Please look at the seating chart on the door as you enter and sit in your assigned seat. If you sit anywhere else you will lose 20 points. 5. Have your Comet card or other photo ID on the desk in front of you during the exam. 6. This test is closed book and closed notes. You will not need a calculator or other electronics. 7. Hand in all papers, including scratch paper, that you use during the exam. 8. Tests in the classroom will usually require a blue Scantron card, form 19641. You will be assigned a Student ID for this class that you will use for the duration of the semester. Use this number on the form, not your UTD ID. (Never put your UTD ID on anything. This is different from your NetID, which is the same as your e-mail address.) Here is what a properly filled out ScanTron Form looks like. Please don't fold or wrinkle the form. Notes for all exams: 1. If you have a question, raise your hand. I will come to you. 2. When answering an essay question, please do not repeat the question in your answer. For example, if the question is "Give an example of polymorphism," you do not need to begin your answer with "An example of polymorphism is...". 3. Read the questions and problems carefully so you answer the question being asked and answer all parts fully.`, `High-level Languages (below) Assembly Code Part of your program grade is dependent upon documentation, that is, the comments in your program. After going through well over a thousand programs in my last few years at UTD, it occured to me that I was making a bad assumption: that most students have been taught what constitutes good comments in a program. Therefore, below is what I consider to be a standard for your programs. If you follow these guidelines well, you will get full points for that aspect of your assignment. You should always use good naming conventions for your variables and methods, but this is not a substitute for good comments, although some would argue that it is. I have seen code in which the code itself can explain what is happening, but not why. I have also observed that if you can explain what you're doing in English, you probably understand it well enough to explain it to the computer. 1. Every module must have a block of comments at the beginning that contains the following information: Your name, your Net ID, the date on which you started writing the program, and your purpose in writing it. The purpose will generally be because it is an assignment for a particular class, and you should name the class and section here. This header must also include a general description of what the program or module does. For example: Written by John Cole for CS6326.001, assignment 4, starting April 1, 2017. NetID: jxc064000 2. Every method must have a comment above it that describes what the method does, and usually its inputs and outputs. The exception is tiny functions of a few lines where the name adequately describes the functionality and the return value, if any, is obvious. Get and Set methods fall into this category. 3. Major sections of code within a method must have comments explaining what they do. The beginnings of loops and conditionals are good places for this. Blocks that set up databases, initialize objects, and the like are also good places for a block of explanatory comments. The best comments describe what you're doing, and they also describe why you're doing it. 4. Some of your variables will need a comment next to them that explain what they signify and other useful information. However, good variable naming conventions (see next item) can make this less necessary. 5. Follow good naming conventions. Even temporary variables such as loop counters should have names that mean something and can be found using the text search. For example, you will never see this in my code: for (i=0; i<10; i++). Instead I'll use, at a minimum, something like this: for (ix=0; ix<10; ix++) because I can find the variable "ix". I know most development environments have a way to find variables and not just text, but I don't always rely upon that. In any case, i and j are seldom good variable names. If you're working with the rows and columns of a matrix, for example, why not use iRow and iCol? 6. When I was teaching at IIT I based part of the grade on the grammar and spelling in the comments. However, given the large population of students for whom English is not their first language, I no longer do this. Please do your best to be clear. 7. Don't write the code figuring you'll go back and document it later. Write the description before you write the code. For example, if you decide you need a method to, say, return an average price for a set of items in a database, define the method with its return value and parameters first. Then write the comments describing how the method works. Finally, write the method itself. If you come to office hours with code that contains no comments, you are likely to be sent away to do some writing. 8. I mention above that your comments should explain why you're doing certain things. Here are some examples of why you should do that. In one of my programs I had code to clear a buffer to blanks, and the comment said that this was so. However, it failed to explain that this was being done because ch`, `Assembly Code Assembler is different. It requires far better documentation than high-level language. See the examples below for what good code and documentation look like. Here are some rules: 1. Nearly every line should have a comment. Without this, many assembly language programs are nearly impossible to read and understand, even if you are the one who wrote it. Make the comments useful, same as for a high-level language. Not "Add one to $a0" but "Move pointer to next byte." See the difference? Keep line comments short and to the point. 2. Since register names are not particularly descriptive, it helps to have comments above a block of code describing the register contents when you enter that block along with what the block accomplishes. Use margins. Do not type past column 80 or 90 so I don't have to side-scroll to read your code. 3. Every assembly language has a directive that lets you set a symbol equal to a value. In MIPS this is the .eqv directive, which sets the symbol, the first argument, equal to the second thing. (This is very similar to the C/C++ #define directive.) This can be especially helpful for local variables that are at some offset from the stack pointer. See the example below. You can also use this to make your register names mean something. This helps you avoid what I call "magic numbers," numerical constants whose meaning you will forget within 10 minutes of using them and the meaning of which is completely opaque to anyone else reading your code. 4. Use labels where you need them. While many of us have a tendency to use short labels and put them on the same line as code, this is not necessary, and a longer, more descriptive label above a section of code may be much better. Speaking of labels, if you have a function named, for example, strcpy, if you have labels within it, use the name of the function and a number, for example, strcpy5. You will find that you need many more labels in assembly language because there are no looping constructs, just branch or jump instructions that require a label. Convention is that labels start in column 1. Do not use labels that you never reference. 5. Do not indent assembly code the way you would C++ or other high-level languages. Line up your instruction menemonics in colum 10 or 11, tab to the next column, and align the operands. To clarify: Labels in column 1. Instructions and pseudo-operations in column 10 or 11. Operands in column 19 or 20. Comments in 30 or so. Line up everything neatly to the extent that this is possible. 6. As you would with a high-level language, modularize. Put your simple utility functions such as copying strings, searches, and the like into a separately-assembled module. Once you have those working, you never need to look at them again. Do not use the .include directive for this code. 7. This is not strictly about documentation, but readability. Unless you have a loop, the control flow in your program should be generally from top to bottom. Since assembly code has no inherent structure, you must provide one. For example, testing something and branching if equal to a place further down in the code is fine. Branching from that place to someplace further up in the code is usually not; the technical term for this is "spaghetti code," because it goes everywhere. Similarly, don't put your subroutines in the middle and branch around them. Don't branch to a label that your code would fall through to anyway. See the bad example below. See the good example in Fibonacci.asm.`, `I couldn't get the example code to look right in HTML, so I have linked some useful things here. They have a .txt extension so you can see them rendered. SysCalls.asm Fibonacci.asm Bad example: bne $t0, '*', down back: sb $t0, 0($a0) ... j over down: li $t0, 'x' j back over: b over2 over2: ...` |  |
| `limit` | query | integer | max rows (default 50) |  |
| `offset` | query | integer | skip rows |  |

Example request:

```http
GET /announcements?title=I+give+many+exams+in+the+Testing+Center%2C+in+the+basement+of+the+McDermott+Library.+For+such+exams%2C+you+will+follow+Testing+Center+rules%2C+including+not+being+permitted+to+bring+in+anything%2C+such+as+notes%2C+a+calculator%2C+or+a+cell+phone.+The+test+will+auto-submit+at+the+end+of+the+allotted+time+and+your+work+will+be+saved.+However%2C+you+will+be+unable+to+work+on+the+test+past+the+time+allowed.+Rules+for+Paper+Exams%3A+1.+This+exam+is+timed.+You+may+turn+the+page+and+start+when+I+announce+the+start+and+you+will+put+your+pencils+or+pens+down+and+stop+writing+when+I+announce+the+stop+time.+I+may+extend+the+stop+time%2C+but+nominally+you+have+1+hour+15+minutes.+You+will+lose+20+points+if+you+are+still+writing+after+time+is+called.+2.+When+time+is+called%2C+pass+your+paper+to+your+left+and+remain+seated+until+I+have+collected+all+papers.+3.+If+you+finish+before+3+minutes+prior+to+the+stop+time+you+may+hand+in+your+paper+and+leave.+If+it+is+after+3+minutes+before+the+end%2C+please+remain+seated+until+time+is+called.+4.+Please+look+at+the+seating+chart+on+the+door+as+you+enter+and+sit+in+your+assigned+seat.+If+you+sit+anywhere+else+you+will+lose+20+points.+5.+Have+your+Comet+card+or+other+photo+ID+on+the+desk+in+front+of+you+during+the+exam.+6.+This+test+is+closed+book+and+closed+notes.+You+will+not+need+a+calculator+or+other+electronics.+7.+Hand+in+all+papers%2C+including+scratch+paper%2C+that+you+use+during+the+exam.+8.+Tests+in+the+classroom+will+usually+require+a+blue+Scantron+card%2C+form+19641.+You+will+be+assigned+a+Student+ID+for+this+class+that+you+will+use+for+the+duration+of+the+semester.+Use+this+number+on+the+form%2C+not+your+UTD+ID.+%28Never+put+your+UTD+ID+on+anything.+This+is+different+from+your+NetID%2C+which+is+the+same+as+your+e-mail+address.%29+Here+is+what+a+properly+filled+out+ScanTron+Form+looks+like.+Please+don%27t+fold+or+wrinkle+the+form.+Notes+for+all+exams%3A+1.+If+you+have+a+question%2C+raise+your+hand.+I+will+come+to+you.+2.+When+answering+an+essay+question%2C+please+do+not+repeat+the+question+in+your+answer.+For+example%2C+if+the+question+is+%22Give+an+example+of+polymorphism%2C%22+you+do+not+need+to+begin+your+answer+with+%22An+example+of+polymorphism+is...%22.+3.+Read+the+questions+and+problems+carefully+so+you+answer+the+question+being+asked+and+answer+all+parts+fully.&limit=3
```

Response (real data):

```json
{
  "total": 1,
  "limit": 3,
  "offset": 0,
  "items": [
    {
      "legacy_id": "f49336554f9d",
      "title": "I give many exams in the Testing Center, in the basement of the McDermott Library. For such exams, you will follow Testing Center rules, including not being permitted to bring in anything, such as notes, a calculator, or a cell phone. The test will auto-submit at the end of the allotted time and your work will be saved. However, you will be unable to work on the test past the time allowed. Rules for Paper Exams: 1. This exam is timed. You may turn the page and start when I announce the start and you will put your pencils or pens down and stop writing when I announce the stop time. I may extend the stop time, but nominally you have 1 hour 15 minutes. You will lose 20 points if you are still writing after time is called. 2. When time is called, pass your paper to your left and remain seated until I have collected all papers. 3. If you finish before 3 minutes prior to the stop time you may hand in your paper and leave. If it is after 3 minutes before the end, please remain seated until time is called. 4. Please look at the seating chart on the door as you enter and sit in your assigned seat. If you sit anywhere else you will lose 20 points. 5. Have your Comet card or other photo ID on the desk in front of you during the exam. 6. This test is closed book and closed notes. You will not need a calculator or other electronics. 7. Hand in all papers, including scratch paper, that you use during the exam. 8. Tests in the classroom will usually require a blue Scantron card, form 19641. You will be assigned a Student ID for this class that you will use for the duration of the semester. Use this number on the form, not your UTD ID. (Never put your UTD ID on anything. This is different from your NetID, which is the same as your e-mail address.) Here is what a properly filled out ScanTron Form looks like. Please don't fold or wrinkle the form. Notes for all exams: 1. If you have a question, raise your hand. I will come to you. 2. When answering an essay question, please do not repeat the question in your answer. For example, if the question is \"Give an example of polymorphism,\" you do not need to begin your answer with \"An example of polymorphism is...\". 3. Read the questions and problems carefully so you answer the question being asked and answer all parts fully."
    }
  ]
}
```

### `GET /announcements/{id}`

One Announcement by its legacy id

| Name | In | Type | Meaning | Required |
|---|---|---|---|---|
| `id` | path | string | legacy id | yes |

Example request:

```http
GET /announcements/707359fc4ff1
```

Response (real data):

```json
{
  "legacy_id": "707359fc4ff1",
  "date_posted": "12/18/2023",
  "announcement": "From Cal Newport's book Deep Work: The Deep Work Hypothesis: The ability to perform deep work is becoming increasingly rare at exactly the same time that it is becoming increasingly valuable in our economy. As a consequence, the few who cultivate this skill and then make it the core of their working life will thrive."
}
```


## Course

79 records. Fields: `term` (string), `course_details` (string)

_No form was seen for this entity on the legacy site, so it has no write endpoints._

### `GET /courses`

List Course records, with filters

| Name | In | Type | Meaning | Required |
|---|---|---|---|---|
| `term` | query | string | `term` contains (case-insensitive) |  |
| `limit` | query | integer | max rows (default 50) |  |
| `offset` | query | integer | skip rows |  |

Example request:

```http
GET /courses?limit=3
```

Response (real data):

```json
{
  "total": 79,
  "limit": 3,
  "offset": 0,
  "items": [
    {
      "legacy_id": "21155380afaa",
      "term": "Courses Fall 2026",
      "course_details": "CS3162 Professional Responsibility in CS and SE on Tuesday/Thursday from 8:00 AM to 8:50 (Section 052) and 9:00 to 9:50 (Section 051) in SCI 1.220"
    },
    {
      "legacy_id": "6669de66b481",
      "term": "Courses Fall 2026",
      "course_details": "CS4485.0W1 Senior Design on Tuesday from 1:00 to 3:00; Friday from 2:15 to 4:00 Online on Teams; in person meetings TBA"
    },
    "... 1 more"
  ]
}
```

### `GET /courses/{id}`

One Course by its legacy id

| Name | In | Type | Meaning | Required |
|---|---|---|---|---|
| `id` | path | string | legacy id | yes |

Example request:

```http
GET /courses/21155380afaa
```

Response (real data):

```json
{
  "legacy_id": "21155380afaa",
  "term": "Courses Fall 2026",
  "course_details": "CS3162 Professional Responsibility in CS and SE on Tuesday/Thursday from 8:00 AM to 8:50 (Section 052) and 9:00 to 9:50 (Section 051) in SCI 1.220"
}
```


## CourseInfo

5 records. Fields: `title` (string), `page` (integer), `source_url` (string), `found_on` (string), `file_type` (enum)

_No form was seen for this entity on the legacy site, so it has no write endpoints._

### `GET /course_infos`

List CourseInfo records, with filters

| Name | In | Type | Meaning | Required |
|---|---|---|---|---|
| `min_page` | query | integer | `page` ≥ |  |
| `max_page` | query | integer | `page` ≤ |  |
| `source_url` | query | string | `source_url` equals: `https://personal.utdallas.edu/~John.cole/ProgrammingTips/AndroidFileIO.html` |  |
| `found_on` | query | string | `found_on` equals: `https://personal.utdallas.edu/~John.cole/ProgrammingTips/AndroidFileIO.html` |  |
| `file_type` | query | enum | `file_type` equals: `HTML`, `image`, `pdf` |  |
| `limit` | query | integer | max rows (default 50) |  |
| `offset` | query | integer | skip rows |  |
| `sort` | query | string | sort field, `-` = descending: `page`, `-page` |  |

Example request:

```http
GET /course_infos?min_page=1&source_url=https%3A%2F%2Fpersonal.utdallas.edu%2F~John.cole%2FProjects%2FRobot-Version2.JPG&limit=3
```

Response (real data):

```json
{
  "total": 1,
  "limit": 3,
  "offset": 0,
  "items": [
    {
      "legacy_id": "robot-version2-9d39a4-p1",
      "title": "Distance-sensing robot",
      "page": 1,
      "source_url": "https://personal.utdallas.edu/~John.cole/Projects/Robot-Version2.JPG",
      "found_on": "https://personal.utdallas.edu/~John.cole/Projects/Projects.html",
      "file_type": "image"
    }
  ]
}
```

### `GET /course_infos/{id}`

One CourseInfo by its legacy id

| Name | In | Type | Meaning | Required |
|---|---|---|---|---|
| `id` | path | string | legacy id | yes |

Example request:

```http
GET /course_infos/AndroidFileIO.html
```

Response (real data):

```json
{
  "legacy_id": "AndroidFileIO.html",
  "title": "Android Programming Android File I/O examples Android File I/O problem and solution Code snippets for animation using a thread on a timer Low-Pass Filter Array Adapter for ListView"
}
```

