import 'package:flutter_test/flutter_test.dart';
import 'package:sirisos/src/services/knowledge_service.dart';

void main() {
  test('related note preserves score and explanation reasons', () {
    final related = KnowledgeRelatedNote.fromJson({
      'note': {
        'path': 'Projects/Drainage.md',
        'title': 'Drainage',
        'modified_at': '2026-08-08T00:00:00Z',
        'size_bytes': 42,
        'tags': ['stormwater'],
        'wikilinks': ['Hydraulics'],
        'is_daily_note': false,
      },
      'score': 115,
      'reasons': ['linked from this note', 'shared tags: #stormwater'],
    });

    expect(related.note.path, 'Projects/Drainage.md');
    expect(related.score, 115);
    expect(related.reasons, contains('linked from this note'));
  });

  test('knowledge graph parses center and typed edges', () {
    final graph = KnowledgeGraph.fromJson({
      'center_path': 'Main.md',
      'nodes': [
        {'id': 'Main.md', 'title': 'Main', 'center': true},
        {'id': 'Linked.md', 'title': 'Linked', 'center': false},
      ],
      'edges': [
        {
          'source': 'Main.md',
          'target': 'Linked.md',
          'kind': 'outgoing',
          'label': 'linked from this note',
        },
      ],
    });

    expect(graph.nodes.first.center, isTrue);
    expect(graph.edges.single.kind, 'outgoing');
  });
}
