import 'package:flutter_test/flutter_test.dart';
import 'package:siris_os/src/connectors/knowledge_connector.dart';
import 'package:siris_os/src/services/knowledge_service.dart';

class _FakeKnowledgeService extends KnowledgeService {
  _FakeKnowledgeService(this.value);

  final KnowledgeOverview value;

  @override
  Future<KnowledgeOverview> overview() async => value;
}

KnowledgeOverview _overview(bool available) => KnowledgeOverview(
      available: available,
      vaultName: 'Test Vault',
      noteCount: 2,
      recent: const [],
      daily: const [],
    );

void main() {
  test('Knowledge connector reports a mounted vault as healthy', () async {
    final connector = KnowledgeConnector(
      service: _FakeKnowledgeService(_overview(true)),
    );

    expect(connector.id, 'knowledge');
    expect(connector.label, 'Knowledge Vault');
    await connector.connect();
    await connector.refresh();
  });

  test('Knowledge connector fails health check when vault is unavailable', () async {
    final connector = KnowledgeConnector(
      service: _FakeKnowledgeService(_overview(false)),
    );

    expect(connector.connect(), throwsStateError);
  });
}
