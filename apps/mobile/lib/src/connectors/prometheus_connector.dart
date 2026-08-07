import '../core/notification_policy.dart';
import '../core/siris_connector.dart';
import '../core/siris_event_bus.dart';
import '../models/prometheus_snapshot.dart';
import '../services/prometheus_service.dart';

class PrometheusConnector extends SirisConnector {
  PrometheusConnector({PrometheusService? service})
      : _service = service ?? PrometheusService();

  final PrometheusService _service;
  PrometheusSnapshot? _latest;

  PrometheusSnapshot? get latest => _latest;

  static const _unavailablePolicy = NotificationPolicyRule(
    id: 'prometheus.unavailable',
    moduleId: 'homelab',
    title: 'Prometheus unavailable',
    message: 'Prometheus has been unreachable for several minutes.',
    severity: NotificationPolicySeverity.warning,
    activeAfter: Duration(minutes: 2),
    escalateAfter: Duration(minutes: 10),
    escalatedSeverity: NotificationPolicySeverity.critical,
    scorePenalty: 6,
  );

  static const _targetsPolicy = NotificationPolicyRule(
    id: 'prometheus.targets_down',
    moduleId: 'homelab',
    title: 'Prometheus targets down',
    message: 'One or more Prometheus scrape targets are currently down.',
    severity: NotificationPolicySeverity.warning,
    activeAfter: Duration(minutes: 2),
    scorePenalty: 4,
  );

  @override
  String get id => 'prometheus';

  @override
  String get label => 'Prometheus';

  @override
  Duration get refreshInterval => const Duration(seconds: 15);

  @override
  Future<void> connect() async {
    final snapshot = await _service.fetchSnapshot();
    _latest = snapshot;
    _evaluatePolicies(snapshot);
    if (!snapshot.configured) {
      throw const SirisConnectorDisabledException('Prometheus is not configured.');
    }
    if (!snapshot.available) {
      throw PrometheusServiceException(snapshot.error ?? 'Prometheus is unavailable.');
    }
  }

  @override
  Future<void> refresh() async {
    final previous = _latest;
    final next = await _service.fetchSnapshot();
    _latest = next;
    _evaluatePolicies(next);

    if (!next.configured) {
      throw const SirisConnectorDisabledException('Prometheus is not configured.');
    }
    if (!next.available) {
      throw PrometheusServiceException(next.error ?? 'Prometheus is unavailable.');
    }

    if (previous == null ||
        previous.available != next.available ||
        previous.healthyTargets != next.healthyTargets ||
        previous.unhealthyTargets != next.unhealthyTargets ||
        previous.totalTargets != next.totalTargets) {
      SirisEventBus.instance.publish(
        ModuleDataChanged(moduleId: 'homelab', reason: 'prometheus_state_changed'),
      );
    }
  }

  @override
  Future<void> disconnect() async {
    NotificationPolicyEngine.instance.evaluate(_unavailablePolicy, condition: false);
    NotificationPolicyEngine.instance.evaluate(_targetsPolicy, condition: false);
  }

  void _evaluatePolicies(PrometheusSnapshot snapshot) {
    NotificationPolicyEngine.instance.evaluate(
      _unavailablePolicy,
      condition: snapshot.configured && !snapshot.available,
    );
    NotificationPolicyEngine.instance.evaluate(
      _targetsPolicy,
      condition: snapshot.available && snapshot.unhealthyTargets > 0,
    );
  }
}
