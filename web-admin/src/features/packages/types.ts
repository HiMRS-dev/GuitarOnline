export type AdminPackage = {
  package_id: string;
  student_id: string;
  lessons_total: number;
  lessons_left: number;
  lessons_reserved: number;
  price_amount: string | null;
  price_currency: string | null;
  expires_at_utc: string;
  status: "active" | "expired" | "depleted" | "canceled";
  created_at_utc: string;
  updated_at_utc: string;
};

export type AdminPackageCreatePayload = {
  student_id: string;
  lessons_total: number;
  expires_at_utc: string;
  price_amount: string;
  price_currency: string;
};
