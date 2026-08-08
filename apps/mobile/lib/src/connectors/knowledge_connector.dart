import '../core/siris_connector.dart';
import '../services/knowledge_service.dart';

class KnowledgeConnector implements SirisConnector {
  KnowledgeConnector({KnowledgeService? service}) : _service = service ?? KnowledgeService();

  final KnowledgeService _service;

  @override
  String get id => 'knowledge';

  @override
  String get label => 'Knowledge Vault';

  @override
  Duration get refreshInterval => const Duration(minutes: 5);

  @override
  Future<void> connect() async {
    await _checkVault();
  }

  @override
  Future<void> refresh() async {
    await _checkVault();
  }

  Future<void> _checkVault() async {
    final overview = await _service.overview();
    if (!overview.available) {
      throw StateError('Knowledge vault is unavailable.');
    }
  }
}
