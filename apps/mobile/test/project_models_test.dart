import 'package:flutter_test/flutter_test.dart';
import 'package:sirisos/src/core/module_registry.dart';
import 'package:sirisos/src/modules/app_module_registry.dart';
import 'package:sirisos/src/services/project_service.dart';

void main() {
  test('ProjectRecord parses project API payloads', () {
    final project = ProjectRecord.fromJson({
      'id': 'project-1',
      'name': 'Tank site drainage',
      'description': 'Stormwater design',
      'kind': 'engineering',
      'status': 'active',
      'tags': ['stormwater', 'SydneyWater'],
      'created_at': '2026-08-09T00:00:00+00:00',
      'updated_at': '2026-08-09T01:00:00+00:00',
    });

    expect(project.id, 'project-1');
    expect(project.kind, 'engineering');
    expect(project.status, 'active');
    expect(project.tags, ['stormwater', 'SydneyWater']);
  });

  test('ProjectRelationship parses Knowledge target metadata', () {
    final relationship = ProjectRelationship.fromJson({
      'id': 'relationship-1',
      'project_id': 'project-1',
      'target_type': 'knowledge_note',
      'target_id': 'Engineering/Drainage.md',
      'target_label': 'Drainage design',
      'kind': 'contains',
      'provenance': 'manual',
      'created_at': '2026-08-09T00:00:00+00:00',
    });

    expect(relationship.targetId, 'Engineering/Drainage.md');
    expect(relationship.targetLabel, 'Drainage design');
    expect(relationship.kind, 'contains');
    expect(relationship.provenance, 'manual');
  });

  test('Projects is a registered available module', () {
    final definition = SirisModuleRegistry.find('projects');
    final registration = AppModuleRegistry.find('projects');

    expect(definition, isNotNull);
    expect(definition!.label, 'Projects');
    expect(definition.supports(SirisModuleCapability.quickAction), isTrue);
    expect(registration, isNotNull);
    expect(registration!.isAvailable, isTrue);
  });
}
