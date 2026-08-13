"""Vietnamese translations for the seeded marketing content.

The curriculum keeps its translations in ``content/<subject>/i18n/vi.yaml`` alongside the authored
English. The marketing content is seeded from Python rather than YAML, so its translations live
here — same idea, same shape: keyed by the record's natural key, holding only the fields that are
prose.

Everything here is applied to the ``i18n`` column by :func:`app.seed.seed.apply_marketing_vi`, so
an administrator can then edit it in the CMS like any other translation. Re-running the seed
refreshes translations that have not been edited and never touches the English columns.

The Vietnamese is written the way a Vietnamese centre would write it — addressing parents as
*quý phụ huynh* and students as *các em* — rather than transliterating the English sentence by
sentence.
"""

from __future__ import annotations

__all__ = [
    "BLOG_VI",
    "CLASSES_VI",
    "PRODUCTS_VI",
    "SETTINGS_VI",
    "TEACHERS_VI",
    "TESTIMONIALS_VI",
]


# slug -> {name, tagline, description, features}
PRODUCTS_VI: dict[str, dict] = {
    "one-to-one-mathematics": {
        "name": "Gia sư Toán 1 kèm 1",
        "tagline": "Một giáo viên dành trọn cho con bạn",
        "description": (
            "Các buổi học riêng hằng tuần, bám sát đúng những lỗ hổng của con — do mô hình đo "
            "mức độ thành thạo của chúng tôi xác định chứ không phải phỏng đoán. Học trực tuyến "
            "hoặc tại trung tâm."
        ),
        "features": [
            "Tiến độ riêng cho từng em",
            "Được chọn giáo viên",
            "Lịch học linh hoạt",
            "Báo cáo tiến bộ hằng tuần",
            "Học trực tuyến hoặc tại trung tâm",
        ],
    },
    "one-to-one-physics": {
        "name": "Gia sư Vật lý 1 kèm 1",
        "tagline": "Vật lý được giảng đến khi con thực sự hiểu",
        "description": (
            "Các buổi học Vật lý riêng, bắt đầu từ những gì con đã hình dung được và tiến dần "
            "tới khả năng giải bài tập một cách tự tin."
        ),
        "features": [
            "Tiến độ riêng cho từng em",
            "Có thí nghiệm minh hoạ",
            "Rèn kĩ năng làm bài thi",
            "Báo cáo tiến bộ hằng tuần",
        ],
    },
    "small-group-mathematics": {
        "name": "Toán nhóm nhỏ",
        "tagline": "Sáu học sinh, một giáo viên, thảo luận thực sự",
        "description": (
            "Mỗi nhóm tối đa sáu em để giáo viên nghe được tiếng nói của từng học sinh. Các em "
            "có trình độ tương đương cùng học theo một chương trình trọn khoá."
        ),
        "features": [
            "Tối đa 6 học sinh",
            "16 buổi mỗi khoá",
            "Báo cáo bằng văn bản cuối khoá",
            "Kèm quyền truy cập đầy đủ nền tảng học tập",
        ],
    },
    "small-group-physics": {
        "name": "Vật lý nhóm nhỏ",
        "tagline": "Học cùng nhau, với thiết bị các em được trực tiếp sử dụng",
        "description": (
            "Học Vật lý theo nhóm có thực hành — các em tự đo, tự ghi số liệu và tự giải thích, "
            "thay vì chỉ đọc về thí nghiệm."
        ),
        "features": [
            "Tối đa 6 học sinh",
            "Có thực hành trực tiếp",
            "16 buổi mỗi khoá",
            "Kèm quyền truy cập đầy đủ nền tảng học tập",
        ],
    },
    "online-live-classes": {
        "name": "Lớp học trực tuyến trực tiếp",
        "tagline": "Vẫn chất lượng giảng dạy ấy, từ bất cứ đâu trên cả nước",
        "description": (
            "Các lớp học trực tuyến theo lịch cố định, có ghi hình lại để một buổi vắng mặt "
            "không bao giờ trở thành một buổi bị bỏ lỡ."
        ),
        "features": [
            "Dạy trực tiếp, không phải video thu sẵn",
            "Ghi hình lại mọi buổi học",
            "Tối đa 12 học sinh",
            "Tham gia từ bất cứ đâu",
        ],
    },
    "recorded-course": {
        "name": "Khoá học ghi hình + Luyện tập",
        "tagline": "Học theo nhịp của mình, luyện tập không giới hạn",
        "description": (
            "Truy cập trọn bộ bài giảng video và toàn bộ hệ thống luyện tập thích ứng. Đây là "
            "cách tiết kiệm nhất để sử dụng nền tảng, hoàn toàn không ràng buộc lịch học."
        ),
        "features": [
            "Luyện tập thích ứng không giới hạn",
            "Toàn bộ bài giảng video",
            "Theo dõi tiến độ học tập",
            "Huỷ bất cứ lúc nào",
        ],
    },
    "hybrid-programme": {
        "name": "Chương trình kết hợp",
        "tagline": "Học trực tiếp cùng với tất cả những gì còn lại",
        "description": (
            "Lựa chọn đầy đủ nhất của chúng tôi: lớp học trực tiếp hằng tuần, quyền truy cập "
            "toàn bộ nền tảng, và mỗi tháng một buổi 1 kèm 1 để cùng giáo viên nhìn lại."
        ),
        "features": [
            "Một buổi học trực tiếp mỗi tuần",
            "Một buổi 1 kèm 1 mỗi tháng",
            "Luyện tập không giới hạn",
            "Ưu tiên hỗ trợ từ giáo viên",
            "Báo cáo chi tiết hằng tháng",
        ],
    },
}


