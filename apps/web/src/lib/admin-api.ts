/**
 * Typed client for the admin API.
 *
 * Kept separate from `lib/api.ts` because the admin surface is roughly as large as the rest of
 * the product put together, and because nothing outside `/admin` should be able to reach these
 * functions by autocompleting off the shared `api` object.
 */

import { apiFetch, API_BASE, readStoredTokens } from './api';

/* --------------------------------------------------------------------------------------
 * shared shapes
 * ------------------------------------------------------------------------------------ */

export interface Paged<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export type ReviewStatus = 'draft' | 'pending_review' | 'published' | 'rejected' | 'archived';
export type LeadStatus =
  | 'new'
  | 'contacted'
  | 'consulting'
  | 'interested'
  | 'enrolled'
  | 'completed'
  | 'rejected'
  | 'no_response'
  | 'closed';
export type EnrollmentStatus = 'pending' | 'confirmed' | 'active' | 'completed' | 'cancelled';
export type CategoryKind = 'subject' | 'grade' | 'program' | 'topic' | 'tag';
export type MediaKind = 'image' | 'document' | 'video' | 'audio';

/** Serialise a params object into a query string, dropping empty values. */
function qs(params: Record<string, unknown> = {}): string {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null || value === '') return;
    query.set(key, String(value));
  });
  const text = query.toString();
  return text ? `?${text}` : '';
}

/* --------------------------------------------------------------------------------------
 * entity types
 * ------------------------------------------------------------------------------------ */

export interface AdminOverview {
  students: number;
  active_students: number;
  teachers: number;
  parents: number;
  new_students_this_week: number;
  courses: number;
  published_courses: number;
  lessons: number;
  published_lessons: number;
  draft_lessons: number;
  exercises: number;
  published_exercises: number;
  pending_review_questions: number;
  programs: number;
  classes: number;
  active_enrollments: number;
  pending_enrollments: number;
  pending_consultations: number;
  new_consultations: number;
  pending_registrations: number;
  new_registrations: number;
  upcoming_classes: number;
  orders_awaiting_payment: number;
  revenue_vnd: number;
}

export interface DashboardFeed {
  upcoming_classes: {
    id: number;
    title: string;
    class_name: string;
    class_id: number;
    starts_at: string;
    ends_at: string;
    status: string;
    join_url: string | null;
    location: string | null;
  }[];
  recent_students: {
    id: number;
    name: string | null;
    email: string | null;
    grade: number;
    created_at: string;
    is_active: boolean;
  }[];
  recent_consultations: {
    id: number;
    source: 'contact' | 'tutoring';
    name: string;
    email: string;
    phone: string | null;
    interest: string;
    status: LeadStatus;
    created_at: string;
  }[];
  pending_enrollments: {
    id: number;
    student_name: string | null;
    class_name: string | null;
    status: string;
    payment_status: string;
    created_at: string;
  }[];
  recent_activity: {
    id: number;
    actor: string | null;
    action: string;
    entity_type: string;
    entity_id: number | null;
    summary: string;
    created_at: string;
  }[];
  attempts_this_week: number;
}

/**
 * Per-locale field overrides on a content record.
 *
 * The English columns stay the source of truth; this is what the Vietnamese site reads instead
 * where a field is present. Values are `unknown` because a translatable field can be a string
 * (`title`), a list (`objectives`) or a block array (`blocks`) depending on the model.
 */
export type Translations = Record<string, Record<string, unknown>>;

/** What the admin forms send back. `null` clears a field's translation. */
export type TranslationsInput = Record<string, Record<string, string | null>>;

export interface Category {
  id: number;
  slug: string;
  name: string;
  description: string | null;
  image_url: string | null;
  icon: string | null;
  color: string | null;
  kind: CategoryKind;
  parent_id: number | null;
  position: number;
  is_published: boolean;
  is_visible_in_nav: boolean;
  seo_title: string | null;
  seo_description: string | null;
  course_count?: number;
  product_count?: number;
  children?: Category[];
  translations?: Translations;
}

export interface AdminCourse {
  id: number;
  slug: string;
  title: string;
  grade: number;
  subject_id: number;
  subject_name: string | null;
  summary: string | null;
  description: string | null;
  estimated_hours: number;
  status: ReviewStatus;
  is_published: boolean;
  is_featured: boolean;
  thumbnail_url: string | null;
  teacher_id: number | null;
  position: number;
  seo_title: string | null;
  seo_description: string | null;
  categories: { id: number; slug: string; name: string; kind: string }[];
  translations?: Translations;
  /** Structure totals, present on list rows only. The detail endpoint returns the tree instead. */
  unit_count?: number;
  topic_count?: number;
  skill_count?: number;
  lesson_count?: number;
  created_at: string;
  updated_at: string;
}

export interface StructureUnit {
  id: number;
  slug: string;
  title: string;
  summary: string | null;
  icon: string | null;
  position: number;
  translations?: Translations;
  topics: StructureTopic[];
}

export interface StructureTopic {
  id: number;
  slug: string;
  title: string;
  summary: string | null;
  position: number;
  translations?: Translations;
  skills: {
    id: number;
    slug: string;
    name: string;
    difficulty: number;
    position: number;
    question_count: number;
    translations?: Translations;
  }[];
  lessons: {
    id: number;
    slug: string;
    title: string;
    status: ReviewStatus;
    position: number;
    estimated_minutes: number;
    block_count: number;
    has_draft: boolean;
    translations?: Translations;
  }[];
}

