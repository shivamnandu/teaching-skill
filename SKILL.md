---
name: teaching-skill
description: "Complete university-teaching toolkit for professors, lecturers and TAs: 15 specialist modules, 89 modes. Backward course design, learning outcomes, syllabus, lesson plans, lecture notes, slides and rendered decks, active-learning activities, cases, exams, quizzes, rubrics, question banks, AI-era assessment integrity, labs and autograders, video scripts, student feedback, recommendation letters, submission and format checks, TA handbooks and grading calibration, announcements, LMS packaging, learner diagnostics (学情分析), bilingual glossaries, accreditation mapping, evaluation analysis, teaching portfolio and statement, plus a full course pipeline with quality gates. Use whenever the user mentions course design, syllabus, lesson, exam, rubric, grading, student work, TAs or teaching evaluations, writes in Chinese (备课, 教案, 课程设计, 出题, 评分标准, 评教, 助教), or uses a ts-* alias such as ts-course, ts-exam, ts-lesson, ts-rubric."
license: MIT
metadata:
  version: "1.0.2"
  upstream: "teaching-skills v1.2.0 by Jiaxing Yu (MIT)"
  coverage: "15 modules, 89 modes, 76 agents, 30 command aliases"
  merged: "2026-09-26"
---

# Teaching Skill — the complete teaching suite behind one entry point

This skill is a complete toolkit for university teaching: 15 specialist modules covering the
lifecycle **design → build → assess → deliver → reflect → improve**, plus production, operations,
compliance and learner-analysis modules — 89 modes and 76 role-specific agent prompts in
all. Every upstream file is carried (only build debris and redundant stub files are omitted;
`MERGE_NOTES.md` lists every difference). This file decides **which module to use** and **which rules never
bend**; the modules hold the craft. Load only what the current request needs.

> **The professor is the pilot.** You draft, structure, audit and flag; the professor decides. The suite
> handles structure and grunt work so the professor can spend attention on their discipline, their
> students and what matters.

**Handling a request, in order:**

1. If `course_passport.yaml` exists in the working directory, load it first (§2, Passport discipline).
2. Pick the module: an alias if the message starts with one, otherwise by intent (§3). If it is ambiguous,
   prefer the guided path or ask one focused question rather than producing an unwanted artifact.
3. Read `<module>/WORKFLOW.md` and follow its mode table, workflow phases and Iron rules.
4. Open only the agent, reference and template files the current phase names.
5. Present work at checkpoints in the fixed four-block format (§2); write artifacts into the professor's
   working directory; update the passport only after the professor confirms.
6. Run the validators when the workflow calls for them (§6) and report their findings by check id.

## 1. How this skill is laid out

- **Base directory** = the folder that contains this `SKILL.md` (the harness names it when the skill
  loads). Every path in this file is relative to it.
- Each module is a folder `<module>/` whose entry file is **`<module>/WORKFLOW.md`**. Upstream called that
  file `SKILL.md`; it is renamed so that exactly one `SKILL.md` — this router — registers as a skill. A
  module folder also holds `agents/`, `references/` and `templates/`.
- Shared contracts are in `shared/`, executable checks in `scripts/`, the 30 command recipes in
  `commands/`, worked examples in `examples/`, architecture in `docs/ARCHITECTURE.md`, and the mode map in
  `MODE_REGISTRY.md`. `INDEX.md` lists every file with a one-line purpose.
- **Reading paths inside module files.** `shared/…`, `scripts/…`, `commands/…`, `docs/…`, `examples/…`,
  `MODE_REGISTRY.md` and `<other-module>/…` mean *relative to the base directory*. `agents/…`,
  `references/…` and `templates/…` mean *the current module's own folder*. A mention of `SKILL.md` inside a
  module means that module's `WORKFLOW.md`.
