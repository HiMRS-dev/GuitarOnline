export type PageResponse<T> = {
  items: T[];
  total: number;
  limit: number;
  offset: number;
};
