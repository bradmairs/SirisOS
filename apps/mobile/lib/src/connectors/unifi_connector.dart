import '../core/notification_policy.dart';
import '../core/siris_connector.dart';
import '../core/siris_event_bus.dart';
import '../models/unifi_snapshot.dart';
import '../services/unifi_service.dart';

class UniFiConnector extends SirisConnector {
  UniFiConnector({UniFiService? service}) : _service = service ?? UniFiService();

  final UniFiService _service;
  UniFiSnapshot? _latest;

  UniFiSnapshot? get latest => _latest;

  static const _unavailablePolicy = NotificationPolicyRule(
    id: 'unifi.unavailable',
    moduleId: 'homelab',
    title: 'UniFi unavailable',
    message: 'The UniFi Network controller has been unreachable for several minutes.',
    severity: NotificationPolicySeverity.warning,
    activeAfter: Duration(minutes: 2),
    escalateAfter: Duration(minutes: 10),
    escalatedSeverity: NotificationPolicySeverity.critical,
    scorePenalty: 6,
  );

  static const _offlineDevicesPolicy = NotificationPolicyRule(
    id: 'unifi.devices_offline',
    moduleId: 'homelab',
    title: 'UniFi devices offline',
    message: 'One or more adopted UniFi devices are currently offline.',
    severity: NotificationPolicySeverity.warning,
    activeAfter: Duration(minutes: 2),
    escalateAfter: Duration(minutes: 10),
    escalatedSeverity: NotificationPolicySeverity.critical,
    scorePenalty: 5,
  );

  @override
  String get id => 'unifi';

  @override
  String get label => 'UniFi';

  @override
  Duration get refreshInterval => const Duration(seconds: 30);

  @override
  Future<void> connect() async {
    final snapshot = await _service.fetchSnapshot();
    _latest = snapshot;
    _evaluatePolicies(snapshot);
    if (!snapshot.configured) {
      throw const SirisConnectorDisabledException('UniFi is not configured.');
    }
    if (!snapshot.available) {
      throw UniFiServiceException(snapshot.error ?? 'UniFi is unavailable.');
    }
  }

  @override
  Future<void> refresh() async {
    final previous = _latest;
    final next = await _service.fetchSnapshot();
    _latest = next;
    _evaluatePolicies(next);

    if (!next.configured) {
      throw const SirisConnectorDisabledException('UniFi is not configured.');
    }
    if (!next.available) {
      throw UniFiServiceException(next.error ?? 'UniFi is unavailable.');
    }

    if (previous == null ||
        previous.available != next.available ||
        previous.onlineDevices != next.onlineDevices ||
        previous.offlineDevices != next.offlineDevices ||
        previous.connectedClients != next.connectedClients ||
        previous.wanInterfaces != next.wanInterfaces) {
      SirisEventBus.instance.publish(
        ModuleDataChanged(moduleId: 'homelab', reason: 'unifi_state_changed'),
      );
    }
  }

  @override
  Future<void> disconnect() async {
    NotificationPolicyEngine.instance.evaluate(_unavailablePolicy, condition: false);
    NotificationPolicyEngine.instance.evaluate(_offlineDevicesPolicy, condition: false);
  }

  void _evaluatePolicies(UniFiSnapshot snapshot) {
    NotificationPolicyEngine.instance.evaluate(
      _unavailablePolicy,
      condition: snapshot.configured && !snapshot.available,
    );
    NotificationPolicyEngine.instance.evaluate(
      _offlineDevicesPolicy,
      condition: snapshot.available && snapshot.offlineDevices > 0,
    );
  }
}
