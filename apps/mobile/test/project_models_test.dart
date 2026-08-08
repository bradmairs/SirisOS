import 'package:flutter_test/flutter_test.dart';
import 'package:sirisos/src/services/project_service.dart';

void main() {
  test('ProjectRecord parses project identity and lifecycle', () {
    final project = ProjectRecord.fromJson({
      'id': 'project-1',
      'name': 'Tank site drainage',
      'description': 'Stormwater design',
      'kind': 'engineering',
      'status': 'active',
      'tags': ['stormwater'],
      'created_at': '2026-08-08T00:00:00+00:00',
      'updated_at': '2026-08-08T01:00:00+00:00',
    });

    expect(project.id, 'project-1');
    expect(project.kind, 'engineering');
    expect(project.status, 'active');
    expect(project.tags, ['stormwater']);
  });

  test('ProjectRelationship preserves canonical note identity', () {
    final relationship = ProjectRelationship.fromJson({
      'id': 'relationship-1',
      'project_id': 'project-1',
      'target_type': 'knowledge_note',
      'target_id': 'Engineering/Stormwater.md',
      'target_label': 'Stormwater design',
      'kind': 'contains',
      'provenance': 'manual',
    });

    expect(relationship.targetId, 'Engineering/Stormwater.md');
    expect(relationship.targetLabel, 'Stormwater design');
    expect(relationship.provenance, 'manual');
  });
}
