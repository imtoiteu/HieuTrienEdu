"""Seed the database with content and a realistic demo dataset.

Idempotent: safe to run repeatedly. Content is upserted by slug; demo accounts are created only
if their email is not already present.

The brief is explicit that the application must not open empty, so this does more than insert a
few rows — it simulates a term's worth of practice for the demo student so that mastery bars,
streaks, recommendations and the weak-skills list all have honest data behind them.
"""

from __future__ import annotations

import argparse
import datetime as dt
import random
import sys
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.content_io.loader import load_all
from app.core.config import settings
from app.core.db import SessionLocal, engine
from app.core.security import hash_password
from app.models import (
    Achievement,
    Base,
    BlogPost,
    ClassEnrollment,
    ClassGroup,
    ContactLead,
    Course,
    CourseEnrollment,
    DeliveryMode,
    EnrollmentStatus,
    LearningFormat,
    LiveSession,
    ParentProfile,
    ParentStudentLink,
    Question,
    ReviewStatus,
    ScheduleSlot,
    SessionStatus,
    Skill,
    StudentProfile,
    TeacherProfile,
    Testimonial,
    TutoringProduct,
    User,
    UserRole,
)
from app.services.practice import record_attempt, serve_question

DEMO_PASSWORD = "HietEdu2026!"


# --------------------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------------------


def _get_or_create_user(
    db: Session, email: str, *, full_name: str, role: UserRole, **extra
) -> tuple[User, bool]:
    user = db.scalar(select(User).where(func.lower(User.email) == email.lower()))
    if user is not None:
        return user, False
    user = User(
        email=email.lower(),
        password_hash=hash_password(DEMO_PASSWORD),
        full_name=full_name,
        role=role,
        is_verified=True,
        **extra,
    )
    db.add(user)
    db.flush()
    return user, True


def _upsert_by_slug(db: Session, model, slug: str, **fields):
    instance = db.scalar(select(model).where(model.slug == slug))
    if instance is None:
        instance = model(slug=slug, **fields)
        db.add(instance)
        db.flush()
        return instance
    for key, value in fields.items():
        setattr(instance, key, value)
    return instance


# --------------------------------------------------------------------------------------
# seed steps
# --------------------------------------------------------------------------------------


def seed_achievements(db: Session) -> int:
    definitions = [
        ("first-steps", "First Steps", "Answer your first question", "footprints", "bronze",
         {"type": "questions_attempted", "value": 1}, 10),
        ("getting-going", "Getting Going", "Answer 25 questions", "activity", "bronze",
         {"type": "questions_attempted", "value": 25}, 25),
        ("century", "Century", "Answer 100 questions", "target", "silver",
         {"type": "questions_attempted", "value": 100}, 60),
        ("sharp-shooter", "Sharp Shooter", "Get 50 questions correct", "crosshair", "silver",
         {"type": "questions_correct", "value": 50}, 50),
        ("first-mastery", "Skill Unlocked", "Master your first skill", "unlock", "bronze",
         {"type": "skills_mastered", "value": 1}, 30),
        ("five-skills", "Building Momentum", "Master 5 skills", "layers", "silver",
         {"type": "skills_mastered", "value": 5}, 75),
        ("twenty-skills", "Serious Progress", "Master 20 skills", "mountain", "gold",
         {"type": "skills_mastered", "value": 20}, 200),
        ("three-day-streak", "Three in a Row", "Practise three days running", "flame", "bronze",
         {"type": "streak_days", "value": 3}, 20),
        ("week-streak", "Week Warrior", "Practise seven days running", "flame", "silver",
         {"type": "streak_days", "value": 7}, 60),
        ("month-streak", "Unstoppable", "Practise thirty days running", "flame", "gold",
         {"type": "streak_days", "value": 30}, 300),
        ("level-five", "Level 5", "Reach level 5", "star", "silver",
         {"type": "level", "value": 5}, 50),
        ("level-ten", "Level 10", "Reach level 10", "star", "gold",
         {"type": "level", "value": 10}, 150),
    ]
    created = 0
    for slug, name, description, icon, tier, criteria, xp in definitions:
        existing = db.scalar(select(Achievement).where(Achievement.slug == slug))
        if existing is None:
            db.add(
                Achievement(
                    slug=slug, name=name, description=description, icon=icon, tier=tier,
                    criteria=criteria, xp_reward=xp,
                )
            )
            created += 1
    db.flush()
    return created


