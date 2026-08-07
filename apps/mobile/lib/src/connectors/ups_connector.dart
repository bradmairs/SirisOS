import '../core/notification_policy.dart';
import '../core/siris_connector.dart';
import '../core/siris_event_bus.dart';
import '../models/ups_snapshot.dart';
import '../services/ups_service.dart';

class UpsConnector extends SirisConnector {
  UpsConnector({UpsService? service}) : _service = service ?? UpsService();

  final UpsService _service;
  UpsSnapshot? _latest;

  static const _unavailablePolicy = NotificationPolicyRule(
    id: 'ups.unavailable',
    moduleId: 'homelab',
    title: 'UPS monitoring unavailable',
    message: 'The configured NUT server cannot be reached.',
    severity: NotificationPolicySeverity.warning,
    activeAfter: Duration(minutes: 2),
    escalateAfter: Duration(minutes: 10),
    escalatedSeverity: NotificationPolicySeverity.critical,
    scorePenalty: 6,
  );

  static const _onBatteryPolicy = NotificationPolicyRule(
    id: 'ups.on_battery',
    moduleId: 'homelab',
    title: 'UPS running on battery',
    message: 'Utility power is unavailable and the UPS is supplying battery power.',
    severity: NotificationPolicySeverity.warning,
    activeAfter: Duration.zero,
    scorePenalty: 6,
  );

  static const _lowBatteryPolicy = NotificationPolicyRule(
    id: 'ups.low_battery',
    moduleId: 'homelab',
    title: 'UPS battery critically low',
    message: 'The UPS reports a low-battery condition. Protected systems may need to shut down soon.',
    severity: NotificationPolicySeverity.critical,
    activeAfter: Duration.zero,
    scorePenalty: 15,
  );

  @override
  String get id => 'ups';

  @override
  String get label => 'UPS';

  @override
  Duration get refreshInterval => const Duration(seconds: 15);

  @override
  Future<void> connect() async {
    final snapshot = await _service.fetchSnapshot();
    _latest = snapshot;
    _evaluatePolicies(snapshot);
    if (!snapshot.configured) {
      throw const SirisConnectorDisabledException('UPS is not configured.');
    }
    if (!snapshot.available) {
      throw UpsServiceException(snapshot.error ?? 'UPS monitoring unavailable.');
    }
  }

  @override
  Future<void> refresh() async {
    final previous = _latest;
    final next = await _service.fetchSnapshot();
    _latest = next;
    _evaluatePolicies(next);
    if (!next.configured) {
      throw const SirisConnectorDisabledException('UPS is not configured.');
    }
    if (!next.available) {
      throw UpsServiceException(next.error ?? 'UPS monitoring unavailable.');
    }

    if (previous == null ||
        previous.status != next.status ||
        previous.onBattery != next.onBattery ||
        previous.lowBattery != next.lowBattery ||
        previous.batteryChargePercent != next.batteryChargePercent ||
        previous.batteryRuntimeSeconds != next.batteryRuntimeSeconds) {
      SirisEventBus.instance.publish(
        ModuleDataChanged(moduleId: 'homelab', reason: 'ups_state_changed'),
      );
    }
  }

  @override
  Future<void> disconnect() async {
    NotificationPolicyEngine.instance.evaluate(_unavailablePolicy, condition: false);
    NotificationPolicyEngine.instance.evaluate(_onBatteryPolicy, condition: false);
    NotificationPolicyEngine.instance.evaluate(_lowBatteryPolicy, condition: false);
  }

  void _evaluatePolicies(UpsSnapshot snapshot) {
    NotificationPolicyEngine.instance.evaluate(
      _unavailablePolicy,
      condition: snapshot.configured && !snapshot.available,
    );
    NotificationPolicyEngine.instance.evaluate(
      _onBatteryPolicy,
      condition: snapshot.available && snapshot.onBattery && !snapshot.lowBattery,
    );
    NotificationPolicyEngine.instance.evaluate(
      _lowBatteryPolicy,
      condition: snapshot.available && snapshot.lowBattery,
    );
  }
}
