import { Button } from "@mui/material";
import {
  Datagrid,
  DateField,
  FunctionField,
  List,
  TextField,
  TextInput,
  useNotify,
  useRecordContext,
  useRefresh,
  useUpdate
} from "react-admin";

import type { PackageRaRecord } from "../dataProvider";

const packageFilters = [
  <TextInput key="student_id" source="student_id" label="Student ID" />,
  <TextInput key="status" source="status" label="Status" />
];

export function PackagesList() {
  return (
    <List title="Packages" perPage={20} filters={packageFilters}>
      <Datagrid bulkActionButtons={false}>
        <TextField source="package_id" label="Package ID" />
        <TextField source="student_id" label="Student ID" />
        <TextField source="status" label="Status" />
        <TextField source="lessons_total" label="Total" />
        <TextField source="lessons_left" label="Left" />
        <TextField source="lessons_reserved" label="Reserved" />
        <FunctionField<PackageRaRecord> label="Price" render={(record) => renderPrice(record)} />
        <DateField source="expires_at_utc" label="Expires UTC" showTime />
        <FunctionField<PackageRaRecord> label="Action" render={() => <PackageCancelButton />} />
        <DateField source="updated_at_utc" label="Updated" showTime />
      </Datagrid>
    </List>
  );
}

function renderPrice(record: PackageRaRecord): string {
  if (!record.price_amount || !record.price_currency) {
    return "-";
  }
  return `${record.price_amount} ${record.price_currency}`;
}

function PackageCancelButton() {
  const record = useRecordContext<PackageRaRecord>();
  const notify = useNotify();
  const refresh = useRefresh();
  const [update, { isPending }] = useUpdate();

  if (!record) {
    return null;
  }
  if (record.status === "canceled") {
    return <span>-</span>;
  }

  const handleClick = () => {
    update(
      "packages",
      {
        id: record.id,
        data: { status: "canceled" },
        previousData: record
      },
      {
        onSuccess: () => {
          notify("Package canceled", { type: "info" });
          refresh();
        },
        onError: (error) => {
          notify(error instanceof Error ? error.message : "Package cancel failed", {
            type: "error"
          });
        }
      }
    );
  };

  return (
    <Button variant="outlined" size="small" disabled={isPending} onClick={handleClick}>
      Cancel
    </Button>
  );
}
