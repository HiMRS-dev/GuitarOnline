export type LoginPayload = {
  email: string;
  password: string;
};

export type TokenPair = {
  access_token: string;
  refresh_token: string;
  token_type: string;
};

export type Role = {
  id: string;
  name: string;
};

export type CurrentUser = {
  id: string;
  email: string;
  timezone: string;
  is_active: boolean;
  role: Role;
  created_at: string;
  updated_at: string;
};
