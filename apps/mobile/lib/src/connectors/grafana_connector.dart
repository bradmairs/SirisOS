import '../core/notification_policy.dart';
import '../core/siris_connector.dart';
import '../core/siris_event_bus.dart';
import '../models/grafana_snapshot.dart';
import '../services/grafana_service.dart';

class GrafanaConnector extends SirisConnector {
  GrafanaConnector({GrafanaService? service}) : _service = service ?? GrafanaService();

  final GrafanaService _service;
  GrafanaSnapshot? _latest;

  GrafanaSnapshot? get latest => _latest;

  static const _unavailablePolicy = NotificationPolicyRule(
    id: 'grafana.unavailable',
    moduleId: 'homelab',
    title: 'Grafana unavailable',
    message: 'Grafana has been unreachable for several minutes.',
    severity: NotificationPolicySeverity.warning,
    activeAfter: Duration(minutes: 2),
    escalateAfter: Duration(minutes: 10),
    escalatedSeverity: NotificationPolicySeverity.critical,
    scorePenalty: 4,
  );

  @override
  String get id => 'grafana';

  @override
  String get label => 'Grafana';

  @override
  Duration get refreshInterval => const Duration(seconds: 30);

  @override
  Future<void> connect() async {
    final snapshot = await _service.fetchSnapshot();
    _latest = snapshot;
    _evaluatePolicy(snapshot);
    if (!snapshot.configured) {
      throw const SirisConnectorDisabledException('Grafana is not configured.');
    }
    if (!snapshot.available) {
      throw GrafanaServiceException(snapshot.error ?? 'Grafana is unavailable.');
    }
  }

  @override
  Future<void> refresh() async {
    final previous = _latest;
    final next = await _service.fetchSnapshot();
    _latest = next;
    _evaluatePolicy(next);
    if (!next.configured) {
      throw const SirisConnectorDisabledException('Grafana is not configured.');
    }
    if (!next.available) {
      throw GrafanaServiceException(next.error ?? 'Grafana is unavailable.');
    }
    if (previous == null ||
        previous.available != next.available ||
        previous.dashboardCount != next.dashboardCount ||
        previous.version != next.version) {
      SirisEventBus.instance.publish(
        ModuleDataChanged(moduleId: 'homelab', reason: 'grafana_state_changed'),
      );
    }
  }

  @override
  Future<void> disconnect() async {
    NotificationPolicyEngine.instance.evaluate(_unavailablePolicy, condition: false);
  }

  void _evaluatePolicy(GrafanaSnapshot snapshot) {
    NotificationPolicyEngine.instance.evaluate(
      _unavailablePolicy,
      condition: snapshot.configured && !snapshot.available,
    );
  }
}
