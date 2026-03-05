export type LoginPayload = {
  email: string;
  password: string;
};

export type TokenPair = {
  access_token: string;
  refresh_token: string;
  token_type: string;
};