- **Two directories are in play.** The professor's files (`course_passport.yaml`, `syllabus.md`,
  `lessons/…`, `assessments/…`) live in the *working directory*; this skill's files live in the base
  directory. A workflow line such as `python3 scripts/check_passport.py <passport>` therefore has to be run
  as `python "<base-dir>/scripts/check_passport.py" <passport>` (`python3` on macOS/Linux; `python` or
  `py -3` on Windows). Never write the professor's artifacts into the skill folder.

**Load lazily.** Read (1) this file; (2) the chosen module's `WORKFLOW.md`; (3) only the agent files for the
phase you are running; (4) references and templates when the workflow names them; (5) the shared
protocols in §2 when their trigger applies. Do not bulk-read the tree. If this router and a module's
`WORKFLOW.md` ever disagree, follow the `WORKFLOW.md` for that module and tell the professor.

## 2. Standing rules — every module, every output

Each module's `WORKFLOW.md` adds its own Iron rules; these hold everywhere. They come from `CLAUDE.md`
and the `shared/` protocols; the right-hand column names the protocol that holds the full text — open it
when its rule is in play.

| Rule | Full text |
|---|---|
| **Checkpoints — the professor decides.** Stop at a checkpoint at the end of every stage, before anything is treated as final, before anything student-facing or person-affecting leaves the session, and at gate closures. Emit the four labeled blocks every time — **Produced**, **Key decisions made for you (review these)**, **Flags**, **Open questions** — writing "none" rather than dropping one, then ask "Ready to proceed, or what should change?". Surface every consequential default. "Just proceed" collapses checkpoints to minimal confirmations; it never skips the confirmation itself and never applies to gate acknowledgments or person-affecting outputs. When the professor writes in another language, translate the four labels and keep the English label in parentheses, so the fixed structure stays recognizable. | `shared/checkpoint_protocol.md` |
| **No invented context.** Institutional policy, calendar dates, room numbers and learner facts are asked for or written as `[NEEDS PROFESSOR INPUT: what and where to find it]`. Uncertain domain claims in generated teaching material carry `[VERIFY: claim — why uncertain]`. | `shared/output_self_check.md` |
| **Person-affecting outputs** — feedback on named work, recommendation letters, intervention plans, integrity-concern write-ups, anything evaluative about a named TA — are **evidence-bound** (every evaluative claim traces to material the professor provided; no invented anecdotes, ratings or comparisons; gaps become `[NEEDS PROFESSOR INPUT]`), **draft-only** (never auto-sent or finalized) and end with a one-line **verify-before-send reminder** that no configuration or "just proceed" removes. Student data never enters the Course Passport. | `shared/checkpoint_protocol.md` |
| **Integrity by design, not detection.** Never recommend AI-detection tools as an integrity mechanism; use per-assignment policy tiers (P / D / O) and structural resilience. | `shared/ai_era_integrity.md` |
| **Evidence honesty.** Student evaluations are biased, small-sample evidence of student experience, not a teaching-quality score; every analysis says what the evidence cannot show. | `shared/pedagogy_foundations.md` §11 |
| **Passport discipline.** If `course_passport.yaml` exists in the working directory, load it before asking for context it already holds. Append, never overwrite another stage's fields; `confirmed_by_professor` is set only at a real confirmation; "unknown" is a legitimate value and a guess recorded as fact is not. `iteration_history` has one writer, `iteration_coach_agent` (pipeline Stage 6): other modules produce aggregate evidence and hand it over, so where a module says "append to `iteration_history`", prepare the entry, show it at the checkpoint, and let the iteration coach or the professor write it. | `shared/course_passport_schema.md` |
| **Self-check before presenting.** Run the seven-line output self-check (grounding, no silent defaults, honest markers, person-affecting guardrails, voice and altitude, accessibility floor, passport discipline) and surface only failing lines under **Flags**. | `shared/output_self_check.md` |
| **Pedagogy defaults are defaults.** Cite Pedagogy Foundations by § when explaining a flag; the professor's discipline knowledge wins; a logged decision is not re-argued; do not lecture unprompted. | `shared/pedagogy_foundations.md` |
| **Gate mechanics.** Gate 1.5 (alignment) and Gate 3.5 (quality) are deterministic checklists followed by professor acknowledgment; a BLOCK returns to the producing stage, at most 3 rounds before it becomes a recorded professor decision; a WARN may be dismissed with a logged reason and is never re-raised. The numeric thresholds (workload, weight caps) live in one file. | `shared/alignment_gate_protocol.md`, `shared/quality_gate_protocol.md`, `shared/workload_constants.md` |

