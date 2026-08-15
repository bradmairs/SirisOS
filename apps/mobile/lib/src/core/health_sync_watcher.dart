import '../services/health_service.dart';
import 'siris_event_bus.dart';
import 'siris_scheduler.dart';

/// Health Auto Export syncs land out-of-band, straight from the iPhone
/// automation to the backend -- no currently-open Flutter session is
/// involved in that request, so there's nothing to hook a bus-publish onto
/// client-side the way gym_service.dart does after its own POST. Instead
/// this polls the cheap GET /health/status endpoint periodically and only
/// publishes ModuleDataChanged when last_sync/records_received actually
/// change, mirroring SirisIntegrationManager's poll-then-publish pattern for
/// its own connectors. The first poll only establishes a baseline silently
/// -- it must never fire a refresh purely because the app just started.
class HealthSyncWatcher {
  HealthSyncWatcher._();

  static final HealthSyncWatcher instance = HealthSyncWatcher._();
  static const jobId = 'health.ingest-watch';

  final HealthService _service = HealthService();
  DateTime? _lastSeenSync;
  int? _lastSeenRecordsReceived;

  void start() {
    SirisScheduler.instance.register(
      SirisScheduledJob(
        id: jobId,
        interval: const Duration(minutes: 5),
        run: _poll,
      ),
    );
  }

  void stop() => SirisScheduler.instance.unregister(jobId);

  Future<void> _poll() async {
    try {
      final status = await _service.fetchIngestStatus();
      final hasBaseline = _lastSeenSync != null || _lastSeenRecordsReceived != null;
      final changed = hasBaseline &&
          (status.lastSync != _lastSeenSync ||
              status.recordsReceived != _lastSeenRecordsReceived);
      _lastSeenSync = status.lastSync;
      _lastSeenRecordsReceived = status.recordsReceived;
      if (changed) {
        SirisEventBus.instance.publish(
          ModuleDataChanged(moduleId: 'health', reason: 'ingest_sync'),
        );
      }
    } catch (_) {
      // Best-effort background poll -- a failed check just tries again next
      // interval rather than surfacing an error anywhere.
    }
  }
}