export interface AdminLesson {
  id: number;
  slug: string;
  title: string;
  topic_id: number;
  topic_title: string | null;
  skill_id: number | null;
  summary: string | null;
  objectives: string[];
  estimated_minutes: number;
  position: number;
  status: ReviewStatus;
  has_draft: boolean;
  version: number;
  thumbnail_url: string | null;
  block_count: number;
  draft_block_count: number;
  published_at: string | null;
  updated_at: string;
  created_at: string;
  translations?: Translations;
}

export interface LessonBlock {
  id?: string;
  type: string;
  section?: string;
  [key: string]: unknown;
}

export interface LessonDetail extends AdminLesson {
  blocks: LessonBlock[];
  draft_blocks: LessonBlock[];
  teacher_notes: string | null;
  video_id: number | null;
  skill_name: string | null;
  breadcrumb: {
    course_id: number | null;
    course_title: string | null;
    unit_id: number | null;
    unit_title: string | null;
    topic_id: number | null;
    topic_title: string | null;
  };
  resources: {
    id: number;
    title: string;
    url: string;
    resource_type: string;
    description: string | null;
    is_public: boolean;
    position: number;
  }[];
}

export interface AdminQuestion {
  id: number;
  slug: string;
  prompt: string;
  question_type: string;
  difficulty: number;
  skill_id: number;
  skill_name: string | null;
  subject_slug: string;
  topic_slug: string;
  grade: number;
  status: ReviewStatus;
  is_parametric: boolean;
  tags: string[];
  estimated_seconds: number;
  times_served: number;
  times_correct: number;
  success_rate: number | null;
  generated_by_ai: boolean;
  source: string | null;
  created_at: string;
  updated_at: string;
  translations?: Translations;
}

export interface QuestionDetail extends AdminQuestion {
  variables: Record<string, unknown>;
  constraints: string[];
  answer_spec: Record<string, unknown>;
  options: Record<string, unknown>;
  hints: { text: string }[];
  solution: { text?: string; math?: string }[];
  license: string | null;
  attribution: string | null;
}

export interface AdminStudent {
  id: number;
  user_id: number;
  full_name: string | null;
  email: string | null;
  phone: string | null;
  avatar_url: string | null;
  is_active: boolean;
  is_verified: boolean;
  locale: string;
  grade: number;
  school: string | null;
  date_of_birth: string | null;
  xp_total: number;
  level: number;
  streak_days: number;
  last_activity_date: string | null;
  learning_goals: string[];
  created_at: string;
  last_login_at: string | null;
  temporary_password?: string;
}

export interface AdminTeacher {
  id: number;
  user_id: number;
  slug: string | null;
  full_name: string | null;
  email: string | null;
  phone: string | null;
  photo_url: string | null;
  is_active: boolean;
  headline: string | null;
  bio: string | null;
  subjects: string[];
  grades: number[];
  qualifications: string[];
  years_experience: number;
  languages: string[];
  hourly_rate_vnd: number | null;
  rating: number;
  rating_count: number;
  is_featured: boolean;
  is_published: boolean;
  accepts_one_to_one: boolean;
  availability: { weekday: number; start: string; end: string }[];
  teaching_philosophy: string | null;
  teaching_style: string | null;
  specializations: string[];
  learning_formats: string[];
  video_intro_url: string | null;
  gallery: { url: string; caption?: string }[];
  social_links: Record<string, string>;
  public_email: string | null;
  public_phone: string | null;
  position: number;
  class_count?: number;
  temporary_password?: string;
  translations?: Translations;
}

export interface TeacherCredential {
  id: number;
  kind: string;
  title: string;
  organisation: string | null;
  year_start: number | null;
  year_end: number | null;
  description: string | null;
  url: string | null;
  position: number;
  is_published: boolean;
}

export interface LeadRow {
  source: 'contact' | 'tutoring';
  id: number;
  name: string;
  email: string;
  phone: string | null;
  subject_slug: string | null;
  grade: number | null;
  interest: string;
  preferred_format: string | null;
  status: LeadStatus;
  assigned_to_id: number | null;
  assigned_to_name: string | null;
  created_at: string;
  next_follow_up_at: string | null;
  converted_student_id: number | null;
}

export interface LeadDetail extends LeadRow {
  message: string | null;
  student_name: string | null;
  parent_name: string | null;
  parent_phone: string | null;
  school?: string | null;
  preferred_delivery: string | null;
  preferred_schedule?: string | null;
  preferred_slots?: { weekday: number; start: string; end: string }[];
  sessions_requested?: number;
  preferred_teacher?: { id: number; name: string | null } | null;
  interested_course?: { id: number; title: string } | null;
  interested_product?: { id: number; name: string } | null;
  admin_note: string | null;
  consultation_result: string | null;
  last_contacted_at: string | null;
  converted_student_name: string | null;
  converted_at: string | null;
  source_page: string | null;
  notes: {
    id: number;
    body: string;
    kind: string;
    author_id: number | null;
    author_name: string | null;
    created_at: string;
  }[];
}

export interface AdminEnrollment {
  id: number;
  student_id: number;
  student_name: string | null;
  student_email: string | null;
  student_grade: number | null;
  class_group_id: number;
  class_name: string | null;
  format: string | null;
  delivery_mode: string | null;
  teacher_id: number | null;
  teacher_name: string | null;
  status: EnrollmentStatus;
  payment_status: string;
  preferred_schedule: string | null;
  requested_format: string | null;
  notes: string | null;
  cancelled_reason: string | null;
  order_id: number | null;
  enrolled_at: string | null;
  approved_at: string | null;
  created_at: string;
}

