import { Datagrid, DateField, List, TextField, TextInput } from "react-admin";

const slotFilters = [
  <TextInput key="teacher_id" source="teacher_id" label="Teacher ID" alwaysOn />,
  <TextInput key="from_utc" source="from_utc" label="From UTC (ISO)" />,
  <TextInput key="to_utc" source="to_utc" label="To UTC (ISO)" />
];

export function SlotsList() {
  return (
    <List title="Slots" perPage={20} filters={slotFilters}>
      <Datagrid bulkActionButtons={false}>
        <TextField source="slot_id" label="Slot ID" />
        <TextField source="teacher_id" label="Teacher ID" />
        <DateField source="start_at_utc" label="Start UTC" showTime />
        <DateField source="end_at_utc" label="End UTC" showTime />
        <TextField source="slot_status" label="Slot Status" />
        <TextField source="aggregated_booking_status" label="Aggregate Status" />
        <TextField source="booking_status" label="Booking Status" emptyText="-" />
        <TextField source="booking_id" label="Booking ID" emptyText="-" />
        <DateField source="updated_at_utc" label="Updated" showTime />
      </Datagrid>
    </List>
  );
}
