import 'package:flutter_test/flutter_test.dart';
import 'package:siris_os/src/core/project_context_provider.dart';
import 'package:siris_os/src/core/siris_context_service.dart';
import 'package:siris_os/src/services/project_service.dart';

void main() {
  final base = ProjectRecord(
    id: 'project-1',
    name: 'Tank site drainage',
    description: 'Stormwater design',
    kind: 'engineering',
    status: 'active',
    tags: const ['stormwater'],
    createdAt: DateTime.fromMillisecondsSinceEpoch(0),
    updatedAt: DateTime.fromMillisecondsSinceEpoch(0),
  );

  test('engineering project maps to explicit engineering context', () {
    final fact = ProjectContextProvider.factFor(base);
    expect(fact.id, 'project.current.project-1');
    expect(fact.label, 'Project: Tank site drainage');
    expect(fact.domain, SirisContextDomain.engineering);
    expect(fact.source, 'projects.manual_selection');
    expect(fact.priority, 55);
  });

  test('homelab and personal project kinds map to safe context domains', () {
    expect(ProjectContextProvider.domainFor('homelab'), SirisContextDomain.homelab);
    expect(ProjectContextProvider.domainFor('travel'), SirisContextDomain.personal);
    expect(ProjectContextProvider.domainFor('fitness'), SirisContextDomain.personal);
  });

  test('CurrentProjectState parses nullable selection response', () {
    final empty = CurrentProjectState.fromJson({
      'project': null,
      'selected_at': '2026-08-09T00:00:00+00:00',
      'provenance': 'manual',
    });
    expect(empty.project, isNull);
    expect(empty.provenance, 'manual');

    final selected = CurrentProjectState.fromJson({
      'project': {
        'id': 'project-1',
        'name': 'Tank site drainage',
        'description': 'Stormwater design',
        'kind': 'engineering',
        'status': 'active',
        'tags': ['stormwater'],
        'created_at': '2026-08-09T00:00:00+00:00',
        'updated_at': '2026-08-09T00:00:00+00:00',
      },
      'selected_at': '2026-08-09T00:10:00+00:00',
      'provenance': 'manual',
    });
    expect(selected.project?.id, 'project-1');
  });
}
