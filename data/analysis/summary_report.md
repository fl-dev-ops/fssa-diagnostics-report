# Diagnostic Sessions And WhatsApp Feedback Summary

## Scope

This summary is based on:

- `39` manually tagged WhatsApp feedback entries
- `96` pre-diagnostic sessions from the database
- `67` completed sessions (`59` with report generated, `8` completed without report)
- turn-level transcript review for completed sessions, using student turn + next Sana response pairs

The supporting CSVs live in this folder:

- [aggregate_metrics.csv](/Users/suryaumapathy/Developers/Github/foreverlearning/streamlit/diagnostic-report/data/analysis/aggregate_metrics.csv)
- [whatsapp_feedback_tagged.csv](/Users/suryaumapathy/Developers/Github/foreverlearning/streamlit/diagnostic-report/data/analysis/whatsapp_feedback_tagged.csv)
- [user_sessions_feedback.csv](/Users/suryaumapathy/Developers/Github/foreverlearning/streamlit/diagnostic-report/data/analysis/user_sessions_feedback.csv)
- [session_pair_relevance.csv](/Users/suryaumapathy/Developers/Github/foreverlearning/streamlit/diagnostic-report/data/analysis/session_pair_relevance.csv)
- [session_relevance_summary.csv](/Users/suryaumapathy/Developers/Github/foreverlearning/streamlit/diagnostic-report/data/analysis/session_relevance_summary.csv)
- [shareable_student_sessions_full.csv](/Users/suryaumapathy/Developers/Github/foreverlearning/streamlit/diagnostic-report/data/analysis/shareable_student_sessions_full.csv)

## 1. WhatsApp Feedback Tagging

Each WhatsApp feedback message was manually tagged into one primary bucket:

- `Technical`: `25`
- `UI/UX`: `10`
- `Conversational`: `4`

### Quick read

The dominant pain is technical rather than conversational.

The most common technical issues were:

- speech-to-text inaccuracies
- answers not being captured or submitted
- sessions getting stuck on "waiting for agent"
- lag or slow response time
- audio capture and voice recognition problems
- sessions skipping to the next question unexpectedly

The UI/UX comments were more about control and visibility:

- users wanted live subtitles or visible text while speaking
- users wanted a stop/delete option before sending
- some users could not find the exit/end call action easily
- a few users felt the chat card or layout on laptop was too constrained

Conversational issues were the smallest bucket, but still important:

- a few students felt Sana kept asking a fixed set of questions
- some felt the response did not actually follow what they had said
- some positive conversational feedback also appeared, especially around friendliness and clarity

## 2. Session Funnel

Session funnel from the database:

- Sessions initiated: `96`
- Completed with report generated: `59`
- Completed but no report yet: `8`
- Dropped mid-way: `29`

### Quick read

About `70%` of sessions reached completion in some form (`67 / 96`), while about `30%` dropped before completion (`29 / 96`).

The main product concern is not just report generation, but session reliability before the student gets through the experience. This lines up with the WhatsApp feedback, which repeatedly mentions connection delay, dropped turns, skipped answers, and recording problems.

### What "dropped mid-way" means in this dataset

For this analysis, "dropped mid-way" maps to sessions with `session_status = STARTED`.

After checking all `29` such sessions against the stored transcript files:

- all `29` have `0` transcript messages
- none contain a captured agent turn
- none contain a captured student turn

So in this dataset, these are better understood as:

- sessions that were initiated
- but did not progress to a captured conversation

This means we do **not** see evidence here of conversations that started and then failed halfway through. The failure appears to happen before any transcript exchange is stored.

## 3. Form Completion

For the current database snapshot, all tracked form/profile fields were present for all `96` sessions:

- `name`: `96 / 96`
- `email`: `96 / 96`
- `phone_number`: `96 / 96`
- `preferred_name`: `96 / 96`
- `institution`: `96 / 96`
- `degree`: `96 / 96`
- `stream`: `96 / 96`
- `year_of_study`: `96 / 96`
- `coach`: `96 / 96`

### Quick read

There is no evidence of a form-completion problem in this dataset.

That means the forms themselves were not a blocker in this sample. The operational problems happened after form completion, during the live interview flow.

If the goal is to argue that these fields matter, the strongest case here is not missingness. The stronger case is downstream usefulness:

- these fields make user-to-session-to-feedback analysis possible
- they enable matching user feedback back to session outcomes
- they help explain report quality and relevance by student context

## 4. Relevance Of Sana Responses

For completed sessions, each student turn was paired with the next Sana response and reviewed for:

- student intent:
  `aspiring job`, `dream company`, `backup plan`, `senior reference`, `day in life`, `JD awareness`, `tools/skills`, `unclear`
- response relevance:
  `Relevant`, `Partially Relevant`, `Not Relevant`

### Aggregate result

- `Relevant`: `22.89%`
- `Partially Relevant`: `71.51%`
- `Not Relevant`: `5.61%`

### Quick read

Most Sana responses were not completely off-topic, but they were often only partially aligned with what the student had just said.

The pattern is:

- Sana usually stayed in the same broad career/interview zone
- but many replies looked like generic follow-up prompts rather than sharply targeted responses to the student's exact point
- fully off-topic or clearly misaligned responses were relatively rare, but still visible in a few sessions

### Sessions that were mostly not relevant

These sessions were flagged for manual review because not-relevant responses were high relative to relevant ones:

- `cmnr10cdu000304lbfvxc7rr4`
- `cmnr7kymf000k04jrq66gh93o`
- `cmnr7mp51000p05ifwi0v1nrs`
- `cmnr7tewk000304jzbun78uyf`
- `cmnr7valg000804jzagu2y5h0`

### Interpretation

This is not a "Sana is failing most of the time" result.

It is more a "Sana is usually adjacent, but not always precise" result.

That suggests the next product improvement is not only model quality. It may also require:

- stronger turn grounding
- better handling of mixed-language or noisy student inputs
- more explicit carry-forward of the student's last answer into the next prompt

### Example transcript pairs

#### Relevant

Session ID: `cmnr4hygf000104jrhez16k4k`

- Student intent: `aspiring job`
- Student: `I am looking at becoming a software engineer.`
- Sana: `Nice, software engineer is a very clear direction. What made you choose software engineering specifically?`
- Why this is relevant: Sana stays directly on the student’s stated goal and asks a focused follow-up.

#### Partially Relevant

Session ID: `cmnr16ngv0007gjse9m5m9vv0`

- Student intent: `unclear`
- Student: `Okay.`
- Sana: `Okay, thanks for staying with me, Surya. When you think about your future job, what kind of work do you see yourself doing or what role comes to your mind first?`
- Why this is partially relevant: the follow-up is reasonable, but the student input is too thin to judge strong alignment.

#### Not Relevant

Session ID: `cmnr7jmg9000304jr2xg8n6q7`

- Student intent: `tools/skills`
- Student: `I'd always stop and then react immediately.`
- Sana: `Okay, so it sounds like you’re not fully sure about the exact role name yet, and that’s alright. When you picture yourself working in a company after this course, what kind of tasks do you imagine doing in a normal day?`
- Why this is not relevant: Sana moves away from the student’s skill/tool statement and reframes the conversation instead of responding to it.

## 5. Average Call Duration

For completed sessions with reports, the average call duration was:

- `684.14` seconds
- approximately `11.4 minutes`

### Quick read

This is long enough that friction compounds.

When speech recognition, transcript visibility, or latency fail even occasionally, the student notices it repeatedly because the session is not a short one-step flow.

## 6. Latency Instrumentation

The current transcript data does **not** include separate timestamps for:

- STT output
- LLM response generation
- TTS start

The transcript structure currently only has:

- `source`
- `updatedAt`
- `messages[]`

And each message only has:

- `id`
- `role`
- `text`
- `timestamp`


## 7. Overall Takeaway

The data points to a clear story:

- the biggest issues are technical reliability and turn handling
- form completion is not the problem in this dataset
- session drop-off is meaningful and likely tied to technical friction
- Sana is usually directionally relevant, but often not precise enough at the turn level
- better latency instrumentation is required before making a strong claim about where response delay is coming from

If this needs to be presented to others, the cleanest framing is:

1. The experience is getting users into sessions successfully often enough, but not reliably enough.
2. The main pain is technical, especially speech capture, transcript accuracy, skipped turns, and waiting/latency.
3. Conversation quality is not the primary failure mode, but relevance can be tightened substantially.