export interface AdminClass {
  id: number;
  slug: string;
  name: string;
  course_id: number | null;
  course_title: string | null;
  product_id: number | null;
  teacher_id: number | null;
  teacher_name: string | null;
  format: string;
  delivery_mode: string;
  capacity: number;
  enrolled: number;
  seats_taken: number;
  seats_available: number;
  start_date: string | null;
  end_date: string | null;
  location: string | null;
  timezone: string;
  is_open_for_enrollment: boolean;
  schedule: {
    id?: number;
    weekday: number;
    weekday_label: string;
    start_time: string;
    end_time: string;
  }[];
  session_count: number;
  created_at: string;
  translations?: Translations;
}

export interface AdminSession {
  id: number;
  title: string;
  class_group_id: number;
  class_name: string | null;
  teacher_name: string | null;
  starts_at: string;
  ends_at: string;
  status: string;
  provider: string;
  join_url: string | null;
  recording_url: string | null;
  location: string | null;
  topic_summary: string | null;
}

export interface MediaAsset {
  id: number;
  filename: string;
  original_name: string;
  content_type: string;
  kind: MediaKind;
  size_bytes: number;
  url: string;
  title: string | null;
  alt_text: string | null;
  description: string | null;
  tags: string[];
  width: number | null;
  height: number | null;
  created_at: string;
  deduplicated?: boolean;
}

export interface SiteSection {
  id: number;
  page: string;
  key: string;
  locale: string;
  kind: string;
  label: string;
  position: number;
  status: ReviewStatus;
  content: Record<string, unknown>;
  published_content: Record<string, unknown>;
  has_unpublished_changes: boolean;
  published_at: string | null;
  updated_at: string;
}

export interface SiteSettingRow {
  id: number;
  key: string;
  group: string;
  label: string;
  value: Record<string, unknown>;
  value_type: string;
  description: string | null;
  position: number;
}

export interface FaqRow {
  id: number;
  question: string;
  answer: string;
  category: string;
  locale: string;
  position: number;
  is_published: boolean;
}

export interface AnnouncementRow {
  id: number;
  title: string;
  body: string | null;
  kind: string;
  tone: string;
  link_url: string | null;
  link_label: string | null;
  image_url: string | null;
  locale: string;
  starts_at: string | null;
  ends_at: string | null;
  is_published: boolean;
  is_live: boolean;
  position: number;
}

export interface TestimonialRow {
  id: number;
  author_name: string;
  author_role: string;
  quote: string;
  rating: number;
  subject_slug: string | null;
  grade: number | null;
  avatar_url: string | null;
  is_published: boolean;
  is_featured: boolean;
  position: number;
  translations?: Translations;
}

export interface ProgramRow {
  id: number;
  slug: string;
  name: string;
  tagline: string | null;
  description: string | null;
  format: string;
  delivery_mode: string;
  subject_slug: string | null;
  grade_min: number;
  grade_max: number;
  price_vnd: number;
  price_unit: string;
  sessions_included: number;
  session_minutes: number;
  capacity: number;
  features: string[];
  thumbnail_url: string | null;
  teacher_id: number | null;
  course_id: number | null;
  start_date: string | null;
  end_date: string | null;
  status: ReviewStatus;
  is_active: boolean;
  is_featured: boolean;
  position: number;
  categories: { id: number; name: string; slug: string }[];
  translations?: Translations;
}

export interface NotificationRow {
  id: number;
  kind: string;
  title: string;
  body: string | null;
  link_url: string | null;
  entity_type: string | null;
  entity_id: number | null;
  is_read: boolean;
  read_at: string | null;
  created_at: string;
}

export interface AuditRow {
  id: number;
  actor_id: number | null;
  actor_email: string | null;
  action: string;
  entity_type: string;
  entity_id: number | null;
  summary: string;
  changes: Record<string, unknown>;
  created_at: string;
}

export interface StaffMember {
  id: number;
  full_name: string;
  email: string;
  role: string;
  teacher_id: number | null;
}

/* --------------------------------------------------------------------------------------
 * client
 * ------------------------------------------------------------------------------------ */

const ADMIN = '/admin';