def seed_staff(db: Session) -> dict[str, object]:
    """The two founding teachers the platform is named after, plus supporting staff."""
    admin, _ = _get_or_create_user(
        db, "admin@hietrieneducation.vn", full_name="HieuTrienEducation Admin",
        role=UserRole.ADMIN,
    )

    teachers = [
        {
            "email": "hieu@hietrieneducation.vn",
            "full_name": "Thầy Hiếu",
            "headline": "Co-founder · Mathematics lead",
            "bio": (
                "Thầy Hiếu has taught middle-school mathematics for over a decade. He is known "
                "for breaking hard ideas into steps a student can actually hold in their head, "
                "and for refusing to let anyone move on from fractions until they truly have them."
            ),
            "subjects": ["mathematics"],
            "grades": [6, 7, 8, 9],
            "qualifications": ["MSc Mathematics Education", "National teaching certification"],
            "years_experience": 12,
            "languages": ["Vietnamese", "English"],
            "hourly_rate_vnd": 450000,
            "is_featured": True,
            "availability": [
                {"weekday": 1, "start": "18:00", "end": "21:00"},
                {"weekday": 3, "start": "18:00", "end": "21:00"},
                {"weekday": 5, "start": "09:00", "end": "12:00"},
            ],
        },
        {
            "email": "trien@hietrieneducation.vn",
            "full_name": "Cô Triền",
            "headline": "Co-founder · Physics lead",
            "bio": (
                "Cô Triền teaches physics as a practical, measurable subject rather than a list "
                "of formulas. Her lessons start from something students can see happening and "
                "work towards the equation that explains it."
            ),
            "subjects": ["physics"],
            "grades": [6, 7, 8, 9],
            "qualifications": ["MSc Physics", "Advanced pedagogy certification"],
            "years_experience": 11,
            "languages": ["Vietnamese", "English"],
            "hourly_rate_vnd": 450000,
            "is_featured": True,
            "availability": [
                {"weekday": 2, "start": "18:00", "end": "21:00"},
                {"weekday": 4, "start": "18:00", "end": "21:00"},
                {"weekday": 6, "start": "09:00", "end": "12:00"},
            ],
        },
        {
            "email": "mai@hietrieneducation.vn",
            "full_name": "Cô Mai",
            "headline": "Mathematics teacher · Grades 6-7",
            "bio": (
                "Cô Mai specialises in the transition into middle school, working with students "
                "who arrive convinced they are 'not a maths person'."
            ),
            "subjects": ["mathematics"],
            "grades": [6, 7],
            "qualifications": ["BSc Mathematics", "Primary-secondary transition specialist"],
            "years_experience": 6,
            "languages": ["Vietnamese"],
            "hourly_rate_vnd": 320000,
            "availability": [{"weekday": 1, "start": "17:00", "end": "20:00"}],
        },
        {
            "email": "duc@hietrieneducation.vn",
            "full_name": "Thầy Đức",
            "headline": "Physics teacher · Exam preparation",
            "bio": (
                "Thầy Đức focuses on grade 9 exam preparation, with an emphasis on the "
                "problem-solving structure examiners actually reward."
            ),
            "subjects": ["physics", "mathematics"],
            "grades": [8, 9],
            "qualifications": ["BSc Physics", "Examination board assessor"],
            "years_experience": 8,
            "languages": ["Vietnamese", "English"],
            "hourly_rate_vnd": 380000,
            "availability": [{"weekday": 4, "start": "18:00", "end": "21:00"}],
        },
    ]

    profiles: dict[str, TeacherProfile] = {}
    for data in teachers:
        email = data.pop("email")
        full_name = data.pop("full_name")
        user, _ = _get_or_create_user(db, email, full_name=full_name, role=UserRole.TEACHER)
        profile = db.scalar(select(TeacherProfile).where(TeacherProfile.user_id == user.id))
        if profile is None:
            profile = TeacherProfile(user_id=user.id)
            db.add(profile)
        for key, value in data.items():
            setattr(profile, key, value)
        profile.rating = round(random.Random(user.id).uniform(4.6, 5.0), 1)
        profile.rating_count = random.Random(user.id + 7).randint(18, 96)
        db.flush()
        profiles[email] = profile

    return {"admin": admin, "teachers": profiles}


