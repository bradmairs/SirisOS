import 'package:flutter_test/flutter_test.dart';
import 'package:siris_os/src/core/dependency_graph.dart';

void main() {
  final graph = DependencyGraph.instance;

  test('Synology failure exposes declared backup downstream chain', () {
    final impacts = graph.downstreamImpacts('synology');

    expect(impacts.map((item) => item.node.id), containsAll(['hyper_backup', 'backup_analytics']));
    expect(
      impacts.firstWhere((item) => item.node.id == 'backup_analytics').path,
      ['synology', 'hyper_backup', 'backup_analytics'],
    );
  });

  test('UPS has no guessed physical downstream dependencies', () {
    final impacts = graph.downstreamImpacts('ups');
    expect(impacts, isEmpty);
  });

  test('multiple dependency roots deduplicate downstream nodes', () {
    final impacts = graph.downstreamForMany(['synology', 'hyper_backup']);
    final ids = impacts.map((item) => item.node.id).toList();

    expect(ids.where((id) => id == 'backup_analytics'), hasLength(1));
  });
}
