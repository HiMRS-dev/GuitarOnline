import {
  BooleanField,
  Datagrid,
  DateField,
  FunctionField,
  List,
  SelectInput,
  Show,
  SimpleShowLayout,
  TextField,
  TextInput
} from "react-admin";

import type { TeacherRaRecord } from "../dataProvider";

const teacherFilters = [
  <SelectInput
    key="status"
    source="status"
    label="Status"
    choices={[
      { id: "active", name: "active" },
      { id: "disabled", name: "disabled" }
    ]}
  />,
  <TextInput key="q" source="q" label="Search (name/email)" alwaysOn />,
  <TextInput key="tag" source="tag" label="Tag" />
];

export function TeachersList() {
  return (
    <List
      title="Teachers"
      perPage={20}
      sort={{ field: "created_at_utc", order: "DESC" }}
      filters={teacherFilters}
      filterDefaultValues={{ status: "active" }}
    >
      <Datagrid rowClick="show" bulkActionButtons={false}>
        <TextField source="teacher_id" label="Teacher ID" />
        <TextField source="full_name" label="Full Name" />
        <TextField source="email" label="Email" />
        <TextField source="timezone" label="Timezone" />
        <TextField source="status" label="Status" />
        <BooleanField source="is_active" label="Active" />
        <FunctionField<TeacherRaRecord>
          label="Tags"
          render={(record) => (record.tags.length > 0 ? record.tags.join(", ") : "-")}
        />
        <DateField source="created_at_utc" label="Created" showTime />
      </Datagrid>
    </List>
  );
}

export function TeachersShow() {
  return (
    <Show title="Teacher Detail">
      <SimpleShowLayout>
        <TextField source="teacher_id" label="Teacher ID" />
        <TextField source="profile_id" label="Profile ID" />
        <TextField source="full_name" label="Full Name" />
        <TextField source="display_name" label="Display Name" />
        <TextField source="email" label="Email" />
        <TextField source="timezone" label="Timezone" />
        <TextField source="status" label="Status" />
        <BooleanField source="is_active" label="Active" />
        <FunctionField<TeacherRaRecord>
          label="Tags"
          render={(record) => (record.tags.length > 0 ? record.tags.join(", ") : "-")}
        />
        <TextField source="bio" label="Bio" emptyText="-" />
        <TextField source="experience_years" label="Experience (years)" emptyText="-" />
        <DateField source="created_at_utc" label="Created" showTime />
        <DateField source="updated_at_utc" label="Updated" showTime />
      </SimpleShowLayout>
    </Show>
  );
}