export const adminApi = {
  overview: () => apiFetch<AdminOverview>(`${ADMIN}/overview`),
  dashboard: () => apiFetch<DashboardFeed>(`${ADMIN}/dashboard`),
  search: (q: string) =>
    apiFetch<Record<string, { id: number; [k: string]: unknown }[]>>(
      `${ADMIN}/search${qs({ q })}`,
    ),
  staff: () => apiFetch<StaffMember[]>(`${ADMIN}/staff`),

  categories: {
    list: (params?: Record<string, unknown>) =>
      apiFetch<Paged<Category>>(`${ADMIN}/categories${qs(params)}`),
    tree: () => apiFetch<Category[]>(`${ADMIN}/categories/tree`),
    get: (id: number) => apiFetch<Category>(`${ADMIN}/categories/${id}`),
    create: (body: Partial<Category>) =>
      apiFetch<Category>(`${ADMIN}/categories`, { method: 'POST', body }),
    update: (id: number, body: Partial<Category>) =>
      apiFetch<Category>(`${ADMIN}/categories/${id}`, { method: 'PATCH', body }),
    publish: (id: number) =>
      apiFetch<Category>(`${ADMIN}/categories/${id}/publish`, { method: 'POST' }),
    unpublish: (id: number) =>
      apiFetch<Category>(`${ADMIN}/categories/${id}/unpublish`, { method: 'POST' }),
    reorder: (ids: number[]) =>
      apiFetch<{ reordered: number }>(`${ADMIN}/categories/reorder`, {
        method: 'POST',
        body: { ids },
      }),
    remove: (id: number, reassignChildrenTo?: number) =>
      apiFetch<void>(
        `${ADMIN}/categories/${id}${qs({ reassign_children_to: reassignChildrenTo })}`,
        { method: 'DELETE' },
      ),
  },

  subjects: {
    list: () => apiFetch<{ id: number; slug: string; name: string; position: number }[]>(
      `${ADMIN}/subjects`,
    ),
    create: (body: Record<string, unknown>) =>
      apiFetch<{ id: number; name: string }>(`${ADMIN}/subjects`, { method: 'POST', body }),
    update: (id: number, body: Record<string, unknown>) =>
      apiFetch<{ id: number }>(`${ADMIN}/subjects/${id}`, { method: 'PATCH', body }),
    remove: (id: number) => apiFetch<void>(`${ADMIN}/subjects/${id}`, { method: 'DELETE' }),
  },

  courses: {
    list: (params?: Record<string, unknown>) =>
      apiFetch<Paged<AdminCourse>>(`${ADMIN}/courses${qs(params)}`),
    get: (id: number) =>
      apiFetch<AdminCourse & { units: StructureUnit[] }>(`${ADMIN}/courses/${id}`),
    create: (body: Record<string, unknown>) =>
      apiFetch<AdminCourse>(`${ADMIN}/courses`, { method: 'POST', body }),
    update: (id: number, body: Record<string, unknown>) =>
      apiFetch<AdminCourse>(`${ADMIN}/courses/${id}`, { method: 'PATCH', body }),
    setStatus: (id: number, status: ReviewStatus) =>
      apiFetch<AdminCourse>(`${ADMIN}/courses/${id}/status${qs({ status })}`, {
        method: 'POST',
      }),
    duplicate: (id: number) =>
      apiFetch<AdminCourse & { copied: Record<string, number> }>(
        `${ADMIN}/courses/${id}/duplicate`,
        { method: 'POST' },
      ),
    reorder: (ids: number[]) =>
      apiFetch<{ reordered: number }>(`${ADMIN}/courses/reorder`, {
        method: 'POST',
        body: { ids },
      }),
    remove: (id: number) => apiFetch<void>(`${ADMIN}/courses/${id}`, { method: 'DELETE' }),
  },

  units: {
    create: (body: Record<string, unknown>) =>
      apiFetch<{ id: number; title: string }>(`${ADMIN}/units`, { method: 'POST', body }),
    update: (id: number, body: Record<string, unknown>) =>
      apiFetch<{ id: number }>(`${ADMIN}/units/${id}`, { method: 'PATCH', body }),
    remove: (id: number) => apiFetch<void>(`${ADMIN}/units/${id}`, { method: 'DELETE' }),
  },
  topics: {
    create: (body: Record<string, unknown>) =>
      apiFetch<{ id: number; title: string }>(`${ADMIN}/topics`, { method: 'POST', body }),
    update: (id: number, body: Record<string, unknown>) =>
      apiFetch<{ id: number }>(`${ADMIN}/topics/${id}`, { method: 'PATCH', body }),
    remove: (id: number) => apiFetch<void>(`${ADMIN}/topics/${id}`, { method: 'DELETE' }),
  },
  skills: {
    create: (body: Record<string, unknown>) =>
      apiFetch<{ id: number; name: string }>(`${ADMIN}/skills`, { method: 'POST', body }),
    update: (id: number, body: Record<string, unknown>) =>
      apiFetch<{ id: number }>(`${ADMIN}/skills/${id}`, { method: 'PATCH', body }),
    remove: (id: number) => apiFetch<void>(`${ADMIN}/skills/${id}`, { method: 'DELETE' }),
  },
  structure: {
    reorder: (nodeType: 'units' | 'topics' | 'skills' | 'lessons', ids: number[]) =>
      apiFetch<{ reordered: number }>(`${ADMIN}/structure/${nodeType}/reorder`, {
        method: 'POST',
        body: { ids },
      }),
  },

  lessons: {
    list: (params?: Record<string, unknown>) =>
      apiFetch<Paged<AdminLesson>>(`${ADMIN}/lessons${qs(params)}`),
    get: (id: number) => apiFetch<LessonDetail>(`${ADMIN}/lessons/${id}`),
    create: (body: Record<string, unknown>) =>
      apiFetch<AdminLesson>(`${ADMIN}/lessons`, { method: 'POST', body }),
    update: (id: number, body: Record<string, unknown>) =>
      apiFetch<AdminLesson>(`${ADMIN}/lessons/${id}`, { method: 'PATCH', body }),
    publish: (id: number) =>
      apiFetch<AdminLesson>(`${ADMIN}/lessons/${id}/publish`, { method: 'POST' }),
    unpublish: (id: number) =>
      apiFetch<AdminLesson>(`${ADMIN}/lessons/${id}/unpublish`, { method: 'POST' }),
    archive: (id: number) =>
      apiFetch<AdminLesson>(`${ADMIN}/lessons/${id}/archive`, { method: 'POST' }),
    discardDraft: (id: number) =>
      apiFetch<AdminLesson>(`${ADMIN}/lessons/${id}/discard-draft`, { method: 'POST' }),
    duplicate: (id: number) =>
      apiFetch<AdminLesson>(`${ADMIN}/lessons/${id}/duplicate`, { method: 'POST' }),
    preview: (id: number, draft = true) =>
      apiFetch<Record<string, unknown>>(`${ADMIN}/lessons/${id}/preview${qs({ draft })}`),
    revisions: (id: number) =>
      apiFetch<{ id: number; version: number; note: string | null; created_at: string; block_count: number }[]>(
        `${ADMIN}/lessons/${id}/revisions`,
      ),
    restore: (id: number, revisionId: number) =>
      apiFetch<AdminLesson>(`${ADMIN}/lessons/${id}/revisions/${revisionId}/restore`, {
        method: 'POST',
      }),
    remove: (id: number) => apiFetch<void>(`${ADMIN}/lessons/${id}`, { method: 'DELETE' }),
    addResource: (id: number, body: Record<string, unknown>) =>
      apiFetch<{ id: number }>(`${ADMIN}/lessons/${id}/resources`, { method: 'POST', body }),
    removeResource: (resourceId: number) =>
      apiFetch<void>(`${ADMIN}/lessons/resources/${resourceId}`, { method: 'DELETE' }),
    videos: () =>
      apiFetch<{ id: number; title: string; provider: string; external_id: string; playback_url: string | null }[]>(
        `${ADMIN}/lessons/videos/library`,
      ),
    createVideo: (body: Record<string, unknown>) =>
      apiFetch<{ id: number; title: string }>(`${ADMIN}/lessons/videos`, {
        method: 'POST',
        body,
      }),
  },

  questions: {
    list: (params?: Record<string, unknown>) =>
      apiFetch<Paged<AdminQuestion>>(`${ADMIN}/questions${qs(params)}`),
    get: (id: number) => apiFetch<QuestionDetail>(`${ADMIN}/questions/${id}`),
    create: (body: Record<string, unknown>) =>
      apiFetch<AdminQuestion>(`${ADMIN}/questions`, { method: 'POST', body }),
    update: (id: number, body: Record<string, unknown>) =>
      apiFetch<AdminQuestion>(`${ADMIN}/questions/${id}`, { method: 'PATCH', body }),
    /** `locale` renders the question as a student of that language would receive it. */
    preview: (id: number, params?: { seed?: number; reveal?: boolean; locale?: string }) =>
      apiFetch<Record<string, unknown>>(`${ADMIN}/questions/${id}/preview${qs(params)}`),
    publish: (id: number) =>
      apiFetch<AdminQuestion>(`${ADMIN}/questions/${id}/publish`, { method: 'POST' }),
    unpublish: (id: number) =>
      apiFetch<AdminQuestion>(`${ADMIN}/questions/${id}/unpublish`, { method: 'POST' }),
    archive: (id: number) =>
      apiFetch<AdminQuestion>(`${ADMIN}/questions/${id}/archive`, { method: 'POST' }),
    bulkStatus: (ids: number[], status: ReviewStatus) =>
      apiFetch<{ updated: number }>(`${ADMIN}/questions/bulk-status`, {
        method: 'POST',
        body: { ids, status },
      }),
    remove: (id: number) => apiFetch<void>(`${ADMIN}/questions/${id}`, { method: 'DELETE' }),
    importTemplate: () => apiFetch<Record<string, unknown>>(`${ADMIN}/questions/import/template`),
    import: (file: File, commit: boolean) => uploadFile(
      `${ADMIN}/questions/import${qs({ commit })}`,
      file,
    ),
  },

  students: {
    list: (params?: Record<string, unknown>) =>
      apiFetch<Paged<AdminStudent>>(`${ADMIN}/students${qs(params)}`),
    get: (id: number) => apiFetch<Record<string, unknown>>(`${ADMIN}/students/${id}`),
    create: (body: Record<string, unknown>) =>
      apiFetch<AdminStudent>(`${ADMIN}/students`, { method: 'POST', body }),
    update: (id: number, body: Record<string, unknown>) =>
      apiFetch<AdminStudent>(`${ADMIN}/students/${id}`, { method: 'PATCH', body }),
    setActive: (id: number, isActive: boolean) =>
      apiFetch<AdminStudent>(`${ADMIN}/students/${id}/set-active`, {
        method: 'POST',
        body: { is_active: isActive },
      }),
    resetPassword: (id: number, password?: string) =>
      apiFetch<{ temporary_password: string | null; message: string }>(
        `${ADMIN}/students/${id}/reset-password`,
        { method: 'POST', body: { password } },
      ),
    remove: (id: number) => apiFetch<void>(`${ADMIN}/students/${id}`, { method: 'DELETE' }),
  },

  teachers: {
    list: (params?: Record<string, unknown>) =>
      apiFetch<Paged<AdminTeacher>>(`${ADMIN}/teachers${qs(params)}`),
    get: (id: number) => apiFetch<Record<string, unknown>>(`${ADMIN}/teachers/${id}`),
    create: (body: Record<string, unknown>) =>
      apiFetch<AdminTeacher>(`${ADMIN}/teachers`, { method: 'POST', body }),
    update: (id: number, body: Record<string, unknown>) =>
      apiFetch<AdminTeacher>(`${ADMIN}/teachers/${id}`, { method: 'PATCH', body }),
    publish: (id: number) =>
      apiFetch<AdminTeacher>(`${ADMIN}/teachers/${id}/publish`, { method: 'POST' }),
    unpublish: (id: number) =>
      apiFetch<AdminTeacher>(`${ADMIN}/teachers/${id}/unpublish`, { method: 'POST' }),
    setActive: (id: number, isActive: boolean) =>
      apiFetch<AdminTeacher>(`${ADMIN}/teachers/${id}/set-active`, {
        method: 'POST',
        body: { is_active: isActive },
      }),
    resetPassword: (id: number, password?: string) =>
      apiFetch<{ temporary_password: string | null }>(
        `${ADMIN}/teachers/${id}/reset-password`,
        { method: 'POST', body: { password } },
      ),
    reorder: (ids: number[]) =>
      apiFetch<{ reordered: number }>(`${ADMIN}/teachers/reorder`, {
        method: 'POST',
        body: { ids },
      }),
    remove: (id: number) => apiFetch<void>(`${ADMIN}/teachers/${id}`, { method: 'DELETE' }),
    credentials: (id: number) =>
      apiFetch<TeacherCredential[]>(`${ADMIN}/teachers/${id}/credentials`),
    addCredential: (id: number, body: Record<string, unknown>) =>
      apiFetch<TeacherCredential>(`${ADMIN}/teachers/${id}/credentials`, {
        method: 'POST',
        body,
      }),
    updateCredential: (credentialId: number, body: Record<string, unknown>) =>
      apiFetch<TeacherCredential>(`${ADMIN}/teachers/credentials/${credentialId}`, {
        method: 'PATCH',
        body,
      }),
    removeCredential: (credentialId: number) =>
      apiFetch<void>(`${ADMIN}/teachers/credentials/${credentialId}`, { method: 'DELETE' }),
    assign: (id: number, body: Record<string, unknown>) =>
      apiFetch<{ id: number }>(`${ADMIN}/teachers/${id}/assignments`, { method: 'POST', body }),
    unassign: (assignmentId: number) =>
      apiFetch<void>(`${ADMIN}/teachers/assignments/${assignmentId}`, { method: 'DELETE' }),
    assignClass: (id: number, classId: number) =>
      apiFetch<{ class_id: number }>(`${ADMIN}/teachers/${id}/classes/${classId}`, {
        method: 'POST',
      }),
  },

  leads: {
    list: (params?: Record<string, unknown>) =>
      apiFetch<Paged<LeadRow>>(`${ADMIN}/leads${qs(params)}`),
    stats: () =>
      apiFetch<{ by_status: Record<string, number>; open: number; total: number }>(
        `${ADMIN}/leads/stats`,
      ),
    get: (source: string, id: number) =>
      apiFetch<LeadDetail>(`${ADMIN}/leads/${source}/${id}`),
    update: (source: string, id: number, body: Record<string, unknown>) =>
      apiFetch<LeadDetail>(`${ADMIN}/leads/${source}/${id}`, { method: 'PATCH', body }),
    addNote: (source: string, id: number, body: { body: string; kind: string }) =>
      apiFetch<{ id: number }>(`${ADMIN}/leads/${source}/${id}/notes`, {
        method: 'POST',
        body,
      }),
    removeNote: (noteId: number) =>
      apiFetch<void>(`${ADMIN}/leads/notes/${noteId}`, { method: 'DELETE' }),
    convert: (source: string, id: number, body: Record<string, unknown>) =>
      apiFetch<{
        student_id: number;
        student_name: string | null;
        enrollment_id: number | null;
        temporary_password: string | null;
        created_account: boolean;
      }>(`${ADMIN}/leads/${source}/${id}/convert`, { method: 'POST', body }),
    remove: (source: string, id: number) =>
      apiFetch<void>(`${ADMIN}/leads/${source}/${id}`, { method: 'DELETE' }),
  },

  enrollments: {
    list: (params?: Record<string, unknown>) =>
      apiFetch<Paged<AdminEnrollment>>(`${ADMIN}/enrollments${qs(params)}`),
    get: (id: number) => apiFetch<AdminEnrollment>(`${ADMIN}/enrollments/${id}`),
    create: (body: Record<string, unknown>) =>
      apiFetch<AdminEnrollment>(`${ADMIN}/enrollments`, { method: 'POST', body }),
    update: (id: number, body: Record<string, unknown>) =>
      apiFetch<AdminEnrollment>(`${ADMIN}/enrollments/${id}`, { method: 'PATCH', body }),
    approve: (id: number) =>
      apiFetch<AdminEnrollment>(`${ADMIN}/enrollments/${id}/approve`, { method: 'POST' }),
    activate: (id: number) =>
      apiFetch<AdminEnrollment>(`${ADMIN}/enrollments/${id}/activate`, { method: 'POST' }),
    reject: (id: number, reason?: string) =>
      apiFetch<AdminEnrollment>(`${ADMIN}/enrollments/${id}/reject${qs({ reason })}`, {
        method: 'POST',
      }),
    markPaid: (id: number) =>
      apiFetch<AdminEnrollment>(`${ADMIN}/enrollments/${id}/mark-paid`, { method: 'POST' }),
    remove: (id: number) => apiFetch<void>(`${ADMIN}/enrollments/${id}`, { method: 'DELETE' }),
  },

  orders: {
    list: (params?: Record<string, unknown>) =>
      apiFetch<Paged<Record<string, unknown>>>(`${ADMIN}/orders${qs(params)}`),
    stats: () => apiFetch<Record<string, unknown>>(`${ADMIN}/orders/stats`),
    markPaid: (id: number, body: Record<string, unknown> = {}) =>
      apiFetch<Record<string, unknown>>(`${ADMIN}/orders/${id}/mark-paid`, {
        method: 'POST',
        body,
      }),
  },

  classes: {
    list: (params?: Record<string, unknown>) =>
      apiFetch<Paged<AdminClass>>(`${ADMIN}/classes${qs(params)}`),
    get: (id: number) =>
      apiFetch<AdminClass & {
        roster: {
          enrollment_id: number;
          student_id: number;
          name: string | null;
          email: string | null;
          grade: number;
          status: string;
          payment_status: string;
          enrolled_at: string | null;
        }[];
        sessions: AdminSession[];
      }>(`${ADMIN}/classes/${id}`),
    create: (body: Record<string, unknown>) =>
      apiFetch<AdminClass>(`${ADMIN}/classes`, { method: 'POST', body }),
    update: (id: number, body: Record<string, unknown>) =>
      apiFetch<AdminClass>(`${ADMIN}/classes/${id}`, { method: 'PATCH', body }),
    remove: (id: number) => apiFetch<void>(`${ADMIN}/classes/${id}`, { method: 'DELETE' }),
    generateSessions: (id: number, body: Record<string, unknown>) =>
      apiFetch<{ created: number }>(`${ADMIN}/classes/${id}/generate-sessions`, {
        method: 'POST',
        body,
      }),
  },

  sessions: {
    list: (params?: Record<string, unknown>) =>
      apiFetch<Paged<AdminSession>>(`${ADMIN}/live-sessions${qs(params)}`),
    create: (body: Record<string, unknown>) =>
      apiFetch<AdminSession>(`${ADMIN}/live-sessions`, { method: 'POST', body }),
    update: (id: number, body: Record<string, unknown>) =>
      apiFetch<AdminSession>(`${ADMIN}/live-sessions/${id}`, { method: 'PATCH', body }),
    remove: (id: number) => apiFetch<void>(`${ADMIN}/live-sessions/${id}`, { method: 'DELETE' }),
    attendance: (id: number) =>
      apiFetch<Record<string, unknown>[]>(`${ADMIN}/live-sessions/${id}/attendance`),
  },

  media: {
    list: (params?: Record<string, unknown>) =>
      apiFetch<Paged<MediaAsset>>(`${ADMIN}/media${qs(params)}`),
    stats: () => apiFetch<Record<string, unknown>>(`${ADMIN}/media/stats/summary`),
    upload: (file: File, meta?: { title?: string; alt_text?: string }) =>
      uploadFile(`${ADMIN}/media/upload${qs(meta)}`, file) as Promise<MediaAsset>,
    update: (id: number, body: Record<string, unknown>) =>
      apiFetch<MediaAsset>(`${ADMIN}/media/${id}`, { method: 'PATCH', body }),
    usage: (id: number) =>
      apiFetch<{ in_use: boolean; lessons: { id: number; title: string }[]; resources: { id: number; title: string }[] }>(
        `${ADMIN}/media/${id}/usage`,
      ),
    remove: (id: number, force = false) =>
      apiFetch<void>(`${ADMIN}/media/${id}${qs({ force })}`, { method: 'DELETE' }),
  },

  cms: {
    pages: () =>
      apiFetch<{ page: string; sections: number; unpublished: number; locales: string[] }[]>(
        `${ADMIN}/cms/pages`,
      ),
    sections: (params?: Record<string, unknown>) =>
      apiFetch<SiteSection[]>(`${ADMIN}/cms/sections${qs(params)}`),
    createSection: (body: Record<string, unknown>) =>
      apiFetch<SiteSection>(`${ADMIN}/cms/sections`, { method: 'POST', body }),
    updateSection: (id: number, body: Record<string, unknown>) =>
      apiFetch<SiteSection>(`${ADMIN}/cms/sections/${id}`, { method: 'PATCH', body }),
    publishSection: (id: number) =>
      apiFetch<SiteSection>(`${ADMIN}/cms/sections/${id}/publish`, { method: 'POST' }),
    unpublishSection: (id: number) =>
      apiFetch<SiteSection>(`${ADMIN}/cms/sections/${id}/unpublish`, { method: 'POST' }),
    discardSection: (id: number) =>
      apiFetch<SiteSection>(`${ADMIN}/cms/sections/${id}/discard`, { method: 'POST' }),
    publishPage: (page: string) =>
      apiFetch<{ published: number }>(`${ADMIN}/cms/sections/publish-all${qs({ page })}`, {
        method: 'POST',
      }),
    removeSection: (id: number) =>
      apiFetch<void>(`${ADMIN}/cms/sections/${id}`, { method: 'DELETE' }),

    settings: (group?: string) =>
      apiFetch<SiteSettingRow[]>(`${ADMIN}/cms/settings${qs({ group })}`),
    setSetting: (key: string, value: Record<string, unknown>) =>
      apiFetch<{ key: string }>(`${ADMIN}/cms/settings/${key}`, {
        method: 'PUT',
        body: { value },
      }),

    faqs: (params?: Record<string, unknown>) =>
      apiFetch<FaqRow[]>(`${ADMIN}/cms/faqs${qs(params)}`),
    createFaq: (body: Record<string, unknown>) =>
      apiFetch<FaqRow>(`${ADMIN}/cms/faqs`, { method: 'POST', body }),
    updateFaq: (id: number, body: Record<string, unknown>) =>
      apiFetch<FaqRow>(`${ADMIN}/cms/faqs/${id}`, { method: 'PATCH', body }),
    removeFaq: (id: number) => apiFetch<void>(`${ADMIN}/cms/faqs/${id}`, { method: 'DELETE' }),
    reorderFaqs: (ids: number[]) =>
      apiFetch<{ reordered: number }>(`${ADMIN}/cms/faqs/reorder`, {
        method: 'POST',
        body: { ids },
      }),

    announcements: (params?: Record<string, unknown>) =>
      apiFetch<AnnouncementRow[]>(`${ADMIN}/cms/announcements${qs(params)}`),
    createAnnouncement: (body: Record<string, unknown>) =>
      apiFetch<AnnouncementRow>(`${ADMIN}/cms/announcements`, { method: 'POST', body }),
    updateAnnouncement: (id: number, body: Record<string, unknown>) =>
      apiFetch<AnnouncementRow>(`${ADMIN}/cms/announcements/${id}`, { method: 'PATCH', body }),
    removeAnnouncement: (id: number) =>
      apiFetch<void>(`${ADMIN}/cms/announcements/${id}`, { method: 'DELETE' }),

    testimonials: () => apiFetch<TestimonialRow[]>(`${ADMIN}/cms/testimonials`),
    createTestimonial: (body: Record<string, unknown>) =>
      apiFetch<TestimonialRow>(`${ADMIN}/cms/testimonials`, { method: 'POST', body }),
    updateTestimonial: (id: number, body: Record<string, unknown>) =>
      apiFetch<TestimonialRow>(`${ADMIN}/cms/testimonials/${id}`, { method: 'PATCH', body }),
    removeTestimonial: (id: number) =>
      apiFetch<void>(`${ADMIN}/cms/testimonials/${id}`, { method: 'DELETE' }),
    reorderTestimonials: (ids: number[]) =>
      apiFetch<{ reordered: number }>(`${ADMIN}/cms/testimonials/reorder`, {
        method: 'POST',
        body: { ids },
      }),

    posts: (params?: Record<string, unknown>) =>
      apiFetch<Paged<Record<string, unknown>>>(`${ADMIN}/cms/posts${qs(params)}`),
    post: (id: number) => apiFetch<Record<string, unknown>>(`${ADMIN}/cms/posts/${id}`),
    createPost: (body: Record<string, unknown>) =>
      apiFetch<Record<string, unknown>>(`${ADMIN}/cms/posts`, { method: 'POST', body }),
    updatePost: (id: number, body: Record<string, unknown>) =>
      apiFetch<Record<string, unknown>>(`${ADMIN}/cms/posts/${id}`, { method: 'PATCH', body }),
    removePost: (id: number) => apiFetch<void>(`${ADMIN}/cms/posts/${id}`, { method: 'DELETE' }),
  },

  programs: {
    list: (params?: Record<string, unknown>) =>
      apiFetch<Paged<ProgramRow>>(`${ADMIN}/programs${qs(params)}`),
    get: (id: number) => apiFetch<ProgramRow>(`${ADMIN}/programs/${id}`),
    create: (body: Record<string, unknown>) =>
      apiFetch<ProgramRow>(`${ADMIN}/programs`, { method: 'POST', body }),
    update: (id: number, body: Record<string, unknown>) =>
      apiFetch<ProgramRow>(`${ADMIN}/programs/${id}`, { method: 'PATCH', body }),
    setStatus: (id: number, status: ReviewStatus) =>
      apiFetch<ProgramRow>(`${ADMIN}/programs/${id}/status${qs({ status })}`, {
        method: 'POST',
      }),
    remove: (id: number) => apiFetch<void>(`${ADMIN}/programs/${id}`, { method: 'DELETE' }),
  },

  notifications: {
    list: (params?: Record<string, unknown>) =>
      apiFetch<Paged<NotificationRow> & { unread: number }>(
        `${ADMIN}/notifications${qs(params)}`,
      ),
    unreadCount: () => apiFetch<{ unread: number }>(`${ADMIN}/notifications/unread-count`),
    markRead: (id: number) =>
      apiFetch<{ id: number }>(`${ADMIN}/notifications/${id}/read`, { method: 'POST' }),
    markAllRead: () =>
      apiFetch<{ marked: number }>(`${ADMIN}/notifications/read-all`, { method: 'POST' }),
    remove: (id: number) =>
      apiFetch<void>(`${ADMIN}/notifications/${id}`, { method: 'DELETE' }),
  },

  audit: {
    list: (params?: Record<string, unknown>) =>
      apiFetch<Paged<AuditRow>>(`${ADMIN}/audit-log${qs(params)}`),
  },
};

/**
 * Multipart upload.
 *
 * `apiFetch` always JSON-encodes its body, so file uploads need their own path. The
 * Content-Type header is deliberately *not* set — the browser has to add it itself in order to
 * include the multipart boundary.
 */
async function uploadFile<T = Record<string, unknown>>(path: string, file: File): Promise<T> {
  const form = new FormData();
  form.append('file', file);

  const token = readStoredTokens()?.access_token;
  const response = await fetch(`${API_BASE}/api/v1${path}`, {
    method: 'POST',
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
    body: form,
  });

  const text = await response.text();
  let payload: unknown = null;
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      payload = text;
    }
  }
  if (!response.ok) {
    const detail =
      payload && typeof payload === 'object' && 'detail' in payload
        ? String((payload as { detail: unknown }).detail)
        : `Upload failed with status ${response.status}`;
    throw new Error(detail);
  }
  return payload as T;
}