Two more habits from the suite's routing discipline: when a request is ambiguous between guided and direct
production, prefer the guided/Socratic path (an unwanted full artifact wastes more than a clarifying
dialogue), and detect the professor's intent in any language — English and Simplified Chinese trigger
words ship by default (§3.4); the modes themselves are language-agnostic.

## 3. Route the request

### 3.1 Aliases (`ts-*`)

If the message starts with an alias — `/ts-exam` or plain `ts-exam` — strip it, read `commands/<alias>.md`,
then open that module's `WORKFLOW.md` and run the named mode; the rest of the message is the request. In
Claude Code, invoke this skill with `/teaching-skill ts-exam …`, or say it in words. To get real
`/ts-*` slash commands back, copy the wrappers in `install/claude-code-commands/` into `~/.claude/commands/`
(see `MERGE_NOTES.md`).

| Alias | Module | Mode | What it does |
|---|---|---|---|
| `/ts-accredit` | accreditation-mapper | `map` | outcomes-to-standards matrix |
| `/ts-activities` | lesson-builder | `activities` | active-learning activity design |
| `/ts-align` | course-designer | `align-check` | constructive-alignment audit |
| `/ts-announce` | course-publisher | `announcement` | student announcement draft |
| `/ts-audit` | submission-auditor | `audit` (or `batch-audit` for multiple submissions) | check submissions against the spec |
| `/ts-calibrate` | ta-coordinator | `calibration` | grading norming session |
| `/ts-cohort` | cohort-analyst | `cohort-profile` | analyze student readiness data |
| `/ts-course` | course-designer | `full` | complete backward course design |
| `/ts-dashboard` | teaching-pipeline | `dashboard` | single-file HTML course overview |
| `/ts-deck` | deck-studio | `deck` | render an actual slide deck |
| `/ts-diagnostic` | cohort-analyst | `instrument` | design a pre-lesson diagnostic |
| `/ts-evals` | teaching-reflector | `eval-analysis` | student evaluation analysis |
| `/ts-exam` | assessment-architect | `exam` | blueprint-first exam construction |
| `/ts-feedback` | student-mentor | `feedback` | structured feedback on student work |
| `/ts-full` | teaching-pipeline | `full` | complete teaching lifecycle |
| `/ts-glossary` | bilingual-courseware | `glossary` | course terminology glossary |
| `/ts-integrity` | assessment-architect | `integrity-check` | AI-resilience audit |
| `/ts-lab` | lab-forge | `lab` | complete executable lab package |
| `/ts-lesson` | lesson-builder | `full` | complete class-meeting package |
| `/ts-letter` | student-mentor | `recommendation-letter` | intake interview → letter |
| `/ts-midcourse` | teaching-reflector | `midcourse` | mid-semester feedback loop |
| `/ts-outcomes` | course-designer | `outcomes-only` | Bloom-tagged learning outcomes |
| `/ts-redesign` | course-designer | `redesign` | evidence-based course redesign |
| `/ts-rubric` | assessment-architect | `rubric` | rubric design |
| `/ts-script` | media-scripter | `script` | mini-lecture video script |
| `/ts-spec` | submission-auditor | `spec` | compile a checkable Submission Spec |
| `/ts-statement` | teaching-reflector | `teaching-statement` | teaching philosophy statement |
| `/ts-status` | teaching-pipeline | `status` | where is my course? |
| `/ts-syllabus` | course-designer | `syllabus-only` | syllabus from existing design |
| `/ts-translate` | bilingual-courseware | `translate` | glossary-bound translation |

