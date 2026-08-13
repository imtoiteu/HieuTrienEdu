/**
 * Typed client for the HieuTrienEducation API.
 *
 * One place that knows about the base URL, auth headers, and how the API reports errors.
 * Everything else calls typed functions, so a route change is a one-line edit here.
 */

/**
 * Base URL of the API.
 *
 * The default uses 127.0.0.1 rather than `localhost` deliberately. Node's fetch resolves
 * `localhost` to the IPv6 address `::1` first, and a server bound only to IPv4 refuses that
 * connection — which shows up as every server-rendered page silently losing its data. Naming
 * the IPv4 address removes the ambiguity. Docker Compose overrides this with the service name.
 */
export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? 'http://127.0.0.1:8000';

const API_PREFIX = '/api/v1';

export const TOKEN_STORAGE_KEY = 'hietedu.tokens';

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly detail?: unknown,
  ) {
    super(message);
    this.name = 'ApiError';
  }

  /** True when the failure is a network/connectivity problem rather than an HTTP response. */
  get isOffline(): boolean {
    return this.status === 0;
  }
}

export function readStoredTokens(): TokenPair | null {
  if (typeof window === 'undefined') return null;
  try {
    const raw = window.localStorage.getItem(TOKEN_STORAGE_KEY);
    return raw ? (JSON.parse(raw) as TokenPair) : null;
  } catch {
    // Corrupt storage should log the user out, not crash the page.
    return null;
  }
}

export function storeTokens(tokens: TokenPair | null): void {
  if (typeof window === 'undefined') return;
  if (tokens) {
    window.localStorage.setItem(TOKEN_STORAGE_KEY, JSON.stringify(tokens));
  } else {
    window.localStorage.removeItem(TOKEN_STORAGE_KEY);
  }
}

interface RequestOptions extends Omit<RequestInit, 'body'> {
  body?: unknown;
  token?: string | null;
  /** Skip the automatic Authorization header (used for public endpoints). */
  anonymous?: boolean;
  /**
   * Language to render content in.
   *
   * Server components must pass this explicitly — they handle many users' requests in one
   * process, so a module-level default would leak one visitor's language into another's page.
   * Client components can omit it and rely on `setClientLocale`, which is safe because a browser
   * only ever has one active locale.
   */
  locale?: string;
}

/**
 * The locale used for client-side requests, set once by the i18n provider.
 *
 * Deliberately not read on the server: see the `locale` option above.
 */
let clientLocale = 'en';

export function setClientLocale(locale: string): void {
  if (typeof window !== 'undefined') clientLocale = locale;
}

function extractDetail(payload: unknown): string | null {
  if (!payload || typeof payload !== 'object') return null;
  const detail = (payload as { detail?: unknown }).detail;
  if (typeof detail === 'string') return detail;
  // FastAPI validation errors come back as a list of {loc, msg, type}.
  if (Array.isArray(detail) && detail.length > 0) {
    const first = detail[0] as { msg?: string };
    if (typeof first?.msg === 'string') return first.msg;
  }
  return null;
}