# slug -> {name}
CLASSES_VI: dict[str, dict] = {
    "math-7-evening-group": {"name": "Toán lớp 7 — Nhóm tối thứ Ba"},
    "math-8-online-live": {"name": "Toán lớp 8 — Trực tuyến trực tiếp"},
    "physics-8-evening-group": {"name": "Vật lý lớp 8 — Nhóm tối thứ Tư"},
    "physics-9-exam-prep": {"name": "Vật lý lớp 9 — Luyện thi"},
    "math-6-foundations": {"name": "Toán lớp 6 — Nền tảng"},
}


# teacher account email -> {headline, bio, qualifications, languages}
TEACHERS_VI: dict[str, dict] = {
    "hieu@hietrieneducation.vn": {
        "headline": "Đồng sáng lập · Phụ trách chuyên môn Toán",
        "bio": (
            "Thầy Hiếu đã dạy Toán bậc trung học cơ sở hơn mười năm. Thầy được biết đến vì cách "
            "chia nhỏ những ý tưởng khó thành từng bước mà học sinh thực sự ghi nhớ được, và vì "
            "sự kiên quyết không cho em nào bỏ qua phần phân số khi chưa thật sự nắm vững."
        ),
        "qualifications": ["Thạc sĩ Lý luận và Phương pháp dạy học môn Toán",
                           "Chứng chỉ nghiệp vụ sư phạm quốc gia"],
        "languages": ["Tiếng Việt", "Tiếng Anh"],
    },
    "trien@hietrieneducation.vn": {
        "headline": "Đồng sáng lập · Phụ trách chuyên môn Vật lý",
        "bio": (
            "Cô Triền dạy Vật lý như một môn học thực nghiệm và đo đạc được, chứ không phải một "
            "danh sách công thức. Mỗi bài giảng của cô bắt đầu từ một hiện tượng các em nhìn "
            "thấy được, rồi mới đi tới phương trình giải thích hiện tượng đó."
        ),
        "qualifications": ["Thạc sĩ Vật lý", "Chứng chỉ nghiệp vụ sư phạm nâng cao"],
        "languages": ["Tiếng Việt", "Tiếng Anh"],
    },
    "mai@hietrieneducation.vn": {
        "headline": "Giáo viên Toán · Lớp 6-7",
        "bio": (
            "Cô Mai chuyên đồng hành cùng các em trong giai đoạn chuyển cấp lên trung học cơ sở, "
            "đặc biệt là những em đến lớp với suy nghĩ rằng mình 'không có năng khiếu Toán'."
        ),
        "qualifications": ["Cử nhân Toán học", "Chuyên về giai đoạn chuyển cấp tiểu học — THCS"],
        "languages": ["Tiếng Việt"],
    },
    "duc@hietrieneducation.vn": {
        "headline": "Giáo viên Vật lý · Luyện thi",
        "bio": (
            "Thầy Đức phụ trách các lớp luyện thi vào lớp 10, tập trung vào kĩ năng làm bài và "
            "cách trình bày lời giải sao cho không mất điểm ở những chỗ đáng tiếc."
        ),
        "qualifications": ["Cử nhân Sư phạm Vật lý", "Chuyên luyện thi vào lớp 10"],
        "languages": ["Tiếng Việt"],
    },
}