def seed_products(db: Session) -> None:
    products = [
        {
            "slug": "one-to-one-mathematics",
            "name": "1-to-1 Mathematics Tutoring",
            "tagline": "A teacher entirely focused on your child",
            "description": (
                "Weekly private lessons matched to your child's exact gaps, identified by our "
                "mastery model rather than guesswork. Online or at the centre."
            ),
            "format": LearningFormat.ONE_TO_ONE,
            "delivery_mode": DeliveryMode.HYBRID,
            "subject_slug": "mathematics",
            "price_vnd": 450000, "price_unit": "session", "sessions_included": 1,
            "session_minutes": 90, "capacity": 1, "is_featured": True, "position": 1,
            "features": [
                "Individually paced", "Choose your teacher", "Flexible scheduling",
                "Weekly progress report", "Online or at the centre",
            ],
        },
        {
            "slug": "one-to-one-physics",
            "name": "1-to-1 Physics Tutoring",
            "tagline": "Physics explained until it clicks",
            "description": (
                "Private physics lessons that start from what your child can already picture "
                "and build towards confident problem solving."
            ),
            "format": LearningFormat.ONE_TO_ONE,
            "delivery_mode": DeliveryMode.HYBRID,
            "subject_slug": "physics",
            "price_vnd": 450000, "price_unit": "session", "sessions_included": 1,
            "session_minutes": 90, "capacity": 1, "position": 2,
            "features": [
                "Individually paced", "Practical demonstrations", "Exam technique",
                "Weekly progress report",
            ],
        },
        {
            "slug": "small-group-mathematics",
            "name": "Small Group Mathematics",
            "tagline": "Six students, one teacher, real discussion",
            "description": (
                "Groups are capped at six so every student is heard. Students at a similar "
                "level work through a term-long programme together."
            ),
            "format": LearningFormat.GROUP,
            "delivery_mode": DeliveryMode.OFFLINE,
            "subject_slug": "mathematics",
            "price_vnd": 2800000, "price_unit": "course", "sessions_included": 16,
            "session_minutes": 90, "capacity": 6, "is_featured": True, "position": 3,
            "features": [
                "Maximum 6 students", "16 sessions per term", "Termly written report",
                "Full platform access included",
            ],
        },
        {
            "slug": "small-group-physics",
            "name": "Small Group Physics",
            "tagline": "Learn together, with equipment you can actually use",
            "description": (
                "Group physics with practical work — students measure, record and explain "
                "rather than only reading about experiments."
            ),
            "format": LearningFormat.GROUP,
            "delivery_mode": DeliveryMode.OFFLINE,
            "subject_slug": "physics",
            "price_vnd": 2800000, "price_unit": "course", "sessions_included": 16,
            "session_minutes": 90, "capacity": 6, "position": 4,
            "features": [
                "Maximum 6 students", "Hands-on practical work", "16 sessions per term",
                "Full platform access included",
            ],
        },
        {
            "slug": "online-live-classes",
            "name": "Online Live Classes",
            "tagline": "The same teaching, from anywhere in Vietnam",
            "description": (
                "Scheduled live classes delivered online, with recordings available afterwards "
                "so a missed session is never a lost session."
            ),
            "format": LearningFormat.ONLINE_LIVE,
            "delivery_mode": DeliveryMode.ONLINE,
            "price_vnd": 2200000, "price_unit": "course", "sessions_included": 16,
            "session_minutes": 75, "capacity": 12, "is_featured": True, "position": 5,
            "features": [
                "Live, not pre-recorded", "Every session recorded", "Maximum 12 students",
                "Join from anywhere",
            ],
        },
        {
            "slug": "recorded-course",
            "name": "Recorded Course + Practice",
            "tagline": "Learn at your own pace, practise without limit",
            "description": (
                "Full access to video lessons and the entire adaptive practice system. The most "
                "affordable way to use the platform, with no fixed schedule."
            ),
            "format": LearningFormat.RECORDED,
            "delivery_mode": DeliveryMode.ONLINE,
            "price_vnd": 690000, "price_unit": "month", "sessions_included": 0,
            "session_minutes": 0, "capacity": 1000, "position": 6,
            "features": [
                "Unlimited adaptive practice", "All video lessons", "Progress tracking",
                "Cancel any time",
            ],
        },
        {
            "slug": "hybrid-programme",
            "name": "Hybrid Programme",
            "tagline": "Live teaching plus everything else",
            "description": (
                "Our most complete option: weekly live classes, full platform access, and a "
                "monthly 1-to-1 review session with your teacher."
            ),
            "format": LearningFormat.HYBRID,
            "delivery_mode": DeliveryMode.HYBRID,
            "price_vnd": 3900000, "price_unit": "course", "sessions_included": 20,
            "session_minutes": 90, "capacity": 8, "is_featured": True, "position": 7,
            "features": [
                "Weekly live class", "Monthly 1-to-1 review", "Unlimited practice",
                "Priority teacher support", "Detailed monthly report",
            ],
        },
    ]
    for data in products:
        _upsert_by_slug(db, TutoringProduct, data.pop("slug"), **data)
    db.flush()


