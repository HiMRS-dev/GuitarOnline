export type TeacherListItem = {
  teacher_id: string;
  profile_id: string;
  email: string;
  display_name: string;
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
