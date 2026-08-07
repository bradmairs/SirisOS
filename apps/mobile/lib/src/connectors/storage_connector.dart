import '../core/notification_policy.dart';
import '../core/siris_connector.dart';
import '../core/siris_event_bus.dart';
import '../models/storage_snapshot.dart';
import '../services/storage_service.dart';

class StorageConnector extends SirisConnector {
  StorageConnector({StorageService? service}) : _service = service ?? StorageService();

  final StorageService _service;
  StorageSnapshot? _latest;

  StorageSnapshot? get latest => _latest;

  static const _warningPolicy = NotificationPolicyRule(
    id: 'storage.capacity.warning',
    moduleId: 'homelab',
    title: 'Storage capacity high',
    message: 'At least one monitored filesystem is above 85% used.',
    severity: NotificationPolicySeverity.warning,
    activeAfter: Duration(minutes: 2),
    scorePenalty: 4,
  );

  static const _criticalPolicy = NotificationPolicyRule(
    id: 'storage.capacity.critical',
    moduleId: 'homelab',
    title: 'Storage capacity critical',
    message: 'At least one monitored filesystem is above 95% used.',
    severity: NotificationPolicySeverity.critical,
    activeAfter: Duration(minutes: 2),
    scorePenalty: 10,
  );

  @override
  String get id => 'storage';

  @override
  String get label => 'Storage';

  @override
  Duration get refreshInterval => const Duration(seconds: 30);

  @override
  Future<void> connect() async {
    final snapshot = await _service.fetchSnapshot();
    _latest = snapshot;
    _evaluatePolicies(snapshot);
    if (!snapshot.available) {
      throw StorageServiceException(snapshot.error ?? 'Storage monitoring unavailable.');
    }
  }

  @override
  Future<void> refresh() async {
    final previous = _latest;
    final next = await _service.fetchSnapshot();
    _latest = next;
    _evaluatePolicies(next);
    if (!next.available) {
      throw StorageServiceException(next.error ?? 'Storage monitoring unavailable.');
    }

    if (previous == null ||
        previous.volumes.length != next.volumes.length ||
        previous.highestUsedPercent != next.highestUsedPercent ||
        previous.totalBytes != next.totalBytes) {
      SirisEventBus.instance.publish(
        ModuleDataChanged(moduleId: 'homelab', reason: 'storage_state_changed'),
      );
    }
  }

  @override
  Future<void> disconnect() async {
    NotificationPolicyEngine.instance.evaluate(_warningPolicy, condition: false);
    NotificationPolicyEngine.instance.evaluate(_criticalPolicy, condition: false);
  }

  void _evaluatePolicies(StorageSnapshot snapshot) {
    final highest = snapshot.highestUsedPercent ?? 0;
    NotificationPolicyEngine.instance.evaluate(
      _warningPolicy,
      condition: snapshot.available && highest >= 85 && highest < 95,
    );
    NotificationPolicyEngine.instance.evaluate(
      _criticalPolicy,
      condition: snapshot.available && highest >= 95,
    );
  }
}