### 3.2 Pick the module by intent

Single-artifact requests go to the specific module, not the pipeline. Lifecycle or multi-stage requests
("prepare my whole course", "new semester", "what's next for my course?") go to `teaching-pipeline`.

| Module | Use it when the professor wants… | Route elsewhere when… |
|---|---|---|
| `teaching-pipeline` | the whole lifecycle in order over the Course Passport: "prepare my whole course", a new semester, "what's next?", course status or dashboard, resuming mid-way | one artifact is enough → the specific module below |
| `course-designer` | course-level design: outcomes, assessment plan, semester schedule, syllabus, redesign of an existing course, alignment audit, online/async adaptation; Socratic guidance from a blank page | a single class meeting → `lesson-builder`; the actual exam, rubric or brief → `assessment-architect`; analysis of evaluations → `teaching-reflector` |
| `lesson-builder` | class-meeting materials: lesson plan, lecture notes, slide outline, active-learning activity, teaching case, discussion guide, flipped session — one meeting or whole passport weeks | outcomes, schedule or syllabus → `course-designer`; graded instruments → `assessment-architect` |
| `assessment-architect` | graded instruments: blueprint-first exam, quiz, question bank, rubric, TILT project brief or group project, AI-resilience audit, answer key, item analysis, grade analysis, accommodation variant of an assessment | deciding types, weights or timing → `course-designer`; ungraded practice → `lesson-builder`; comments on a student's work → `student-mentor`; whether an accommodation is granted → the disability/accessibility office |
| `student-mentor` | anything about an individual student: feedback on work, struggling-student outreach, recommendation letter, difficult email, office-hours prep, advisee mentoring plan, suspected integrity case (evidence record only) | class-wide evaluation analysis → `teaching-reflector`; designing the rubric → `assessment-architect`; course policies → `course-designer`; cohort readiness → `cohort-analyst` |
| `submission-auditor` | checking submissions against a template, requirements document, rubric or exemplar: compile a checkable spec, audit one submission or a batch with located findings, student self-check, calibrate the spec | designing the assignment or rubric → `assessment-architect`; coaching beyond the spec → `student-mentor` `feedback`; scoring is the professor's act |
| `teaching-reflector` | teaching evidence and career artifacts: evaluation analysis, mid-semester feedback, peer observation, portfolio, teaching statement, SoTL design | acting on one student → `student-mentor`; redesigning the course → `course-designer` (eval-analysis feeds its `redesign`) |
| `deck-studio` | rendered slide decks (Marp, Pandoc, Beamer, python-pptx), a course theme, code-generated figures, handouts, posters | what the slides should say → `lesson-builder` `slides-outline` |
| `lab-forge` | executable STEM lab and programming assignments: datasets with recoverable ground truth, starter code, autograders, verified solutions, variants | the assignment brief or rubric → `assessment-architect`; checking submissions → `submission-auditor`; ungraded in-class exercises → `lesson-builder` |
| `media-scripter` | recorded media: mini-lecture video scripts, storyboards, episode series, captions and transcripts, audio adaptations | what a flipped class covers → `lesson-builder` `flipped`; the slides shown in the video → `deck-studio` |
| `course-publisher` | student-facing communication and packaging from the passport: announcements, weekly emails, course site, LMS package, FAQ | one individual student → `student-mentor`; building lessons or slides → `lesson-builder` / `deck-studio`; changing syllabus content or policy → `course-designer` |
| `ta-coordinator` | teaching-team operations: TA onboarding handbook, grading calibration session, hours-balanced allocation, TA meetings, cross-TA consistency | designing the rubric → `assessment-architect`; giving feedback to students → `student-mentor`; checking submissions → `submission-auditor` |
| `accreditation-mapper` | accreditation and program documentation: course-to-program-to-standard matrix, evidence package, gap analysis, self-study drafts | revising the outcomes → `course-designer`; program-level curriculum restructuring is out of scope |
| `bilingual-courseware` | bilingual materials: terminology glossary, glossary-bound translation, paired-version sync, terminology audit (default EN ⇄ 简体中文) | writing the original materials → the producing module; translating announcements or FAQ → `course-publisher` bound to this glossary; translation unrelated to a course is out of scope |
| `cohort-analyst` | cohort learner analysis (学情分析): ungraded diagnostics, aggregate readiness profile, lesson calibration, evidence-based grouping, mid-term progress | "which students need help?" → `student-mentor`; graded quizzes → `assessment-architect`; end-of-term evaluations → `teaching-reflector` |

