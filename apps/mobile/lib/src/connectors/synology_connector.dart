import '../core/notification_policy.dart';
import '../core/siris_connector.dart';
import '../core/siris_event_bus.dart';
import '../models/synology_snapshot.dart';
import '../services/synology_service.dart';

class SynologyConnector extends SirisConnector {
  SynologyConnector({SynologyService? service}) : _service = service ?? SynologyService();
  final SynologyService _service;
  SynologySnapshot? _latest;

  static const _unavailablePolicy = NotificationPolicyRule(
    id: 'synology.unavailable',
    moduleId: 'homelab',
    title: 'Synology unavailable',
    message: 'The Synology NAS has been unreachable for several minutes.',
    severity: NotificationPolicySeverity.warning,
    activeAfter: Duration(minutes: 2),
    escalateAfter: Duration(minutes: 10),
    escalatedSeverity: NotificationPolicySeverity.critical,
    scorePenalty: 8,
  );

  static const _storagePolicy = NotificationPolicyRule(
    id: 'synology.storage.issue',
    moduleId: 'homelab',
    title: 'Synology storage needs attention',
    message: 'A Synology disk or volume is reporting an unhealthy state.',
    severity: NotificationPolicySeverity.critical,
    activeAfter: Duration(minutes: 2),
    scorePenalty: 12,
  );

  static const _backupFailurePolicy = NotificationPolicyRule(
    id: 'synology.hyper_backup.failed',
    moduleId: 'homelab',
    title: 'Hyper Backup needs attention',
    message: 'One or more Synology Hyper Backup tasks last reported a failure.',
    severity: NotificationPolicySeverity.critical,
    activeAfter: Duration.zero,
    scorePenalty: 12,
  );

  @override
  String get id => 'synology';
  @override
  String get label => 'Synology';
  @override
  Duration get refreshInterval => const Duration(seconds: 30);

  @override
  Future<void> connect() async {
    final snapshot = await _service.fetchSnapshot();
    _latest = snapshot;
    _evaluate(snapshot);
    if (!snapshot.configured) {
      throw const SirisConnectorDisabledException('Synology is not configured.');
    }
    if (!snapshot.available) {
      throw SynologyServiceException(snapshot.error ?? 'Synology is unavailable.');
    }
  }

  @override
  Future<void> refresh() async {
    final previous = _latest;
    final next = await _service.fetchSnapshot();
    _latest = next;
    _evaluate(next);
    if (!next.configured) {
      throw const SirisConnectorDisabledException('Synology is not configured.');
    }
    if (!next.available) {
      throw SynologyServiceException(next.error ?? 'Synology is unavailable.');
    }
    if (previous == null ||
        previous.available != next.available ||
        previous.unhealthyVolumes != next.unhealthyVolumes ||
        previous.unhealthyDisks != next.unhealthyDisks ||
        previous.highestUsedPercent != next.highestUsedPercent ||
        previous.runningBackupTasks != next.runningBackupTasks ||
        previous.failedBackupTasks != next.failedBackupTasks ||
        previous.latestBackupFinishAt != next.latestBackupFinishAt) {
      SirisEventBus.instance.publish(
        ModuleDataChanged(moduleId: 'homelab', reason: 'synology_state_changed'),
      );
    }
  }

  @override
  Future<void> disconnect() async {
    NotificationPolicyEngine.instance.evaluate(_unavailablePolicy, condition: false);
    NotificationPolicyEngine.instance.evaluate(_storagePolicy, condition: false);
    NotificationPolicyEngine.instance.evaluate(_backupFailurePolicy, condition: false);
  }

  void _evaluate(SynologySnapshot snapshot) {
    NotificationPolicyEngine.instance.evaluate(
      _unavailablePolicy,
      condition: snapshot.configured && !snapshot.available,
    );
    NotificationPolicyEngine.instance.evaluate(
      _storagePolicy,
      condition: snapshot.available &&
          (snapshot.unhealthyVolumes > 0 || snapshot.unhealthyDisks > 0),
    );
    NotificationPolicyEngine.instance.evaluate(
      _backupFailurePolicy,
      condition: snapshot.available && snapshot.failedBackupTasks > 0,
    );
  }
}
