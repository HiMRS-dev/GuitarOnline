import { Button } from "@mui/material";
import {
  BooleanField,
  Datagrid,
  DateField,
  FunctionField,
  List,
  SelectInput,
  TextField,
  TextInput,
  useNotify,
  useRecordContext,
  useRefresh,
  useUpdate
} from "react-admin";

import type { StudentRaRecord } from "../dataProvider";

const studentFilters = [
  <TextInput key="q" source="q" label="Search (name/email)" alwaysOn />,
  <SelectInput
    key="is_active"
    source="is_active"
    label="Active"
    choices={[
      { id: true, name: "true" },
      { id: false, name: "false" }
    ]}
  />
];

export function StudentsList() {
  return (
    <List
      title="Students"
      perPage={20}
      sort={{ field: "created_at_utc", order: "DESC" }}
      filters={studentFilters}
    >
      <Datagrid bulkActionButtons={false}>
        <TextField source="user_id" label="User ID" />
        <TextField source="full_name" label="Full Name" />
        <TextField source="email" label="Email" />
        <TextField source="timezone" label="Timezone" />
        <TextField source="role" label="Role" />
        <BooleanField source="is_active" label="Active" />
        <FunctionField<StudentRaRecord> label="Action" render={() => <StudentActiveToggleButton />} />
        <DateField source="created_at_utc" label="Created" showTime />
        <DateField source="updated_at_utc" label="Updated" showTime />
      </Datagrid>
    </List>
  );
}

function StudentActiveToggleButton() {
  const record = useRecordContext<StudentRaRecord>();
  const notify = useNotify();
  const refresh = useRefresh();
  const [update, { isPending }] = useUpdate();

  if (!record) {
    return null;
  }

  const nextIsActive = !record.is_active;
  const actionLabel = nextIsActive ? "Activate" : "Deactivate";

  const handleClick = () => {
    update(
      "students",
      {
        id: record.id,
        data: { is_active: nextIsActive },
        previousData: record
      },
      {
        onSuccess: () => {
          notify(`Student ${nextIsActive ? "activated" : "deactivated"}`, { type: "info" });
          refresh();
        },
        onError: (error) => {
          notify(error instanceof Error ? error.message : "Student update failed", {
            type: "error"
          });
        }
      }
    );
  };

  return (
    <Button variant="outlined" size="small" disabled={isPending} onClick={handleClick}>
      {actionLabel}
    </Button>
  );
}
