import 'package:flutter_test/flutter_test.dart';
import 'package:siris_os/src/services/project_service.dart';

void main() {
  test('ProjectGraph parses project and Knowledge nodes with provenance edges', () {
    final graph = ProjectGraph.fromJson({
      'project_id': 'project-1',
      'nodes': [
        {
          'id': 'project:project-1',
          'label': 'Tank site drainage',
          'node_type': 'project',
          'detail': 'engineering · active',
          'center': true,
        },
        {
          'id': 'knowledge_note:Engineering/Drainage.md',
          'label': 'Drainage design',
          'node_type': 'knowledge_note',
          'detail': 'Engineering/Drainage.md',
          'center': false,
        },
      ],
      'edges': [
        {
          'source': 'project:project-1',
          'target': 'knowledge_note:Engineering/Drainage.md',
          'kind': 'contains',
          'label': 'Part of project',
          'provenance': 'manual',
        },
      ],
    });

    expect(graph.projectId, 'project-1');
    expect(graph.nodes, hasLength(2));
    expect(graph.nodes.first.center, isTrue);
    expect(graph.nodes.last.nodeType, 'knowledge_note');
    expect(graph.edges.single.kind, 'contains');
    expect(graph.edges.single.provenance, 'manual');
  });
}