def seed_classes(db: Session, teachers: dict[str, TeacherProfile]) -> list[ClassGroup]:
    hieu = teachers.get("hieu@hietrieneducation.vn")
    trien = teachers.get("trien@hietrieneducation.vn")
    duc = teachers.get("duc@hietrieneducation.vn")

    today = dt.date.today()
    start = today - dt.timedelta(days=today.weekday()) + dt.timedelta(days=7)

    definitions = [
        ("math-7-evening-group", "Mathematics Grade 7 — Tuesday Evening Group", "math-7",
         "small-group-mathematics", hieu, LearningFormat.GROUP, DeliveryMode.OFFLINE, 6,
         [(1, "18:00", "19:30")], "HieuTrienEducation Centre, Room 1"),
        ("math-8-online-live", "Mathematics Grade 8 — Online Live", "math-8",
         "online-live-classes", hieu, LearningFormat.ONLINE_LIVE, DeliveryMode.ONLINE, 12,
         [(3, "19:00", "20:15")], None),
        ("physics-8-evening-group", "Physics Grade 8 — Wednesday Evening Group", "physics-8",
         "small-group-physics", trien, LearningFormat.GROUP, DeliveryMode.OFFLINE, 6,
         [(2, "18:00", "19:30")], "HieuTrienEducation Centre, Lab"),
        ("physics-9-exam-prep", "Physics Grade 9 — Exam Preparation", "physics-9",
         "hybrid-programme", duc, LearningFormat.HYBRID, DeliveryMode.HYBRID, 8,
         [(4, "18:30", "20:00"), (6, "09:00", "10:30")], "HieuTrienEducation Centre, Room 2"),
        ("math-6-foundations", "Mathematics Grade 6 — Foundations", "math-6",
         "small-group-mathematics", teachers.get("mai@hietrieneducation.vn"),
         LearningFormat.GROUP, DeliveryMode.OFFLINE, 6,
         [(0, "17:00", "18:30")], "HieuTrienEducation Centre, Room 3"),
    ]

    groups = []
    for slug, name, course_slug, product_slug, teacher, fmt, mode, cap, slots, location in \
            definitions:
        course = db.scalar(select(Course).where(Course.slug == course_slug))
        product = db.scalar(select(TutoringProduct).where(TutoringProduct.slug == product_slug))
        group = _upsert_by_slug(
            db, ClassGroup, slug,
            name=name,
            course_id=course.id if course else None,
            product_id=product.id if product else None,
            teacher_id=teacher.id if teacher else None,
            format=fmt, delivery_mode=mode, capacity=cap,
            start_date=start, end_date=start + dt.timedelta(weeks=16),
            location=location, is_open_for_enrollment=True,
        )
        if not group.schedule_slots:
            for weekday, start_time, end_time in slots:
                db.add(
                    ScheduleSlot(
                        class_group_id=group.id, weekday=weekday,
                        start_time=dt.time.fromisoformat(start_time),
                        end_time=dt.time.fromisoformat(end_time),
                    )
                )
        groups.append(group)
    db.flush()

    # The schedule_slots collections were loaded (empty) before the slots above were added, so
    # they are stale. Without expiring them the session loop below sees no slots and silently
    # creates nothing.
    db.expire_all()

    # Upcoming live sessions for the next four weeks of each class.
    for group in groups:
        if db.scalar(
            select(func.count()).select_from(LiveSession)
            .where(LiveSession.class_group_id == group.id)
        ):
            continue
        for week in range(4):
            for slot in group.schedule_slots:
                day = start + dt.timedelta(days=slot.weekday, weeks=week)
                starts = dt.datetime.combine(day, slot.start_time, tzinfo=dt.UTC)
                ends = dt.datetime.combine(day, slot.end_time, tzinfo=dt.UTC)
                db.add(
                    LiveSession(
                        class_group_id=group.id,
                        title=f"{group.name} — Session {week + 1}",
                        topic_summary="Weekly session. The teacher will share the plan in advance.",
                        starts_at=starts, ends_at=ends,
                        provider=settings.live_class_provider,
                        status=SessionStatus.SCHEDULED,
                        join_url=(
                            "https://meet.hietrieneducation.vn/"
                            f"{group.slug}-{week + 1}"
                            if group.delivery_mode != DeliveryMode.OFFLINE else None
                        ),
                    )
                )
    db.flush()
    return groups


