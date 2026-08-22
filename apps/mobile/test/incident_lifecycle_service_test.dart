import 'package:flutter_test/flutter_test.dart';
import 'package:siris_os/src/services/incident_lifecycle_service.dart';

void main() {
  test('parses a fully populated record', () {
    final record = IncidentLifecycleRecord.fromJson({
      'id': 'incident.power',
      'status': 'acknowledged',
      'assigned_to': 'Brad',
      'notes': 'Investigating',
      'created_at': '2026-08-09T00:00:00+00:00',
      'updated_at': '2026-08-09T00:10:00+00:00',
      'acknowledged_at': '2026-08-09T00:10:00+00:00',
      'resolved_at': null,
    });

    expect(record.id, 'incident.power');
    expect(record.status, IncidentLifecycleStatus.acknowledged);
    expect(record.assignedTo, 'Brad');
    expect(record.notes, 'Investigating');
    expect(record.acknowledgedAt, isNotNull);
    expect(record.resolvedAt, isNull);
  });

  test('an unrecognised status falls back to open rather than throwing', () {
    final record = IncidentLifecycleRecord.fromJson({
      'id': 'incident.compute',
      'status': 'something_new',
      'created_at': '2026-08-09T00:00:00+00:00',
      'updated_at': '2026-08-09T00:00:00+00:00',
    });

    expect(record.status, IncidentLifecycleStatus.open);
    expect(record.assignedTo, isNull);
  });
}