# author name -> {quote, author_role}
TESTIMONIALS_VI: dict[str, dict] = {
    "Nguyễn Thị Lan": {
        "author_role": "Phụ huynh học sinh lớp 7",
        "quote": (
            "Trước đây con gái tôi toàn giấu bài tập Toán không cho mẹ xem. Sau hai học kì, cháu "
            "đã tự giảng lại cho em trai. Báo cáo hằng tuần chỉ rõ cháu yếu ở kĩ năng nào, và "
            "phần luyện tập nhắm đúng vào đó chứ không bắt cháu làm mãi những gì đã biết."
        ),
    },
    "Trần Minh Quân": {
        "author_role": "Học sinh lớp 9",
        "quote": (
            "Bài luyện tập không bao giờ hết — nghe thì hiển nhiên nhưng không trang nào em từng "
            "thử làm được như vậy. Mỗi câu một khác nên em không thể học vẹt đáp án, buộc phải "
            "hiểu thật."
        ),
    },
    "Phạm Thu Hà": {
        "author_role": "Phụ huynh học sinh lớp 8",
        "quote": (
            "Chỉ trong một buổi, cô Triền đã tìm ra đúng chỗ hiểu sai khiến con tôi loay hoay "
            "suốt mấy tháng. Cháu đi từ 5,5 lên 8,0 chỉ trong một học kì."
        ),
    },
    "Lê Hoàng Nam": {
        "author_role": "Phụ huynh của hai học sinh",
        "quote": (
            "Hai cháu nhà tôi đều học ở đây, khác lớp và khác giáo viên. Điều tôi quý nhất là "
            "tôi được nhìn số liệu tiến bộ thật, thay vì chỉ được nghe 'cháu học ổn'."
        ),
    },
    "Vũ Thị Mai Anh": {
        "author_role": "Học sinh lớp 8",
        "quote": (
            "Lộ trình học chỉ rõ việc tiếp theo cần làm là gì. Trước đây em mất thời gian phân "
            "vân nên ôn phần nào; giờ em chỉ cần mở lên và bắt đầu."
        ),
    },
    "Đỗ Văn Thành": {
        "author_role": "Phụ huynh học sinh lớp 9",
        "quote": (
            "Nhờ lớp trực tuyến mà chuyển vào Đà Nẵng rồi cháu vẫn học được đúng thầy cũ. Các "
            "buổi ghi hình lại thực sự hữu ích trong tuần cháu bị ốm."
        ),
    },
}


# slug -> {title, excerpt, body, tags}
BLOG_VI: dict[str, dict] = {
    "why-fractions-are-hard": {
        "title": "Vì sao phân số thực sự khó (và điều gì giúp được)",
        "excerpt": (
            "Phân số là nơi đầu tiên khiến nhiều học sinh tin rằng mình 'dốt Toán'. Nguyên nhân "
            "không nằm ở sự chăm chỉ — mà ở chỗ phân số đòi hỏi một cách nghĩ hoàn toàn mới về "
            "con số."
        ),
        "tags": ["phân số", "lớp 6", "lỗi hiểu sai thường gặp"],
    },
    "what-mastery-actually-means": {
        "title": "'Thành thạo' trên nền tảng này thực sự nghĩa là gì",
        "excerpt": (
            "Khi chúng tôi nói một học sinh đã thành thạo một kĩ năng, đó là một khẳng định cụ "
            "thể dựa trên một mô hình cụ thể. Dưới đây là cách nó hoạt động."
        ),
        "tags": ["mức độ thành thạo", "học tập thích ứng", "minh bạch"],
    },
    "helping-without-doing-it-for-them": {
        "title": "Giúp con làm bài mà không làm hộ con",
        "excerpt": (
            "Một hướng dẫn ngắn dành cho quý phụ huynh muốn đồng hành cùng con nhưng chưa biết "
            "bắt đầu từ đâu — nhất là khi cách dạy Toán đã khác so với thời của mình."
        ),
        "tags": ["phụ huynh", "bài tập về nhà", "đồng hành"],
    },
}


# setting key -> {value}
#
# ``value`` is the whole JSON blob for the setting, translated. Only settings whose value is prose
# appear here: a phone number, an email address or a URL is the same in every language.
SETTINGS_VI: dict[str, dict] = {
    "contact.hours": {"value": {"text": "Thứ Hai – Thứ Bảy, 08:00–20:30"}},
    "footer.tagline": {
        "value": {"text": "Toán và Vật lý, dạy đến khi các em thật sự hiểu."}
    },
    "footer.copyright": {
        "value": {"text": "© HieuTrienEducation. Bảo lưu mọi quyền."}
    },
    "policy.privacy": {
        "value": {
            "markdown": (
                "Chúng tôi chỉ thu thập những thông tin cần thiết để dạy con bạn thật tốt. "
                "Quý phụ huynh có thể chỉnh sửa chính sách này tại Quản trị → Website → Cài đặt."
            )
        }
    },
    "policy.terms": {
        "value": {
            "markdown": "Chỉnh sửa điều khoản này tại Quản trị → Website → Cài đặt."
        }
    },
    "policy.refund": {
        "value": {
            "markdown": "Chỉnh sửa chính sách hoàn phí tại Quản trị → Website → Cài đặt."
        }
    },
}
