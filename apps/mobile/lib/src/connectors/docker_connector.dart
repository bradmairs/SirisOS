import '../core/siris_connector.dart';
import '../core/siris_event_bus.dart';
import '../models/docker_summary.dart';
import '../services/homelab_service.dart';

class DockerConnector extends SirisConnector {
  DockerConnector({HomelabService? service})
      : _service = service ?? HomelabService();

  final HomelabService _service;
  DockerSummary? _latest;

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

    if (_hasMeaningfulChange(previous, next)) {
      SirisEventBus.instance.publish(
        ModuleDataChanged(
          moduleId: 'homelab',
          reason: 'docker_state_changed',
        ),
      );
    }
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