def seed_site_content(db: Session) -> None:
    testimonials = [
        ("Nguyễn Thị Lan", "Parent of a Grade 7 student", 5, "mathematics", 7, True,
         "My daughter used to hide her maths homework from me. Two terms in, she explains it to "
         "her younger brother. The weekly report showed us exactly which skills were weak, and "
         "the practice actually targeted them instead of giving her more of what "
         "she already knew."),
        ("Trần Minh Quân", "Grade 9 student", 5, "physics", 9, True,
         "The practice never runs out, which sounds obvious but no other site I tried did that. "
         "Every question is different so I couldn't memorise answers — I had to "
         "actually learn it."),
        ("Phạm Thu Hà", "Parent of a Grade 8 student", 5, "physics", 8, True,
         "Cô Triền found the exact misunderstanding behind months of confusion in a single "
         "session. My son went from 5.5 to 8.0 in one term."),
        ("Lê Hoàng Nam", "Parent of two students", 5, "mathematics", 6, False,
         "Both my children study here, in different grades and with different teachers. What I "
         "value most is that I can see real progress data rather than being told "
         "'he's doing fine'."),
        ("Vũ Thị Mai Anh", "Grade 8 student", 4, "mathematics", 8, False,
         "The learning path makes it obvious what to do next. I used to waste time deciding what "
         "to revise; now I just open it and start."),
        ("Đỗ Văn Thành", "Parent of a Grade 9 student", 5, "physics", 9, False,
         "The online classes meant we could keep the same teacher after we moved to Đà Nẵng. "
         "The recordings were genuinely useful when my daughter was ill for a week."),
    ]
    for index, (name, role, rating, subject, grade, featured, quote) in enumerate(testimonials):
        existing = db.scalar(
            select(Testimonial).where(
                Testimonial.author_name == name, Testimonial.quote == quote
            )
        )
        if existing is None:
            db.add(
                Testimonial(
                    author_name=name, author_role=role, quote=quote, rating=rating,
                    subject_slug=subject, grade=grade, is_featured=featured,
                    is_published=True, position=index,
                )
            )

    posts = [
        {
            "slug": "why-fractions-are-hard",
            "title": "Why Fractions Are Genuinely Hard (And What Helps)",
            "excerpt": (
                "Fractions are the first place many students decide they are 'bad at maths'. "
                "The reason is not effort — it is that fractions break several rules students "
                "have spent five years learning."
            ),
            "category": "teaching",
            "tags": ["fractions", "grade-6", "misconceptions"],
            "reading_minutes": 6,
            "body_markdown": (
                "## The rules that stop working\n\n"
                "By the end of primary school, a student has internalised some reliable rules:\n\n"
                "- Multiplying makes numbers bigger.\n"
                "- Dividing makes numbers smaller.\n"
                "- A number is a single symbol.\n\n"
                "Every one of these breaks with fractions. Multiplying by 1/2 makes things "
                "*smaller*. Dividing by 1/2 makes things *bigger*. And a fraction is two numbers "
                "that have to be read as one.\n\n"
                "## What actually helps\n\n"
                "**Return to the meaning.** Before any procedure, a student should be able to say "
                "what 3/4 *is*: three pieces, each of which is one quarter of a whole.\n\n"
                "**Estimate before calculating.** If a student can see that 1/2 + 1/3 must be a "
                "bit more than 1/2, they will never accept 2/5 as an answer.\n\n"
                "**Practise until it is automatic.** Understanding is necessary but not "
                "sufficient. Fluency frees up the working memory that later algebra will need.\n\n"
                "## How we teach it\n\n"
                "Our platform treats each fraction sub-skill separately — equivalence, comparison, "
                "common denominators, then the four operations — and will not recommend adding "
                "fractions until equivalence is genuinely secure. That gating is the whole point."
            ),
        },
        {
            "slug": "what-mastery-actually-means",
            "title": "What 'Mastery' Actually Means on This Platform",
            "excerpt": (
                "When we say a student has mastered a skill, that is a specific claim backed by "
                "a specific model. Here is exactly what it means."
            ),
            "category": "platform",
            "tags": ["mastery", "adaptive-learning", "transparency"],
            "reading_minutes": 5,
            "body_markdown": (
                "## Not a percentage\n\n"
                "Most platforms show 'you got 8 out of 10'. That number cannot tell the "
                "difference between a student who understood eight questions and one who guessed "
                "four of them on multiple choice.\n\n"
                "## What we use instead\n\n"
                "We use **Bayesian Knowledge Tracing**. Rather than counting right answers, it "
                "maintains a probability that the student genuinely knows the skill, and updates "
                "that probability after each answer using four parameters:\n\n"
                "- how likely they were to know it already,\n"
                "- how likely they are to learn it from this attempt,\n"
                "- how likely a knowing student is to slip,\n"
                "- how likely a non-knowing student is to guess correctly.\n\n"
                "We adjust the guess probability by question type, because a four-option multiple "
                "choice is guessable one time in four and a numeric answer essentially "
                "never is.\n\n"
                "## When we say mastered\n\n"
                "A skill is marked mastered when that probability passes 95%, which typically "
                "takes around five correct answers from a cold start — more if hints were used, "
                "because a hinted answer is weaker evidence.\n\n"
                "Mastery also **decays**. A skill untouched for months drifts back towards "
                "'needs review', because that is what actually happens to human memory."
            ),
        },
        {
            "slug": "helping-without-doing-it-for-them",
            "title": "Helping With Homework Without Doing It For Them",
            "excerpt": (
                "A short guide for parents who want to help but are not sure how — especially "
                "when the maths has changed since they were at school."
            ),
            "category": "parents",
            "tags": ["parents", "homework", "support"],
            "reading_minutes": 4,
            "body_markdown": (
                "## Ask, do not tell\n\n"
                "The single most useful thing you can say is **'show me what you have tried'**. "
                "It costs you nothing, and it usually reveals the misunderstanding within a "
                "minute.\n\n"
                "Other questions that work well:\n\n"
                "- What is the question actually asking for?\n"
                "- Have you seen anything like this before?\n"
                "- Roughly what size should the answer be?\n\n"
                "## You do not need to know the maths\n\n"
                "You genuinely do not have to remember how to factorise. Asking a student to "
                "explain their reasoning to you is valuable *precisely because* you do not know "
                "— they cannot skip steps, and explaining is where understanding gets tested.\n\n"
                "## Protect the struggle\n\n"
                "The temptation to step in and show them is strong, and it is worth resisting. "
                "Productive struggle is where learning happens. Step in when a student is stuck "
                "and frustrated, not when they are stuck and thinking."
            ),
        },
    ]
    for post in posts:
        existing = db.scalar(select(BlogPost).where(BlogPost.slug == post["slug"]))
        if existing is None:
            db.add(
                BlogPost(
                    **post,
                    author_name="HieuTrienEducation",
                    status=ReviewStatus.PUBLISHED,
                    published_at=dt.datetime.now(dt.UTC) - dt.timedelta(days=len(post["slug"])),
                )
            )

    if db.scalar(select(func.count()).select_from(ContactLead)) == 0:
        db.add(
            ContactLead(
                name="Hoàng Thị Ngọc", email="ngoc.demo@example.com", phone="0901234567",
                subject_slug="mathematics", grade=7, interest="free_assessment",
                message="I would like to book a free assessment for my daughter.",
                source_page="/en/contact",
            )
        )
    db.flush()


