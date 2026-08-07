import '../core/notification_policy.dart';
import '../core/siris_connector.dart';
import '../core/siris_event_bus.dart';
import '../models/docker_summary.dart';
import '../services/homelab_service.dart';

class DockerConnector extends SirisConnector {
  DockerConnector({HomelabService? service})
      : _service = service ?? HomelabService();

  final HomelabService _service;
  DockerSummary? _latest;

  static const _unhealthyPolicy = NotificationPolicyRule(
    id: 'docker.unhealthy',
    moduleId: 'homelab',
    title: 'Docker container unhealthy',
    message: 'One or more Docker containers have remained unhealthy.',
    severity: NotificationPolicySeverity.warning,
    activeAfter: Duration(minutes: 2),
    escalateAfter: Duration(minutes: 5),
    escalatedSeverity: NotificationPolicySeverity.critical,
    scorePenalty: 12,
  );

  static const _stoppedPolicy = NotificationPolicyRule(
    id: 'docker.stopped',
    moduleId: 'homelab',
    title: 'Docker container stopped',
    message: 'One or more Docker containers are not running.',
    severity: NotificationPolicySeverity.warning,
    activeAfter: Duration(minutes: 2),
    escalateAfter: Duration(minutes: 10),
    escalatedSeverity: NotificationPolicySeverity.critical,
    scorePenalty: 8,
  );

  static const _updatesPolicy = NotificationPolicyRule(
    id: 'docker.updates',
    moduleId: 'homelab',
    title: 'Docker image updates available',
    message: 'One or more Docker containers have image updates available.',
    severity: NotificationPolicySeverity.warning,
    scorePenalty: 2,
  );

  DockerSummary? get latest => _latest;

  @override
  String get id => 'docker';

  @override
  String get label => 'Docker';

  @override
  Duration get refreshInterval => const Duration(seconds: 30);

  @override
  Future<void> connect() async {
    final summary = await _service.fetchDockerSummary();
    if (!summary.available) {
      throw HomelabServiceException(
        summary.error ?? 'Docker monitoring is unavailable.',
      );
    }
    _latest = summary;
    _evaluatePolicies(summary);
  }

  @override
  Future<void> refresh() async {
    final previous = _latest;
    final next = await _service.fetchDockerSummary();
    if (!next.available) {
      throw HomelabServiceException(
        next.error ?? 'Docker monitoring is unavailable.',
      );
    }
    _latest = next;
    _evaluatePolicies(next);

    if (_hasMeaningfulChange(previous, next)) {
      SirisEventBus.instance.publish(
        ModuleDataChanged(
          moduleId: 'homelab',
          reason: 'docker_state_changed',
        ),
      );
    }
  }

  @override
  Future<void> disconnect() async {
    NotificationPolicyEngine.instance.clearModule('homelab');
  }

  void _evaluatePolicies(DockerSummary summary) {
    final policies = NotificationPolicyEngine.instance;
    policies.evaluate(_unhealthyPolicy, condition: summary.unhealthy > 0);
    policies.evaluate(_stoppedPolicy, condition: summary.stopped > 0);
    policies.evaluate(
      _updatesPolicy,
      condition: summary.updatesAvailable > 0,
    );
  }

  bool _hasMeaningfulChange(DockerSummary? previous, DockerSummary next) {
    if (previous == null) return true;
    if (previous.running != next.running ||
        previous.stopped != next.stopped ||
        previous.unhealthy != next.unhealthy ||
        previous.updatesAvailable != next.updatesAvailable) {
      return true;
    }

    final before = {
      for (final item in previous.containers)
        item.name: '${item.state}|${item.health}|${item.updateAvailable}',
    };
    final after = {
      for (final item in next.containers)
        item.name: '${item.state}|${item.health}|${item.updateAvailable}',
    };
    return before.length != after.length ||
        before.entries.any((entry) => after[entry.key] != entry.value);
  }
}