### 3.3 Boundary rules that resolve most ambiguity

- A passport already on disk plus a vague request → pipeline `status` first; never restart `full` on top of
  an existing passport.
- Slide *content* (what the slides say) is `lesson-builder` `slides-outline`; slide *files* are
  `deck-studio`. Lecture notes for a live class are `lesson-builder`; what is *said on camera* is
  `media-scripter`.
- Graded quizzes and exams are `assessment-architect`; ungraded diagnostics are `cohort-analyst`
  `instrument`; ungraded in-class checks are `lesson-builder`.
- A whole class or cohort (aggregates) is `cohort-analyst` or `teaching-reflector`; **an individual
  student — including "which students need help?" — is `student-mentor`**, initiated by the professor with
  the evidence in hand, never nominated from cohort data.
- Preventing AI misuse through assessment design is `assessment-architect` `integrity-check`; a *live
  suspected case* is `student-mentor` `integrity-case` (evidence record and process routing only — no
  verdict, guilt estimate or sanction, ever).
- Deciding assessment types, weights and timing is `course-designer`; building the instrument is
  `assessment-architect`; checking submissions against a spec is `submission-auditor` (audit, don't grade).
- When a request mixes modes, run them in the order the professor must act, not the order mentioned.

### 3.4 Trigger keywords (English and 中文) by module

| Module | Trigger keywords (verbatim from the module's description) |
|---|---|
| teaching-pipeline | teach a course, prepare my course, semester, full course pipeline, course lifecycle, new semester, what's next for my course, course status, 开课, 备一门课, 新学期, 整门课, 课程全流程, 教学流程, 下一步 |
| course-designer | design a course, course design, syllabus, learning outcomes, learning objectives, course schedule, redesign my course, new course, curriculum, teaching plan, align my course, 设计课程, 课程设计, 教学大纲, 课程大纲, 教学目标, 学习目标, 课程改革, 培养方案 |
| lesson-builder | lesson plan, lecture notes, slides, slide outline, in-class activity, active learning, case study, discussion questions, flipped classroom, prepare my class, teach next week, 备课, 教案, 讲稿, 课件, 课堂活动, 案例教学, 讨论课, 翻转课堂, 互动环节 |
| assessment-architect | exam, midterm, final, quiz, test questions, rubric, grading criteria, project brief, assignment design, question bank, item analysis, academic integrity, AI-proof, 出题, 试卷, 考试, 测验, 评分标准, 评分量表, 课程项目, 题库, 试题分析, 学术诚信 |
| student-mentor | feedback on student work, grade comments, struggling student, recommendation letter, reference letter, student email, office hours, advising, mentoring, thesis student, difficult conversation, 学生反馈, 批改, 评语, 推荐信, 学生邮件, 答疑, 指导学生, 研究生指导, 师生沟通 |
| submission-auditor | check submissions, format check, check against template, does this meet the requirements, lab report check, audit student work, compliance check, submission requirements, batch check, 检查作业, 格式检查, 格式审查, 实验报告检查, 论文格式, 检查是否符合要求, 批量检查, 提交规范 |
| teaching-reflector | student evaluations, course evaluations, teaching feedback analysis, mid-semester feedback, peer observation, teaching portfolio, teaching statement, teaching philosophy, SoTL, scholarship of teaching, improve my course, what went wrong, 学生评教, 教学评价, 期中反馈, 同行听课, 教学档案, 教学理念, 教学陈述, 教学研究, 课程改进 |
| deck-studio | make slides, PPT, PowerPoint, slide deck, beamer, presentation, lecture slides, poster, render my slides, slide theme, 做PPT, 幻灯片, 课件制作, 讲义, 海报, 演示文稿 |
| lab-forge | lab assignment, programming assignment, problem set code, dataset for students, synthetic data, starter code, autograder, solution notebook, Jupyter, 实验作业, 编程作业, 数据集, 实验数据, 起始代码, 自动评分, 自动批改, 参考答案 |
| media-scripter | video script, record a lecture, lecture video, mini-lecture, screencast, storyboard, captions, transcript, subtitles, podcast, flipped video, MOOC, 录课, 慕课, 视频脚本, 微课, 录屏, 字幕, 讲稿, 播客, 翻转课堂视频 |
| course-publisher | announcement, weekly email, course website, course page, LMS, Canvas, Moodle, Blackboard, post materials, publish course, student FAQ, 课程通知, 周报, 课程网站, 课程主页, 学习平台, 发布课件, 课程公告, 常见问题 |
| ta-coordinator | TA, teaching assistant, grader, grading team, TA training, TA meeting, grading calibration, norming session, divide grading, TA handbook, 助教, 助教培训, 助教手册, 批改分工, 评分一致性, 助教会议, 阅卷 |
| accreditation-mapper | accreditation, ABET, AACSB, program outcomes, curriculum map, self-study, assessment report, learning outcomes assessment, continuous improvement report, 专业认证, 工程教育认证, 培养方案, 毕业要求, 课程目标达成, 自评报告, 持续改进, 课程矩阵 |
| bilingual-courseware | translate course materials, bilingual course, English-medium instruction, EMI, terminology glossary, Chinese version, parallel syllabus, 双语教学, 双语课程, 全英文授课, 术语表, 专业术语, 翻译课件, 中英对照, 中文版 |
| cohort-analyst | student readiness, pre-assessment, diagnostic quiz, pre-lesson questionnaire, prior knowledge survey, learning analytics, ability levels, class profile, differentiation, grouping, 学情分析, 学情, 摸底, 前测, 预习问卷, 课前问卷, 学生基础, 分层教学, 分组 |

## 4. Every module and every mode

| Module | Role | Modes (all) | Agents |
|---|---|---|---|
| [`teaching-pipeline`](teaching-pipeline/WORKFLOW.md) | orchestrator | `full` · `mid-entry` · `status` · `new-term` · `dashboard` | 4 |
| [`course-designer`](course-designer/WORKFLOW.md) | core · 1 DESIGN | `full` · `socratic` · `outcomes-only` · `syllabus-only` · `redesign` · `align-check` · `async-design` | 7 |
| [`lesson-builder`](lesson-builder/WORKFLOW.md) | core · 2 BUILD | `full` · `lecture-notes` · `slides-outline` · `activities` · `case-study` · `discussion-guide` · `flipped` · `week-batch` | 6 |
| [`assessment-architect`](assessment-architect/WORKFLOW.md) | core · 3 ASSESS | `exam` · `quiz` · `question-bank` · `rubric` · `project-brief` · `integrity-check` · `item-analysis` · `answer-key` · `grade-analysis` · `group-assessment` · `accommodate` | 10 |
| [`student-mentor`](student-mentor/WORKFLOW.md) | core · 4 DELIVER | `feedback` · `struggling-student` · `recommendation-letter` · `student-email` · `office-hours` · `mentoring-plan` · `integrity-case` | 6 |
| [`submission-auditor`](submission-auditor/WORKFLOW.md) | core · 4 DELIVER | `spec` · `audit` · `batch-audit` · `self-check` · `calibrate` | 4 |
| [`teaching-reflector`](teaching-reflector/WORKFLOW.md) | core · 5 REFLECT | `eval-analysis` · `midcourse` · `peer-observation` · `portfolio` · `teaching-statement` · `sotl` | 6 |
| [`deck-studio`](deck-studio/WORKFLOW.md) | extension · 2 BUILD | `deck` · `theme` · `figure` · `handout` · `restyle` · `poster` | 4 |
| [`lab-forge`](lab-forge/WORKFLOW.md) | extension · 2 BUILD | `lab` · `dataset` · `starter-code` · `autograder` · `solution` · `variant` | 5 |
| [`media-scripter`](media-scripter/WORKFLOW.md) | extension · 2 BUILD | `script` · `storyboard` · `series` · `captions` · `audio` | 4 |
| [`course-publisher`](course-publisher/WORKFLOW.md) | extension · 4 DELIVER | `announcement` · `weekly-email` · `course-site` · `lms-package` · `faq` | 4 |
| [`ta-coordinator`](ta-coordinator/WORKFLOW.md) | extension · 4 DELIVER | `onboarding` · `calibration` · `allocation` · `meeting` · `consistency` | 4 |
| [`accreditation-mapper`](accreditation-mapper/WORKFLOW.md) | extension · 1 DESIGN | `map` · `evidence` · `gap` · `self-study` | 4 |
| [`bilingual-courseware`](bilingual-courseware/WORKFLOW.md) | extension · cross-cutting support | `glossary` · `translate` · `parallel` · `check` | 4 |
| [`cohort-analyst`](cohort-analyst/WORKFLOW.md) | extension · cross-cutting support | `instrument` · `cohort-profile` · `lesson-calibration` · `grouping` · `progress` | 4 |

Modes are defined in each `WORKFLOW.md` (Modes table) and cross-listed in `MODE_REGISTRY.md`; agent files
are `<module>/agents/<agent>.md`.

## 5. The lifecycle at a glance (`teaching-pipeline`)

```
Stage 0 CONTEXT  intake → initialize course_passport.yaml (cohort-analyst pre-term diagnostic optional)  🧑
Stage 1 DESIGN   course-designer (accreditation-mapper attaches)                  🧑
Gate 1.5 ALIGNMENT  A/B/C/D checks; BLOCK → back to Stage 1 (max 3 rounds)        ✓
Stage 2 BUILD    lesson-builder, just-in-time by default (deck-studio, media-scripter, lab-forge attach)  🧑
Stage 3 ASSESS   assessment-architect + integrity-check (lab-forge attaches)      🧑
Gate 3.5 QUALITY Q/T/U/I/W checks; BLOCK → back to Stage 2 or 3 (max 3 rounds)     ✓
Stage 4 DELIVER  weekly loop: next week's build · student-mentor on demand only ·
                 submission-auditor when work arrives · midcourse feedback at weeks 4–6 ·
                 course-publisher, ta-coordinator, cohort-analyst, bilingual-courseware as needed
Stage 5 REFLECT  teaching-reflector eval-analysis + triangulation                 🧑
Stage 6 IMPROVE  iteration_history entry + redesign brief → next term re-enters Stage 1 (new-term)
```

🧑 = professor checkpoint · ✓ = deterministic gate, then professor acknowledgment. Gates are non-skippable in
pipeline mode and never forced on standalone module use; extension modules are offered where they fit, never
required by a gate. The current stage is derived from the passport plus today's date and the stored
calendar — never from chat history (`teaching-pipeline/references/pipeline_state_machine.md`). Mid-entry is
first-class: validate what the professor already has into the passport, then enter at the earliest stage
whose entry invariants fail. Full flow, stage matrix and gate inventory: `docs/ARCHITECTURE.md`.

## 6. Course Passport, validators and tooling

State lives in `course_passport.yaml` (schema: `shared/course_passport_schema.md` and
`shared/course_passport.schema.json`). The deterministic layer is executable when Python 3 is available; run
each script from the *working directory* by absolute path (see §1):

| Script | Does |
|---|---|
| `scripts/check_passport.py <passport> [--json]` | JSON Schema plus cross-reference invariants P1–P10 and the P11 student-PII guard; run it first |
| `scripts/check_alignment_gate.py <passport> [--json]` | Gate 1.5 checks A1–D3, honoring dismissed findings; it assumes a structurally valid passport and does not report P-check breakage, so run `check_passport.py` before it |
| `scripts/check_quality_gate.py <passport> [--json]` | executable core of Gate 3.5 (Q1, Q2, Q4, T1, T2, T4, W1); judgment checks (Q3, T3, U1–U3, I1–I2) are reported `NOT_EVALUABLE` |
| `scripts/check_content_markers.py <passport> [--strict]` | unresolved `[NEEDS PROFESSOR INPUT]` / `[VERIFY]` markers; `--strict` blocks finalization |
| `scripts/build_dashboard.py <passport> [-o out.html]` | single-file HTML course dashboard (a build product of the passport) |
| `scripts/render_document.py <file.md> --to docx\|pdf` | Markdown → DOCX/PDF through Pandoc; degrades honestly, never fakes a render |
| `scripts/export_lms.py <questions.json> --to gift\|qti\|imscc` | GIFT (Moodle), QTI 2.1 (Canvas/Blackboard/Moodle), Common Cartridge |
| `scripts/check_registry_consistency.py`, `scripts/check_links.py` | maintenance lints for this skill's own registry and references |

The validators need `pyyaml` and `jsonschema` (`pip install pyyaml jsonschema`; `requirements-dev.txt` adds
`pytest` for the test suite). Where the prose schema and the JSON Schema differ, write what the JSON Schema
accepts — for example `iteration_history[].changes` is a list of strings, and an assessment `type` may also be
`lab` or `other`. Without Python, do the same checks by hand from the protocol tables and say
that the assurance is lower. Rendering skills detect installed toolchains honestly and never claim a build
that did not run.

## 7. Hand-offs between modules

`course-designer` → outcomes and schedule → `lesson-builder`; assessment plan → `assessment-architect`.
`assessment-architect` → briefs and rubrics as spec sources → `submission-auditor`; `lab-forge` autograder
output → `submission-auditor` deterministic checks. `submission-auditor` (anonymous counts only) and
`teaching-reflector` hand their evidence to `iteration_coach_agent`, the single writer of
`iteration_history`, which feeds `course-designer` `redesign`. `bilingual-courseware`'s glossary is
consumed by `course-publisher` and `media-scripter`;
`accreditation-mapper` builds its continuous-improvement narrative from `iteration_history`;
`cohort-analyst` writes aggregates only into `learner_profile`; `deck-studio` and `course-publisher` treat
markdown or the passport as source and rendered output as rebuildable. `teaching-reflector` `sotl` hands
off externally to the Academic Research Skills suite for the publication phase.

## 8. Where things are

| Need | Open |
|---|---|
| Every file, one line each | `INDEX.md` |
| Every mode and its command | `MODE_REGISTRY.md` |
| Flow, gates, passport data flow, dependency graph | `docs/ARCHITECTURE.md` |
| A worked STEM course / a humanities seminar with person-affecting outputs | `examples/showcase/`, `examples/showcase-seminar/` |
| First-session walkthrough | `QUICKSTART.md` |
| What changed versus upstream, and why | `MERGE_NOTES.md` |
| How this skill was built and verified (builder, verifier, edit spec, tests) | `tools/merge/`, `tests/` |
| Upstream project docs (kept) | `README.md`, `README.zh-CN.md`, `CHANGELOG.md`, `CONTRIBUTING.md`, `CLAUDE.md` |
| Archived upstream repository files | `upstream/` |

Provenance: merged from *Teaching Skills* v1.2.0 by Jiaxing Yu (MIT License, see `LICENSE`). Pedagogy claims
and citations are the upstream author's; the professor's discipline expertise overrules them.