def seed_demo_family(db: Session, groups: list[ClassGroup]) -> StudentProfile | None:
    """Create the demo student, a sibling, and a parent linked to both."""
    student_user, created = _get_or_create_user(
        db, "student@hietrieneducation.vn", full_name="An Nguyễn", role=UserRole.STUDENT
    )
    student = db.scalar(select(StudentProfile).where(StudentProfile.user_id == student_user.id))
    if student is None:
        student = StudentProfile(
            user_id=student_user.id, grade=8, school="Nguyễn Du Secondary School",
            learning_goals=["Improve algebra", "Get ready for the grade 9 physics exam"],
        )
        db.add(student)
        db.flush()

    sibling_user, _ = _get_or_create_user(
        db, "student2@hietrieneducation.vn", full_name="Bảo Nguyễn", role=UserRole.STUDENT
    )
    sibling = db.scalar(select(StudentProfile).where(StudentProfile.user_id == sibling_user.id))
    if sibling is None:
        sibling = StudentProfile(
            user_id=sibling_user.id, grade=6, school="Nguyễn Du Secondary School"
        )
        db.add(sibling)
        db.flush()

    parent_user, _ = _get_or_create_user(
        db, "parent@hietrieneducation.vn", full_name="Nguyễn Thị Lan", role=UserRole.PARENT
    )
    parent = db.scalar(select(ParentProfile).where(ParentProfile.user_id == parent_user.id))
    if parent is None:
        parent = ParentProfile(user_id=parent_user.id)
        db.add(parent)
        db.flush()

    for child in (student, sibling):
        link = db.scalar(
            select(ParentStudentLink).where(
                ParentStudentLink.parent_id == parent.id,
                ParentStudentLink.student_id == child.id,
            )
        )
        if link is None:
            db.add(ParentStudentLink(parent_id=parent.id, student_id=child.id,
                                     relationship_label="mother"))

    # Enrol the demo student in self-study courses and two live classes.
    for course_slug in ("math-8", "physics-8"):
        course = db.scalar(select(Course).where(Course.slug == course_slug))
        if course is None:
            continue
        if db.scalar(
            select(CourseEnrollment).where(
                CourseEnrollment.student_id == student.id,
                CourseEnrollment.course_id == course.id,
            )
        ) is None:
            db.add(
                CourseEnrollment(
                    student_id=student.id, course_id=course.id,
                    last_activity_at=dt.datetime.now(dt.UTC),
                )
            )

    for group in groups:
        if group.slug not in {"math-8-online-live", "physics-8-evening-group"}:
            continue
        if db.scalar(
            select(ClassEnrollment).where(
                ClassEnrollment.class_group_id == group.id,
                ClassEnrollment.student_id == student.id,
            )
        ) is None:
            db.add(
                ClassEnrollment(
                    class_group_id=group.id, student_id=student.id,
                    status=EnrollmentStatus.ACTIVE, enrolled_at=dt.datetime.now(dt.UTC),
                )
            )

    db.flush()
    return student


