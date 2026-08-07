import '../core/notification_policy.dart';
import '../core/siris_connector.dart';
import '../core/siris_event_bus.dart';
import '../models/home_assistant_snapshot.dart';
import '../services/home_assistant_service.dart';

class HomeAssistantConnector extends SirisConnector {
  HomeAssistantConnector({HomeAssistantService? service})
      : _service = service ?? HomeAssistantService();

  final HomeAssistantService _service;
  HomeAssistantSnapshot? _latest;

  HomeAssistantSnapshot? get latest => _latest;

  static const _unavailablePolicy = NotificationPolicyRule(
    id: 'home_assistant.unavailable',
    moduleId: 'homelab',
    title: 'Home Assistant unavailable',
    message: 'Home Assistant has been unreachable for several minutes.',
    severity: NotificationPolicySeverity.warning,
    activeAfter: Duration(minutes: 2),
    escalateAfter: Duration(minutes: 10),
    escalatedSeverity: NotificationPolicySeverity.critical,
    scorePenalty: 8,
  );

  static const _entityPolicy = NotificationPolicyRule(
    id: 'home_assistant.entities_unavailable',
    moduleId: 'homelab',
    title: 'Home Assistant entities unavailable',
    message: 'Multiple Home Assistant entities are unavailable or unknown.',
    severity: NotificationPolicySeverity.warning,
    activeAfter: Duration(minutes: 2),
    scorePenalty: 4,
  );

  @override
  String get id => 'home_assistant';

  @override
  String get label => 'Home Assistant';

  @override
  Duration get refreshInterval => const Duration(seconds: 30);

  @override
  Future<void> connect() async {
    final snapshot = await _service.fetchSnapshot();
    _latest = snapshot;
    _evaluatePolicies(snapshot);
    if (!snapshot.configured) {
      throw const SirisConnectorDisabledException(
        'Home Assistant is not configured.',
      );
    }
    if (!snapshot.available) {
      throw HomeAssistantServiceException(
        snapshot.error ?? 'Home Assistant is unavailable.',
      );
    }
  }

  @override
  Future<void> refresh() async {
    final previous = _latest;
    final next = await _service.fetchSnapshot();
    _latest = next;
    _evaluatePolicies(next);

    if (!next.configured) {
      throw const SirisConnectorDisabledException(
        'Home Assistant is not configured.',
      );
    }
    if (!next.available) {
      throw HomeAssistantServiceException(
        next.error ?? 'Home Assistant is unavailable.',
      );
    }

    if (_hasMeaningfulChange(previous, next)) {
      SirisEventBus.instance.publish(
        ModuleDataChanged(
          moduleId: 'homelab',
          reason: 'home_assistant_state_changed',
        ),
      );
    }
  }

  @override
  Future<void> disconnect() async {
    NotificationPolicyEngine.instance.evaluate(
      _unavailablePolicy,
      condition: false,
    );
    NotificationPolicyEngine.instance.evaluate(
      _entityPolicy,
      condition: false,
    );
  }

  void _evaluatePolicies(HomeAssistantSnapshot snapshot) {
    final configured = snapshot.configured;
    NotificationPolicyEngine.instance.evaluate(
      _unavailablePolicy,
      condition: configured && !snapshot.available,
    );
    NotificationPolicyEngine.instance.evaluate(
      _entityPolicy,
      condition: configured && snapshot.available && snapshot.unavailable >= 3,
    );
  }

  bool _hasMeaningfulChange(
    HomeAssistantSnapshot? previous,
    HomeAssistantSnapshot next,
  ) {
    if (previous == null) return true;
    if (previous.configured != next.configured ||
        previous.available != next.available ||
        previous.total != next.total ||
        previous.unavailable != next.unavailable) {
      return true;
    }

    final before = {
      for (final entity in previous.entities) entity.entityId: entity.state,
    };
    final after = {
      for (final entity in next.entities) entity.entityId: entity.state,
    };
    return before.length != after.length ||
        before.entries.any((entry) => after[entry.key] != entry.value);
  }
}
