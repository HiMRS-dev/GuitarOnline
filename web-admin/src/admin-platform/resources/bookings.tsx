import { Datagrid, DateField, List, TextField, TextInput } from "react-admin";

const bookingFilters = [
  <TextInput key="teacher_id" source="teacher_id" label="Teacher ID" />,
  <TextInput key="student_id" source="student_id" label="Student ID" />,
  <TextInput key="status" source="status" label="Status" />,
  <TextInput key="from_utc" source="from_utc" label="From UTC (ISO)" />,
  <TextInput key="to_utc" source="to_utc" label="To UTC (ISO)" />
];

export function BookingsList() {
  return (
    <List title="Bookings" perPage={20} filters={bookingFilters}>
      <Datagrid bulkActionButtons={false}>
        <TextField source="booking_id" label="Booking ID" />
        <TextField source="slot_id" label="Slot ID" />
        <TextField source="teacher_id" label="Teacher ID" />
        <TextField source="student_id" label="Student ID" />
        <TextField source="status" label="Status" />
        <DateField source="slot_start_at_utc" label="Start UTC" showTime />
        <DateField source="slot_end_at_utc" label="End UTC" showTime />
        <TextField source="package_id" label="Package ID" emptyText="-" />
        <TextField source="cancellation_reason" label="Cancel Reason" emptyText="-" />
        <DateField source="updated_at_utc" label="Updated" showTime />
      </Datagrid>
    </List>
  );
}
