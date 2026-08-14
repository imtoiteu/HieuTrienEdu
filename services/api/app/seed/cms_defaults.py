"""Initial CMS content: categories, page sections, settings, FAQs.

Seeding real copy rather than empty rows is a deliberate choice. An administrator opening the CMS
for the first time should see the words that are currently on the website and be able to change
them — not a blank form and a guess about what each key controls. Everything here is upserted by
its natural key, so re-running the seed never clobbers an edit an administrator has made.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    Announcement,
    CategoryKind,
    ContentCategory,
    FaqItem,
    ReviewStatus,
    SiteSection,
    SiteSetting,
)

# (slug, English name, Vietnamese name, kind, parent slug or None)
#
# The slug is given explicitly rather than derived from the name. It was originally derived from
# the Vietnamese name, which is what every existing row and every migration keys off; deriving it
# from the English name now would create a second copy of every category rather than translating
# the ones that exist.
#
# Grades run to 12 because the courses do — the list stopped at 9 while the curriculum grew, so
# the two halves of the site disagreed about which grades the centre teaches.
CATEGORIES: list[tuple[str, str, str, CategoryKind, str | None]] = [
    ("toan", "Mathematics", "Toán", CategoryKind.SUBJECT, None),
    ("vat-ly", "Physics", "Vật lý", CategoryKind.SUBJECT, None),
    ("lop-6", "Grade 6", "Lớp 6", CategoryKind.GRADE, None),
    ("lop-7", "Grade 7", "Lớp 7", CategoryKind.GRADE, None),
    ("lop-8", "Grade 8", "Lớp 8", CategoryKind.GRADE, None),
    ("lop-9", "Grade 9", "Lớp 9", CategoryKind.GRADE, None),
    ("lop-10", "Grade 10", "Lớp 10", CategoryKind.GRADE, None),
    ("lop-11", "Grade 11", "Lớp 11", CategoryKind.GRADE, None),
    ("lop-12", "Grade 12", "Lớp 12", CategoryKind.GRADE, None),
    ("luyen-thi", "Exam preparation", "Luyện thi", CategoryKind.PROGRAM, None),
    ("luyen-thi-vao-10", "Grade 10 entrance", "Luyện thi vào 10", CategoryKind.PROGRAM,
     "luyen-thi"),
    ("hoc-them", "Supplementary classes", "Học thêm", CategoryKind.PROGRAM, None),
    ("on-tap", "Revision", "Ôn tập", CategoryKind.PROGRAM, None),
    ("hoc-1-1", "One-to-one", "Học 1-1", CategoryKind.PROGRAM, None),
    ("hoc-nhom", "Group classes", "Học nhóm", CategoryKind.PROGRAM, None),
]

# (key, group, label, value, value_type)
SETTINGS: list[tuple[str, str, str, dict, str]] = [
    ("contact.phone", "contact", "Phone number",
     {"text": "097 5453126"}, "text"),
    ("contact.email", "contact", "Email address",
     {"text": "hello@hietrieneducation.vn"}, "text"),
    ("contact.address", "contact", "Centre address",
     {"text": "6A Thái Phiên, TP Vinh, Nghệ An"}, "text"),
    ("contact.hours", "contact", "Opening hours",
     {"text": "Monday–Saturday, 08:00–20:30"}, "text"),
    ("contact.map_url", "contact", "Google Maps link", {"text": ""}, "url"),
    ("social.facebook", "social", "Facebook page", {"text": ""}, "url"),
    ("social.youtube", "social", "YouTube channel", {"text": ""}, "url"),
    ("social.zalo", "social", "Zalo", {"text": ""}, "url"),
    ("social.tiktok", "social", "TikTok", {"text": ""}, "url"),
    ("footer.tagline", "footer", "Footer tagline",
     {"text": "Mathematics and Physics, taught until it makes sense."}, "text"),
    ("footer.copyright", "footer", "Copyright line",
     {"text": "© HieuTrienEducation. All rights reserved."}, "text"),
    ("policy.privacy", "policy", "Privacy policy",
     {"markdown": "We collect only what we need to teach your child well. "
                  "Edit this policy from Admin → Website → Settings."}, "markdown"),
    ("policy.terms", "policy", "Terms of service",
     {"markdown": "Edit these terms from Admin → Website → Settings."}, "markdown"),
    ("policy.refund", "policy", "Refund policy",
     {"markdown": "Edit the refund policy from Admin → Website → Settings."}, "markdown"),
]

# (page, key, label, kind, content) — English, plus the Vietnamese variants in SECTIONS_VI.
SECTIONS: list[tuple[str, str, str, str, dict]] = [
    (
        "home", "hero", "Homepage hero", "hero",
        {
            "eyebrow": "Grades 6–12 · Mathematics & Physics",
            "title": "Every student can be good at maths.",
            "title_accent": "Ours prove it.",
            "subtitle": (
                "A learning platform that finds the exact gap holding your child back, then "
                "closes it with practice built for that gap — backed by teachers who see the "
                "same data you do."
            ),
            "cta_primary": "Start practising free",
            "cta_primary_href": "/register",
            "cta_secondary": "Book a free assessment",
            "cta_secondary_href": "/contact",
            "trust": "No card needed · Free forever plan · Cancel any time",
        },
    ),
    (
        "home", "mission", "Mission statement", "rich_text",
        {
            "title": "Why we are different",
            "body": (
                "Most platforms give more questions. We find the right ones. Practice only helps "
                "when it targets what a student cannot yet do."
            ),
        },
    ),
    (
        "home", "cta", "Closing call to action", "cta",
        {
            "title": "Book a free assessment",
            "body": (
                "Thirty minutes with a teacher, a clear picture of where your child stands, and "
                "no obligation."
            ),
            "button_label": "Book now",
            "button_href": "/contact",
        },
    ),
    (
        "about", "intro", "About the centre", "rich_text",
        {
            "title": "About HieuTrienEducation",
            "body": (
                "We are a Hanoi tutoring centre teaching Mathematics and Physics to students in "
                "grades 6 to 12, in person and online. Edit this text from Admin → Website."
            ),
        },
    ),
    (
        "about", "mission", "Mission", "rich_text",
        {
            "title": "Our mission",
            "body": (
                "To make sure no student is quietly left behind because nobody noticed which "
                "step they missed."
            ),
        },
    ),
    (
        "contact", "intro", "Contact page introduction", "rich_text",
        {
            "title": "Talk to us",
            "body": (
                "Tell us about your child and we will call you back within one working day."
            ),
        },
    ),
]

# Vietnamese is the centre's primary language, so the same sections are seeded again under the
# `vi` locale. The public endpoint prefers the requested locale and falls back to English, so a
# section only translated later still renders rather than leaving a hole in the page.
SECTIONS_VI: list[tuple[str, str, str, str, dict]] = [
    (
        "home", "hero", "Hero trang chủ", "hero",
        {
            "eyebrow": "Lớp 6–12 · Toán & Vật lý",
            "title": "Học sinh nào cũng có thể giỏi Toán.",
            "title_accent": "Học sinh của chúng tôi chứng minh điều đó.",
            "subtitle": (
                "Nền tảng học tập tìm đúng lỗ hổng đang cản trở con bạn, rồi lấp đầy bằng bài "
                "luyện thiết kế riêng cho lỗ hổng đó — cùng đội ngũ giáo viên nhìn thấy đúng dữ "
                "liệu mà bạn nhìn thấy."
            ),
            "cta_primary": "Học thử miễn phí",
            "cta_primary_href": "/register",
            "cta_secondary": "Đăng ký đánh giá miễn phí",
            "cta_secondary_href": "/contact",
            "trust": "Không cần thẻ · Gói miễn phí trọn đời · Huỷ bất cứ lúc nào",
        },
    ),
    (
        "home", "mission", "Tuyên ngôn", "rich_text",
        {
            "title": "Điều làm chúng tôi khác biệt",
            "body": (
                "Phần lớn nền tảng chỉ cho thêm bài tập. Chúng tôi tìm đúng bài cần làm. Luyện "
                "tập chỉ hiệu quả khi nhắm vào điều học sinh chưa làm được."
            ),
        },
    ),
    (
        "home", "cta", "Kêu gọi hành động cuối trang", "cta",
        {
            "title": "Đăng ký buổi đánh giá miễn phí",
            "body": (
                "Ba mươi phút cùng giáo viên, một bức tranh rõ ràng về trình độ của con bạn, "
                "hoàn toàn không ràng buộc."
            ),
            "button_label": "Đăng ký ngay",
            "button_href": "/contact",
        },
    ),
    (
        "about", "intro", "Về trung tâm", "rich_text",
        {
            "title": "Về HieuTrienEducation",
            "body": (
                "Chúng tôi là trung tâm gia sư tại TP Vinh, Nghệ An, dạy Toán và Vật lý cho "
                "học sinh lớp 6 đến lớp 12, trực tiếp và trực tuyến. Bạn có thể sửa nội dung "
                "này tại Quản trị → Website."
            ),
        },
    ),
    (
        "about", "mission", "Sứ mệnh", "rich_text",
        {
            "title": "Sứ mệnh của chúng tôi",
            "body": (
                "Không để học sinh nào bị bỏ lại phía sau chỉ vì không ai nhận ra em đã bỏ lỡ "
                "bước nào."
            ),
        },
    ),
    (
        "contact", "intro", "Giới thiệu trang liên hệ", "rich_text",
        {
            "title": "Liên hệ với chúng tôi",
            "body": (
                "Hãy cho chúng tôi biết về con bạn, chúng tôi sẽ gọi lại trong một ngày làm việc."
            ),
        },
    ),
]

FAQS: list[tuple[str, str, str]] = [
    (
        "How much do lessons cost?",
        "Prices depend on the format and the number of sessions. Group classes start lower than "
        "one-to-one tutoring. See the Pricing page, or ask us for a quote.",
        "pricing",
    ),
    (
        "Do you teach online, in person, or both?",
        "Both. Classes run at our Hanoi centre and online, and some families mix the two. "
        "Recorded self-study courses are available at any time.",
        "general",
    ),
    (
        "Which grades do you teach?",
        "Grades 6 to 9, in Mathematics and Physics.",
        "general",
    ),
    (
        "How do I know my child is making progress?",
        "Every practice attempt updates a per-skill mastery estimate. Parents get a dashboard "
        "showing which skills are strong, which are weak, and what changed this week.",
        "learning",
    ),
    (
        "Can we try before paying?",
        "Yes. The free assessment is a thirty-minute session with a teacher and costs nothing, "
        "and the self-study practice has a free tier.",
        "pricing",
    ),
]


FAQS_VI: list[tuple[str, str, str]] = [
    (
        "Học phí là bao nhiêu?",
        "Học phí phụ thuộc hình thức học và số buổi. Lớp nhóm có mức thấp hơn gia sư 1 kèm 1. "
        "Xem trang Học phí, hoặc liên hệ để nhận báo giá.",
        "pricing",
    ),
    (
        "Trung tâm dạy trực tuyến, trực tiếp hay cả hai?",
        "Cả hai. Lớp học diễn ra tại trung tâm ở TP Vinh và trực tuyến; một số gia đình kết hợp "
        "cả hai. Khoá tự học quay sẵn có thể học bất cứ lúc nào.",
        "general",
    ),
    (
        "Trung tâm dạy những khối lớp nào?",
        "Từ lớp 6 đến lớp 12, môn Toán và Vật lý.",
        "general",
    ),
    (
        "Làm sao để biết con tôi đang tiến bộ?",
        "Mỗi lượt luyện tập đều cập nhật mức độ thành thạo theo từng kỹ năng. Phụ huynh có bảng "
        "theo dõi cho thấy kỹ năng nào tốt, kỹ năng nào yếu và tuần này đã thay đổi ra sao.",
        "learning",
    ),
    (
        "Chúng tôi có thể học thử trước khi đóng phí không?",
        "Có. Buổi đánh giá miễn phí kéo dài ba mươi phút cùng giáo viên và hoàn toàn không mất "
        "phí, phần luyện tập tự học cũng có gói miễn phí.",
        "pricing",
    ),
]


def seed_cms(db: Session) -> dict[str, int]:
    """Upsert the default CMS content. Safe to run repeatedly."""
    created = {"categories": 0, "settings": 0, "sections": 0, "faqs": 0, "announcements": 0}
    now = dt.datetime.now(dt.UTC)

    # --- categories ------------------------------------------------------------------
    by_slug: dict[str, ContentCategory] = {}
    # A category added to this list later goes to the end rather than taking a position an
    # existing row already holds — two categories sharing a position order arbitrarily, and
    # dragging them apart in the admin is the administrator's call, not the seed's.
    next_slot = (db.scalar(select(func.max(ContentCategory.position))) or 0) + 1
    for slug, name, name_vi, kind, _parent in CATEGORIES:
        category = db.scalar(select(ContentCategory).where(ContentCategory.slug == slug))
        if category is None:
            category = ContentCategory(
                slug=slug,
                name=name,
                i18n={"vi": {"name": name_vi}},
                kind=kind,
                position=next_slot,
                is_published=True,
                is_visible_in_nav=kind in {CategoryKind.SUBJECT, CategoryKind.GRADE},
            )
            db.add(category)
            db.flush()
            next_slot += 1
            created["categories"] += 1
        elif category.name == name_vi and not category.i18n:
            # A row seeded before categories were translatable: the Vietnamese name is sitting in
            # the English column. Move it, so /en stops showing Vietnamese. Anything an
            # administrator has since renamed is left alone.
            category.name = name
            category.i18n = {"vi": {"name": name_vi}}
        by_slug[slug] = category

    # Second pass so a parent listed later still resolves.
    for slug, _name, _name_vi, _kind, parent_slug in CATEGORIES:
        if parent_slug and by_slug[slug].parent_id is None:
            by_slug[slug].parent_id = by_slug[parent_slug].id

    # --- settings --------------------------------------------------------------------
    for position, (key, group, label, value, value_type) in enumerate(SETTINGS, start=1):
        if db.scalar(select(SiteSetting).where(SiteSetting.key == key)) is None:
            db.add(
                SiteSetting(
                    key=key, group=group, label=label, value=value,
                    value_type=value_type, position=position,
                )
            )
            created["settings"] += 1

    # --- page sections ---------------------------------------------------------------
    # Seeded already published: this copy is what the live site says today, so leaving it as a
    # draft would blank the homepage until someone pressed Publish.
    for position, (page, key, label, kind, content) in enumerate(SECTIONS, start=1):
        existing = db.scalar(
            select(SiteSection).where(
                SiteSection.page == page, SiteSection.key == key, SiteSection.locale == "en"
            )
        )
        if existing is None:
            db.add(
                SiteSection(
                    page=page, key=key, label=label, kind=kind, locale="en",
                    content=content, published_content=content,
                    status=ReviewStatus.PUBLISHED, published_at=now, position=position,
                )
            )
            created["sections"] += 1

    for position, (page, key, label, kind, content) in enumerate(SECTIONS_VI, start=1):
        existing = db.scalar(
            select(SiteSection).where(
                SiteSection.page == page, SiteSection.key == key, SiteSection.locale == "vi"
            )
        )
        if existing is None:
            db.add(
                SiteSection(
                    page=page, key=key, label=label, kind=kind, locale="vi",
                    content=content, published_content=content,
                    status=ReviewStatus.PUBLISHED, published_at=now, position=position,
                )
            )
            created["sections"] += 1

    # --- FAQs -------------------------------------------------------------------------
    for position, (question, answer, category) in enumerate(FAQS, start=1):
        if db.scalar(select(FaqItem).where(FaqItem.question == question)) is None:
            db.add(
                FaqItem(
                    question=question, answer=answer, category=category,
                    locale="en", position=position, is_published=True,
                )
            )
            created["faqs"] += 1

    for position, (question, answer, category) in enumerate(FAQS_VI, start=1):
        if db.scalar(select(FaqItem).where(FaqItem.question == question)) is None:
            db.add(
                FaqItem(
                    question=question, answer=answer, category=category,
                    locale="vi", position=position, is_published=True,
                )
            )
            created["faqs"] += 1

    # --- one example announcement, unpublished ---------------------------------------
    # Left unpublished on purpose: the seed should demonstrate the feature without putting a
    # fictional promotion on a real centre's homepage.
    title = "New term starts in September"
    if db.scalar(select(Announcement).where(Announcement.title == title)) is None:
        db.add(
            Announcement(
                title=title,
                body="Places are open for grade 6–12 Mathematics and Physics classes.",
                kind="banner",
                tone="brand",
                link_url="/contact",
                link_label="Book a free assessment",
                is_published=False,
                position=1,
            )
        )
        created["announcements"] += 1

    return created
