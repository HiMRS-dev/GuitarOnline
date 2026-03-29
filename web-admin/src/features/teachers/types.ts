export type TeacherListItem = {
  teacher_id: string;
  profile_id: string;
  email: string;
  full_name: string;
  display_name: string;
  timezone: string;
  status: string;
  is_active: boolean;
  tags: string[];
  created_at_utc: string;
  updated_at_utc: string;
};

export type TeacherDetail = TeacherListItem & {
  bio: string;
  experience_years: number;
};

export type TeacherScheduleWindow = {
  schedule_window_id: string;
  weekday: number;
  start_local_time: string;
  end_local_time: string;
  moscow_start_weekday: number;
  moscow_end_weekday: number;
  moscow_start_time: string;
  moscow_end_time: string;
  created_at_utc: string;
  updated_at_utc: string;
};

export type TeacherSchedule = {
  teacher_id: string;
  timezone: string;
  windows: TeacherScheduleWindow[];
};

export type TeacherScheduleWindowWrite = {
  weekday: number;
  start_local_time: string;
  end_local_time: string;
};

export type TeacherScheduleUpsertPayload = {
  windows: TeacherScheduleWindowWrite[];
};
