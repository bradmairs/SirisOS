import 'package:flutter_test/flutter_test.dart';
import 'package:siris_os/src/core/dependency_graph.dart';
import 'package:siris_os/src/services/digital_twin_service.dart';

/// In-memory stand-in for the real `/api/v1/digital-twin` backend, matching
/// its idempotent-duplicate and remove/reset semantics closely enough for
/// DependencyGraph's own tests -- DependencyGraph already does its own
/// cycle/self/node-existence validation client-side before ever calling this,
/// so the fake doesn't need to re-implement that.
class _FakeDigitalTwinService implements DigitalTwinService {
  final List<DependencyEdge> stored = [];

  @override
  Future<List<DependencyEdge>> fetchCustomEdges() async => List.of(stored);

  @override
  Future<DependencyEdge> addEdge({
    required String dependentId,
    required String dependencyId,
    String? reason,
  }) async {
    final candidate = DependencyEdge(
      dependentId: dependentId,
      dependencyId: dependencyId,
      reason: reason ?? '$dependentId depends on $dependencyId.',
    );
    final existing = stored.where((edge) => edge.key == candidate.key).firstOrNull;
    if (existing != null) return existing;
    stored.add(candidate);
    return candidate;
  }

  @override
  Future<void> removeEdge(String key) async {
    stored.removeWhere((edge) => edge.key == key);
  }

  @override
  Future<void> resetEdges() async {
    stored.clear();
  }
}

void main() {
  final graph = DependencyGraph.instance;
  late _FakeDigitalTwinService fakeService;

  setUp(() async {
    fakeService = _FakeDigitalTwinService();
    graph.debugService = fakeService;
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
    expect(fakeService.stored.single.reason, 'Docker host is powered by the UPS.');
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
    // Rejected client-side before ever reaching the backend.
    expect(fakeService.stored, hasLength(1));
  });

  test('multiple dependency roots deduplicate downstream nodes', () {
    final impacts = graph.downstreamForMany(['synology', 'hyper_backup']);
    final ids = impacts.map((item) => item.node.id).toList();

    expect(ids.where((id) => id == 'backup_analytics'), hasLength(1));
  });

  test('adding the same edge twice is idempotent, not a duplicate', () async {
    await graph.addCustomEdge(dependentId: 'unifi', dependencyId: 'ups');
    await graph.addCustomEdge(dependentId: 'unifi', dependencyId: 'ups');

    expect(graph.customEdges, hasLength(1));
  });

  test('removing a custom edge removes its downstream impact', () async {
    await graph.addCustomEdge(dependentId: 'unifi', dependencyId: 'ups');
    expect(graph.downstreamImpacts('ups').map((item) => item.node.id), contains('unifi'));

    await graph.removeCustomEdge('unifi>ups');
    expect(graph.downstreamImpacts('ups'), isEmpty);
  });

  test('an unreachable topology backend degrades to built-in edges only', () async {
    await graph.addCustomEdge(dependentId: 'unifi', dependencyId: 'ups');
    expect(graph.customEdges, isNotEmpty);

    // Swapping the service forces the next load() to refetch -- from a
    // backend that now throws on every call.
    graph.debugService = _FailingDigitalTwinService();
    await graph.load();

    expect(graph.downstreamImpacts('ups'), isEmpty);
    expect(graph.customEdges, isEmpty);

    // Restore a working service so tearDown's resetCustomEdges() succeeds.
    graph.debugService = fakeService;
  });
}

class _FailingDigitalTwinService implements DigitalTwinService {
  @override
  Future<List<DependencyEdge>> fetchCustomEdges() async => throw const DigitalTwinServiceException('unreachable');

  @override
  Future<DependencyEdge> addEdge({required String dependentId, required String dependencyId, String? reason}) =>
      throw UnimplementedError();

  @override
  Future<void> removeEdge(String key) => throw UnimplementedError();

  @override
  Future<void> resetEdges() => throw UnimplementedError();
}
