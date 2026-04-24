import { BooleanField, Datagrid, DateField, List, SelectInput, TextField, TextInput } from "react-admin";

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
        <DateField source="created_at_utc" label="Created" showTime />
        <DateField source="updated_at_utc" label="Updated" showTime />
      </Datagrid>
    </List>
  );
}