def simulate_practice(db: Session, student: StudentProfile, *, attempts: int = 220) -> int:
    """Give the demo student a believable practice history.

    Answers are simulated with a per-skill 'true ability' so the resulting mastery profile has
    genuine strengths and weaknesses — a uniformly random student would produce a flat, useless
    dashboard.
    """
    if db.scalar(
        select(func.count()).select_from(type(student).attempts.property.mapper.class_)
        .where(type(student).attempts.property.mapper.class_.student_id == student.id)
    ):
        return 0  # already simulated

    rng = random.Random(20260812)

    skills = list(
        db.scalars(
            select(Skill)
            .join(Question, Question.skill_id == Skill.id)
            .where(Question.grade.in_([6, 7, 8]), Question.status == ReviewStatus.PUBLISHED)
            .distinct()
        ).unique()
    )
    if not skills:
        return 0

    # Fewer skills with more attempts each: a student who spreads 200 attempts over 60 skills
    # masters nothing, which makes for a dashboard that cannot demonstrate the mastery flow.
    chosen = rng.sample(skills, min(18, len(skills)))
    ability = {skill.id: rng.uniform(0.35, 0.97) for skill in chosen}

    recorded = 0
    for _ in range(attempts):
        skill = rng.choice(chosen)
        try:
            served = serve_question(db, student, skill)
        except LookupError:
            continue

        correct = rng.random() < ability[skill.id]
        answer = _synthesise_answer(served.variant, correct, rng)
        if answer is None:
            continue

        try:
            record_attempt(
                db, student, served.variant, answer,
                hints_used=1 if (not correct and rng.random() < 0.3) else 0,
                time_spent_seconds=rng.randint(20, 180),
            )
            recorded += 1
        except Exception:  # a malformed synthetic answer must not abort the whole seed
            db.rollback()
            continue

    # Backdate the XP ledger so the activity heatmap and streak look lived-in rather than
    # all landing on the day the seed happened to run.
    from app.models import XPEvent

    events = list(db.scalars(select(XPEvent).where(XPEvent.student_id == student.id)))
    today = dt.datetime.now(dt.UTC).date()
    for index, event in enumerate(events):
        event.occurred_on = today - dt.timedelta(days=(len(events) - index) // 6)

    student.streak_days = 6
    student.longest_streak_days = 11
    student.last_activity_date = today
    db.flush()
    return recorded


def _synthesise_answer(variant, correct: bool, rng: random.Random) -> dict | None:
    """Build a plausible right or wrong submission for a generated variant."""
    answer = variant.answer or {}
    rendered = variant.rendered or {}
    qtype = rendered.get("question_type")

    if qtype == "multiple_choice":
        choices = [c["id"] for c in rendered.get("choices", [])]
        if not choices:
            return None
        if correct:
            return {"choice_id": answer.get("choice_id")}
        wrong = [c for c in choices if c != answer.get("choice_id")]
        return {"choice_id": rng.choice(wrong)} if wrong else None

    if qtype == "multiple_select":
        ids = answer.get("choice_ids", [])
        if correct:
            return {"choice_ids": ids}
        return {"choice_ids": ids[:-1] if len(ids) > 1 else []}

    if qtype == "numeric":
        value = answer.get("value", 0)
        if correct:
            return {"value": value}
        return {"value": value + rng.choice([1, -1, 10]) * max(1, abs(value) * 0.1)}

    if qtype == "true_false":
        value = answer.get("value")
        return {"value": value if correct else (not value)}

    if qtype == "expression":
        return {"value": answer.get("expression") if correct else "x + 1"}

    if qtype == "short_answer":
        accepted = answer.get("accepted", [])
        if not accepted:
            return None
        return {"value": accepted[0] if correct else "not the answer"}

    if qtype == "fill_blank":
        blanks = answer.get("blanks", [])
        if not blanks:
            return None
        return {
            "blanks": {
                b["id"]: (b["value"] if correct else "0") for b in blanks
            }
        }

    if qtype == "matching":
        mapping = dict(answer.get("mapping", {}))
        if not mapping:
            return None
        if not correct and len(mapping) > 1:
            keys = list(mapping)
            mapping[keys[0]] = mapping[keys[1]]
        return {"mapping": mapping}

    if qtype == "ordering":
        order = list(answer.get("order", []))
        if not order:
            return None
        if not correct and len(order) > 1:
            order[0], order[1] = order[1], order[0]
        return {"order": order}

    return None


# --------------------------------------------------------------------------------------
# entrypoint
# --------------------------------------------------------------------------------------


def run(*, reset: bool = False, simulate: bool = True) -> int:
    if reset:
        print("Dropping all tables ...")
        Base.metadata.drop_all(engine)

    Base.metadata.create_all(engine)

    db = SessionLocal()
    try:
        print(f"Loading content from {settings.content_dir} ...")
        report = load_all(db, Path(settings.content_dir))
        print(f"  {report.summary()}")
        for error in report.errors:
            print(f"  CONTENT ERROR: {error}", file=sys.stderr)

        print("Seeding achievements ...")
        print(f"  {seed_achievements(db)} new")

        print("Seeding staff ...")
        staff = seed_staff(db)

        print("Seeding tutoring products ...")
        seed_products(db)

        print("Seeding classes and live sessions ...")
        groups = seed_classes(db, staff["teachers"])  # type: ignore[arg-type]

        print("Seeding site content ...")
        seed_site_content(db)

        print("Seeding demo family ...")
        student = seed_demo_family(db, groups)
        db.commit()

        if simulate and student is not None:
            print("Simulating practice history for the demo student ...")
            count = simulate_practice(db, student)
            db.commit()
            print(f"  {count} attempts recorded")

        print("\nSeed complete. Demo accounts (password: " + DEMO_PASSWORD + "):")
        for email, role in [
            ("student@hietrieneducation.vn", "student"),
            ("parent@hietrieneducation.vn", "parent"),
            ("hieu@hietrieneducation.vn", "teacher"),
            ("admin@hietrieneducation.vn", "admin"),
        ]:
            print(f"  {role:8} {email}")
        return 0 if not report.errors else 1
    finally:
        db.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed the HieuTrienEducation database")
    parser.add_argument("--reset", action="store_true", help="drop all tables first")
    parser.add_argument("--no-simulate", action="store_true",
                        help="skip simulating the demo student's practice history")
    args = parser.parse_args()
    return run(reset=args.reset, simulate=not args.no_simulate)


if __name__ == "__main__":
    raise SystemExit(main())
