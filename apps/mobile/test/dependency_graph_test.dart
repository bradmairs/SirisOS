import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:siris_os/src/core/dependency_graph.dart';

void main() {
  final graph = DependencyGraph.instance;

  setUp(() async {
    SharedPreferences.setMockInitialValues({});
    await graph.resetCustomEdges();
  });

  tearDown(() async {
    await graph.resetCustomEdges();
  });

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

  test('custom topology adds explicit UPS downstream impact', () async {
    await graph.addCustomEdge(
      dependentId: 'docker',
      dependencyId: 'ups',
      reason: 'Docker host is powered by the UPS.',
    );

    final impacts = graph.downstreamImpacts('ups');
    expect(impacts.map((item) => item.node.id), contains('docker'));
    expect(graph.customEdges.single.reason, 'Docker host is powered by the UPS.');
  });

  test('custom topology rejects dependency cycles', () async {
    await graph.addCustomEdge(
      dependentId: 'docker',
      dependencyId: 'ups',
    );

    await expectLater(
      graph.addCustomEdge(dependentId: 'ups', dependencyId: 'docker'),
      throwsA(isA<DependencyGraphException>()),
    );
  });

  test('multiple dependency roots deduplicate downstream nodes', () {
    final impacts = graph.downstreamForMany(['synology', 'hyper_backup']);
    final ids = impacts.map((item) => item.node.id).toList();

    expect(ids.where((id) => id == 'backup_analytics'), hasLength(1));
  });
}