export async function apiFetch<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { body, token, anonymous, headers, locale, ...rest } = options;

  const authToken = anonymous ? null : (token ?? readStoredTokens()?.access_token ?? null);

  // The API answers in whatever language this names, falling back to English. Content
  // (course titles, question prompts, hints) is translated server-side, so this is what makes
  // /vi show Vietnamese curriculum rather than Vietnamese chrome around English content.
  const activeLocale = locale ?? (typeof window !== 'undefined' ? clientLocale : 'en');

  // The locale goes in the URL as well as the header, and the URL is the one that matters.
  // A header alone leaves both languages sharing a single URL, and anything that caches by URL
  // then serves one language's response to the other: Next.js's build-time fetch cache did
  // exactly that, baking the English footer into the prerendered Vietnamese pages. Two languages
  // are two resources, so they get two URLs.
  const localisedPath = path.includes('?')
    ? `${path}&locale=${activeLocale}`
    : `${path}?locale=${activeLocale}`;

  const requestHeaders: Record<string, string> = {
    Accept: 'application/json',
    'X-Locale': activeLocale,
    ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}),
    ...(authToken ? { Authorization: `Bearer ${authToken}` } : {}),
    ...((headers as Record<string, string>) ?? {}),
  };

  let response: Response;
  try {
    response = await fetch(`${API_BASE}${API_PREFIX}${localisedPath}`, {
      ...rest,
      headers: requestHeaders,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch (cause) {
    // fetch only rejects on a network-level failure. In development the overwhelmingly common
    // cause is not that the API is down but that it is running and rejecting the request on
    // CORS grounds — which the browser reports to JavaScript as an indistinguishable network
    // error. That happens whenever the web app is served from an origin missing from the API's
    // CORS_ORIGINS, which is easy to hit because the dev server falls back to another port when
    // 3000 is taken. The hint costs nothing and saves a long debugging session.
    if (process.env.NODE_ENV !== 'production' && typeof window !== 'undefined') {
      console.error(
        `[api] Request to ${API_BASE} failed at the network level.\n` +
          `If the API is running, check that CORS_ORIGINS includes ${window.location.origin}.`,
      );
    }
    throw new ApiError('Cannot reach the server', 0, cause);
  }

  if (response.status === 204) {
    return undefined as T;
  }

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
    throw new ApiError(
      extractDetail(payload) ?? `Request failed with status ${response.status}`,
      response.status,
      payload,
    );
  }

  return payload as T;
}

/* --------------------------------------------------------------------------------------
 * types
 * ------------------------------------------------------------------------------------ */

export type UserRole = 'student' | 'parent' | 'teacher' | 'admin';

export interface StudentProfile {
  id: number;
  grade: number;
  school: string | null;
  xp_total: number;
  level: number;
  streak_days: number;
  longest_streak_days: number;
  last_activity_date: string | null;
  learning_goals: string[];
}

export interface TeacherProfile {
  id: number;
  headline: string | null;
  bio: string | null;
  subjects: string[];
  grades: number[];
  qualifications: string[];
  years_experience: number;
  languages: string[];
  rating: number;
  rating_count: number;
  is_featured: boolean;
  accepts_one_to_one: boolean;
  hourly_rate_vnd: number | null;
}

export interface User {
  id: number;
  email: string;
  full_name: string;
  role: UserRole;
  locale: string;
  avatar_url: string | null;
  phone: string | null;
  is_active: boolean;
  is_verified: boolean;
  created_at: string;
  student_profile: StudentProfile | null;
  teacher_profile: TeacherProfile | null;
  parent_profile: { id: number; contact_preference: string } | null;
}

export interface AuthResponse {
  user: User;
  tokens: TokenPair;
}

export interface Skill {
  id: number;
  slug: string;
  name: string;
  description: string | null;
  difficulty: number;
  position: number;
  tags: string[];
}

export interface Topic {
  id: number;
  slug: string;
  title: string;
  summary: string | null;
  position: number;
  skills: Skill[];
}

export interface Unit {
  id: number;
  slug: string;
  title: string;
  summary: string | null;
  icon: string | null;
  position: number;
  topics: Topic[];
}

export interface CourseSummary {
  id: number;
  slug: string;
  title: string;
  grade: number;
  summary: string | null;
  estimated_hours: number;
  unit_count: number;
  skill_count: number;
  lesson_count: number;
}

export interface CourseDetail extends CourseSummary {
  description: string | null;
  subject_slug: string | null;
  subject_name: string | null;
  units: Unit[];
}

export interface Subject {
  id: number;
  slug: string;
  name: string;
  description: string | null;
  icon: string | null;
  color: string | null;
  courses: CourseSummary[];
}

export interface LessonSummary {
  id: number;
  slug: string;
  title: string;
  summary: string | null;
  estimated_minutes: number;
  position: number;
  objectives: string[];
}

export interface LessonBlock {
  type: string;
  [key: string]: unknown;
}

export interface LessonDetail extends LessonSummary {
  blocks: LessonBlock[];
  topic_slug: string | null;
  topic_title: string | null;
  skill_slug: string | null;
  skill_name: string | null;
  video: {
    id: number;
    title: string;
    provider: string;
    external_id: string;
    duration_seconds: number;
    thumbnail_url: string | null;
    chapters: { time: number; label: string }[];
    captions: { lang: string; url: string; label: string }[];
    playback_url: string | null;
    attribution: string | null;
  } | null;
  attribution: string | null;
  license: string | null;
  progress_percent: number | null;
  completed: boolean | null;
  video_position_seconds: number | null;
}

export interface Choice {
  id: string;
  label: string;
  explanation?: string;
}

export interface ServedQuestion {
  variant_id: number;
  question_id: number;
  question_slug: string;
  question_type: string;
  difficulty: number;
  estimated_seconds: number;
  prompt: string;
  skill: { id: number; slug: string; name: string };
  hints: { index: number; text: string }[];
  hint_count: number;
  choices?: Choice[];
  blanks?: { id: string; type: string; label: string | null; unit: string | null }[];
  left?: { id: string; label: string }[];
  right?: { id: string; label: string }[];
  items?: { id: string; label: string }[];
  unit?: string | null;
  placeholder?: string | null;
  decimals?: number | null;
  symbols?: string[] | null;
  image_url?: string | null;
  interactive?: Record<string, unknown> | null;
}

export interface PracticeSession {
  id: number;
  mode: string;
  skill_id: number | null;
  target_questions: number;
  questions_answered: number;
  questions_correct: number;
  xp_earned: number;
  mastery_before: number | null;
  mastery_after: number | null;
  completed_at: string | null;
}

export interface SubmitResponse {
  is_correct: boolean;
  score: number;
  message: string;
  details: { id: string; is_correct: boolean; correct_answer: string }[];
  correct_answer: string | null;
  solution: { text?: string; math?: string }[];
  mastery: {
    before: number;
    after: number;
    delta: number;
    is_mastered: boolean;
    newly_mastered: boolean;
  };
  gamification: {
    xp_awarded: number;
    level_before: number;
    level_after: number;
    levelled_up: boolean;
    streak_days: number;
    streak_extended: boolean;
    new_achievements: {
      slug: string;
      name: string;
      description: string;
      icon: string;
      tier: string;
    }[];
  };
  session: PracticeSession | null;
}

export interface Recommendation {
  skill_id: number;
  skill_slug: string;
  skill_name: string;
  topic: string | null;
  score: number;
  reason: string;
  detail: string;
  mastery: number;
  readiness: number;
  difficulty: number;
}

export interface PathNode {
  skill_id: number;
  skill_slug: string;
  skill_name: string;
  topic: string | null;
  difficulty: number;
  mastery: number;
  status: 'mastered' | 'in_progress' | 'available' | 'locked';
  attempts: number;
  blocked_by: string[];
}

export interface Dashboard {
  student: {
    id: number;
    name: string | null;
    grade: number;
    xp_total: number;
    level: number;
    xp_into_level: number;
    xp_for_next_level: number;
    streak_days: number;
    longest_streak_days: number;
  };
  overall_mastery_percent: number;
  subjects: {
    subject_slug: string;
    subject_name: string;
    color: string | null;
    icon: string | null;
    mastery_percent: number;
    skills_tracked: number;
    skills_mastered: number;
  }[];
  recommendations: Recommendation[];
  weak_skills: {
    skill_id: number;
    skill_slug: string;
    skill_name: string;
    subject_slug: string | null;
    mastery: number;
    attempts: number;
    accuracy: number | null;
  }[];
  recent_attempts: {
    id: number;
    skill_name: string;
    is_correct: boolean;
    score: number;
    created_at: string;
  }[];
  upcoming_sessions: {
    id: number;
    title: string;
    class_name: string;
    starts_at: string;
    ends_at: string;
    join_url: string | null;
    provider: string;
    teacher_name: string | null;
  }[];
  assignments: {
    id: number;
    title: string;
    due_at: string | null;
    status: string;
    score_percent: number | null;
    question_count: number;
  }[];
  achievements: {
    slug: string;
    name: string;
    description: string;
    icon: string;
    tier: string;
    earned_at: string | null;
  }[];
  enrolled_courses: {
    course_id: number;
    slug: string;
    title: string;
    grade: number;
    last_activity_at: string | null;
  }[];
  stats: {
    skills_tracked: number;
    skills_mastered: number;
    skills_in_progress: number;
    total_attempts: number;
    total_correct: number;
    accuracy: number | null;
    average_mastery: number;
  };
  activity: { date: string; xp: number }[];
}

export interface TutoringProduct {
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
  is_featured: boolean;
}

export interface TeacherCard {
  id: number;
  user_id: number;
  full_name: string;
  headline: string | null;
  bio: string | null;
  avatar_url: string | null;
  subjects: string[];
  grades: number[];
  qualifications: string[];
  years_experience: number;
  languages: string[];
  rating: number;
  rating_count: number;
  is_featured: boolean;
  accepts_one_to_one: boolean;
  hourly_rate_vnd: number | null;
  availability: { weekday: number; start: string; end: string }[];
}

export interface ClassGroup {
  id: number;
  slug: string;
  name: string;
  format: string;
  delivery_mode: string;
  capacity: number;
  seats_taken: number;
  seats_available: number;
  start_date: string | null;
  end_date: string | null;
  location: string | null;
  timezone: string;
  is_open_for_enrollment: boolean;
  course_title: string | null;
  course_slug: string | null;
  grade: number | null;
  teacher: TeacherCard | null;
  schedule: { weekday: number; weekday_label: string; start_time: string; end_time: string }[];
  price_vnd: number | null;
}

export interface Testimonial {
  id: number;
  author_name: string;
  author_role: string;
  quote: string;
  rating: number;
  subject_slug: string | null;
  grade: number | null;
  avatar_url: string | null;
  is_featured: boolean;
}

export interface BlogPostSummary {
  id: number;
  slug: string;
  title: string;
  excerpt: string;
  category: string;
  tags: string[];
  cover_image_url: string | null;
  reading_minutes: number;
  author_name: string;
  published_at: string | null;
}

export interface BlogPostDetail extends BlogPostSummary {
  body_markdown: string;
}


export interface TeacherProfileSummary {
  id: number;
  slug: string | null;
  full_name: string;
  headline: string | null;
  photo_url: string | null;
  subjects: string[];
  grades: number[];
  years_experience: number;
  specializations: string[];
  learning_formats: string[];
  is_featured: boolean;
  rating: number;
  rating_count: number;
}

export interface TeacherCredentialPublic {
  id: number;
  title: string;
  organisation: string | null;
  year_start: number | null;
  year_end: number | null;
  description: string | null;
  url: string | null;
}

export interface TeacherProfileDetail extends TeacherProfileSummary {
  bio: string | null;
  qualifications: string[];
  languages: string[];
  teaching_philosophy: string | null;
  teaching_style: string | null;
  accepts_one_to_one: boolean;
  hourly_rate_vnd: number | null;
  video_intro_url: string | null;
  gallery: { url: string; caption?: string }[];
  social_links: Record<string, string>;
  contact: { email: string | null; phone: string | null };
  availability: { weekday: number; start: string; end: string }[];
  credentials: Record<string, TeacherCredentialPublic[]>;
  courses: { id: number; slug: string; title: string; grade: number; thumbnail_url: string | null }[];
  programs: {
    id: number;
    slug: string;
    name: string;
    format: string;
    price_vnd: number;
    price_unit: string;
    delivery_mode: string;
  }[];
  classes: {
    id: number;
    slug: string;
    name: string;
    format: string;
    start_date: string | null;
    delivery_mode: string;
  }[];
}

/** A published page section, flattened so a template can read fields directly. */
export type SiteSectionContent = Record<string, unknown> & {
  key: string;
  page: string;
  kind: string;
};

export interface PublicFaq {
  id: number;
  question: string;
  answer: string;
  category: string;
}

export interface PublicAnnouncement {
  id: number;
  title: string;
  body: string | null;
  kind: string;
  tone: string;
  link_url: string | null;
  link_label: string | null;
  image_url: string | null;
}

export interface PublicCategory {
  id: number;
  slug: string;
  name: string;
  description: string | null;
  image_url: string | null;
  icon: string | null;
  color: string | null;
  kind: string;
  seo_title: string | null;
  seo_description: string | null;
  children: PublicCategory[];
}

export interface SiteStats {
  subjects: number;
  courses: number;
  skills: number;
  questions: number;
  teachers: number;
  grade_range: string;
}

/* --------------------------------------------------------------------------------------
 * endpoints
 * ------------------------------------------------------------------------------------ */

export const api = {
  auth: {
    register: (body: Record<string, unknown>) =>
      apiFetch<AuthResponse>('/auth/register', { method: 'POST', body, anonymous: true }),
    login: (email: string, password: string) =>
      apiFetch<AuthResponse>('/auth/login', {
        method: 'POST',
        body: { email, password },
        anonymous: true,
      }),
    me: (token?: string) => apiFetch<User>('/auth/me', { token }),
    updateMe: (body: Record<string, unknown>) =>
      apiFetch<User>('/auth/me', { method: 'PATCH', body }),
    refresh: (refreshToken: string) =>
      apiFetch<TokenPair>('/auth/refresh', {
        method: 'POST',
        body: { refresh_token: refreshToken },
        anonymous: true,
      }),
  },

  curriculum: {
    /* Every method takes an optional `locale`. Server components must pass it — see the
       `locale` option on RequestOptions for why it cannot be inferred there. */
    subjects: (locale?: string) =>
      apiFetch<Subject[]>('/curriculum/subjects', { anonymous: true, locale }),
    courses: (params?: { subject?: string; grade?: number }, locale?: string) => {
      const query = new URLSearchParams();
      if (params?.subject) query.set('subject', params.subject);
      if (params?.grade) query.set('grade', String(params.grade));
      const suffix = query.toString() ? `?${query}` : '';
      return apiFetch<CourseSummary[]>(`/curriculum/courses${suffix}`, {
        anonymous: true,
        locale,
      });
    },
    course: (slug: string, locale?: string) =>
      apiFetch<CourseDetail>(`/curriculum/courses/${slug}`, { anonymous: true, locale }),
    unit: (slug: string, locale?: string) =>
      apiFetch<Unit>(`/curriculum/units/${slug}`, { anonymous: true, locale }),
    skill: (slug: string, locale?: string) =>
      apiFetch<Record<string, unknown>>(`/curriculum/skills/${slug}`, {
        anonymous: true,
        locale,
      }),
    topicLessons: (slug: string, locale?: string) =>
      apiFetch<LessonSummary[]>(`/curriculum/topics/${slug}/lessons`, {
        anonymous: true,
        locale,
      }),
    lesson: (slug: string, locale?: string) =>
      apiFetch<LessonDetail>(`/curriculum/lessons/${slug}`, { locale }),
    updateLessonProgress: (
      slug: string,
      body: { progress_percent: number; video_position_seconds?: number; completed?: boolean },
    ) => apiFetch<LessonDetail>(`/curriculum/lessons/${slug}/progress`, { method: 'PUT', body }),
  },

  practice: {
    startSession: (body: { skill_slug?: string; skill_id?: number; target_questions?: number }) =>
      apiFetch<PracticeSession>('/practice/sessions', { method: 'POST', body }),
    session: (id: number) => apiFetch<PracticeSession>(`/practice/sessions/${id}`),
    nextQuestion: (sessionId: number) =>
      apiFetch<ServedQuestion>(`/practice/sessions/${sessionId}/next`),
    quickQuestion: (skillSlug: string) =>
      apiFetch<ServedQuestion>(`/practice/skills/${skillSlug}/question`),
    hint: (variantId: number, index: number) =>
      apiFetch<{ index: number; text: string; is_last: boolean }>(
        `/practice/variants/${variantId}/hints/${index}`,
      ),
    submit: (body: {
      variant_id: number;
      answer: Record<string, unknown>;
      hints_used?: number;
      time_spent_seconds?: number;
      session_id?: number;
    }) => apiFetch<SubmitResponse>('/practice/submit', { method: 'POST', body }),
    completeSession: (id: number) =>
      apiFetch<PracticeSession>(`/practice/sessions/${id}/complete`, { method: 'POST' }),
    recommendations: (limit = 5) =>
      apiFetch<Recommendation[]>(`/practice/recommendations?limit=${limit}`),
    path: (unitSlug: string) => apiFetch<PathNode[]>(`/practice/path/${unitSlug}`),
    topicPath: (topicSlug: string) => apiFetch<PathNode[]>(`/practice/topics/${topicSlug}/path`),
  },

  progress: {
    dashboard: () => apiFetch<Dashboard>('/progress/dashboard'),
    mastery: (subject?: string) =>
      apiFetch<Record<string, unknown>[]>(
        `/progress/mastery${subject ? `?subject=${subject}` : ''}`,
      ),
    enroll: (courseSlug: string) =>
      apiFetch<{ enrolled: boolean; already_enrolled: boolean }>(
        `/progress/courses/${courseSlug}/enroll`,
        { method: 'POST' },
      ),
  },

  // Every public-content method takes an optional `locale`. Server components run in one shared
  // process serving both languages, so they must pass it explicitly — the module-level
  // `clientLocale` is only correct in the browser.
  tutoring: {
    products: (params?: { format?: string; subject?: string; grade?: number; locale?: string }) => {
      const query = new URLSearchParams();
      if (params?.format) query.set('format', params.format);
      if (params?.subject) query.set('subject', params.subject);
      if (params?.grade) query.set('grade', String(params.grade));
      const suffix = query.toString() ? `?${query}` : '';
      return apiFetch<TutoringProduct[]>(`/tutoring/products${suffix}`, {
        anonymous: true,
        locale: params?.locale,
      });
    },
    product: (slug: string, locale?: string) =>
      apiFetch<TutoringProduct>(`/tutoring/products/${slug}`, { anonymous: true, locale }),
    teachers: (params?: {
      subject?: string;
      grade?: number;
      featured?: boolean;
      locale?: string;
    }) => {
      const query = new URLSearchParams();
      if (params?.subject) query.set('subject', params.subject);
      if (params?.grade) query.set('grade', String(params.grade));
      if (params?.featured !== undefined) query.set('featured', String(params.featured));
      const suffix = query.toString() ? `?${query}` : '';
      return apiFetch<TeacherCard[]>(`/tutoring/teachers${suffix}`, {
        anonymous: true,
        locale: params?.locale,
      });
    },
    teacher: (id: number, locale?: string) =>
      apiFetch<TeacherCard>(`/tutoring/teachers/${id}`, { anonymous: true, locale }),
    profiles: (params?: { subject?: string; featured?: boolean; locale?: string }) => {
      const query = new URLSearchParams();
      if (params?.subject) query.set('subject', params.subject);
      if (params?.featured !== undefined) query.set('featured', String(params.featured));
      const suffix = query.toString() ? `?${query}` : '';
      return apiFetch<TeacherProfileSummary[]>(`/tutoring/profiles${suffix}`, {
        anonymous: true,
        locale: params?.locale,
      });
    },
    profile: (slug: string, locale?: string) =>
      apiFetch<TeacherProfileDetail>(`/tutoring/profiles/${slug}`, { anonymous: true, locale }),
    classes: (params?: {
      subject?: string;
      grade?: number;
      format?: string;
      locale?: string;
    }) => {
      const query = new URLSearchParams();
      if (params?.subject) query.set('subject', params.subject);
      if (params?.grade) query.set('grade', String(params.grade));
      if (params?.format) query.set('format', params.format);
      const suffix = query.toString() ? `?${query}` : '';
      return apiFetch<ClassGroup[]>(`/tutoring/classes${suffix}`, {
        anonymous: true,
        locale: params?.locale,
      });
    },
    createRequest: (body: Record<string, unknown>) =>
      apiFetch<{ id: number; status: string }>('/tutoring/requests', {
        method: 'POST',
        body,
        anonymous: true,
      }),
    enroll: (body: { class_group_id: number; student_id?: number; notes?: string }) =>
      apiFetch<Record<string, unknown>>('/tutoring/enroll', { method: 'POST', body }),
  },

  site: {
    testimonials: (featured?: boolean, locale?: string) =>
      apiFetch<Testimonial[]>(
        `/site/testimonials${featured !== undefined ? `?featured=${featured}` : ''}`,
        { anonymous: true, locale },
      ),
    posts: (category?: string, locale?: string) =>
      apiFetch<BlogPostSummary[]>(`/site/posts${category ? `?category=${category}` : ''}`, {
        anonymous: true,
        locale,
      }),
    post: (slug: string, locale?: string) =>
      apiFetch<BlogPostDetail>(`/site/posts/${slug}`, { anonymous: true, locale }),
    stats: () => apiFetch<SiteStats>('/site/stats', { anonymous: true }),
    contact: (body: Record<string, unknown>) =>
      apiFetch<{ id: number; received: boolean; message: string }>('/site/contact', {
        method: 'POST',
        body,
        anonymous: true,
      }),

    /* ---- admin-managed website content ---- */
    settings: (locale?: string) =>
      apiFetch<Record<string, Record<string, string>>>('/site/settings', {
        anonymous: true,
        locale,
      }),
    sections: (page: string, locale?: string) =>
      // The locale goes through the request option, not the path: apiFetch adds `locale` to every
      // URL itself, and a second copy in the path would be overridden by it.
      apiFetch<Record<string, SiteSectionContent>>(`/site/sections?page=${page}`, {
        anonymous: true,
        locale,
      }),
    faqs: (category?: string, locale?: string) =>
      apiFetch<PublicFaq[]>(`/site/faqs${category ? `?category=${category}` : ''}`, {
        anonymous: true,
        locale,
      }),
    announcements: (kind?: string, locale?: string) =>
      apiFetch<PublicAnnouncement[]>(`/site/announcements${kind ? `?kind=${kind}` : ''}`, {
        anonymous: true,
        locale,
      }),
    categories: (params?: { kind?: string; nav_only?: boolean }) => {
      const query = new URLSearchParams();
      if (params?.kind) query.set('kind', params.kind);
      if (params?.nav_only) query.set('nav_only', 'true');
      const suffix = query.toString() ? `?${query}` : '';
      return apiFetch<PublicCategory[]>(`/site/categories${suffix}`, { anonymous: true });
    },
  },

  teacher: {
    questions: (params: Record<string, string | number | undefined> = {}) => {
      const query = new URLSearchParams();
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== '') query.set(key, String(value));
      });
      const suffix = query.toString() ? `?${query}` : '';
      return apiFetch<{
        items: Record<string, unknown>[];
        total: number;
        page: number;
        page_size: number;
      }>(`/teacher/questions${suffix}`);
    },
    previewQuestion: (id: number, seed?: number) =>
      apiFetch<Record<string, unknown>>(
        `/teacher/questions/${id}/preview${seed !== undefined ? `?seed=${seed}` : ''}`,
      ),
    createQuestion: (body: Record<string, unknown>) =>
      apiFetch<Record<string, unknown>>('/teacher/questions', { method: 'POST', body }),
    publishQuestion: (id: number) =>
      apiFetch<Record<string, unknown>>(`/teacher/questions/${id}/publish`, { method: 'POST' }),
    classes: () => apiFetch<Record<string, unknown>[]>('/teacher/classes'),
    classStudents: (id: number) =>
      apiFetch<Record<string, unknown>[]>(`/teacher/classes/${id}/students`),
    students: () => apiFetch<Record<string, unknown>[]>('/teacher/students'),
    studentMastery: (id: number) =>
      apiFetch<Record<string, unknown>[]>(`/teacher/students/${id}/mastery`),
    analytics: (classId?: number) =>
      apiFetch<Record<string, unknown>>(
        `/teacher/analytics${classId ? `?class_id=${classId}` : ''}`,
      ),
    assignments: () => apiFetch<Record<string, unknown>[]>('/teacher/assignments'),
    createAssignment: (body: Record<string, unknown>) =>
      apiFetch<Record<string, unknown>>('/teacher/assignments', { method: 'POST', body }),
    scheduleLiveSession: (body: Record<string, unknown>) =>
      apiFetch<Record<string, unknown>>('/teacher/live-sessions', { method: 'POST', body }),
  },

  admin: {
    overview: () => apiFetch<Record<string, number>>('/admin/overview'),
    users: (params?: { role?: string; search?: string }) => {
      const query = new URLSearchParams();
      if (params?.role) query.set('role', params.role);
      if (params?.search) query.set('search', params.search);
      const suffix = query.toString() ? `?${query}` : '';
      return apiFetch<Record<string, unknown>[]>(`/admin/users${suffix}`);
    },
    classes: () => apiFetch<Record<string, unknown>[]>('/admin/classes'),
    orders: (status?: string) =>
      apiFetch<Record<string, unknown>[]>(`/admin/orders${status ? `?status=${status}` : ''}`),
    markPaid: (id: number, body: Record<string, unknown> = {}) =>
      apiFetch<Record<string, unknown>>(`/admin/orders/${id}/mark-paid`, {
        method: 'POST',
        body,
      }),
    leads: () => apiFetch<Record<string, unknown>[]>('/admin/leads'),
    tutoringRequests: () => apiFetch<Record<string, unknown>[]>('/admin/tutoring-requests'),
    liveSessions: () => apiFetch<Record<string, unknown>[]>('/admin/live-sessions'),
  },

  parent: {
    children: () => apiFetch<Record<string, unknown>[]>('/parent/children'),
    childProgress: (id: number) =>
      apiFetch<Record<string, unknown>>(`/parent/children/${id}/progress`),
    childAttendance: (id: number) =>
      apiFetch<Record<string, unknown>>(`/parent/children/${id}/attendance`),
    childSchedule: (id: number) =>
      apiFetch<Record<string, unknown>[]>(`/parent/children/${id}/schedule`),
    payments: () => apiFetch<Record<string, unknown>[]>('/parent/payments'),
    linkChild: (studentEmail: string) =>
      apiFetch<Record<string, unknown>>('/parent/children/link', {
        method: 'POST',
        body: { student_email: studentEmail },
      }),
  },

  ai: {
    status: () =>
      apiFetch<{
        enabled: boolean;
        provider: string;
        model: string | null;
        features: Record<string, string>;
        message: string;
      }>('/ai/status', { anonymous: true }),
    tutorHint: (variantId: number, studentAnswer: string) =>
      apiFetch<Record<string, unknown>>('/ai/tutor-hint', {
        method: 'POST',
        body: { variant_id: variantId, student_answer: studentAnswer },
      }),
  },
};
