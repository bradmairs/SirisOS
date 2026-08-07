import 'siris_event_bus.dart';

class MissionControlDiagnostics {
  int _eventCount = 0;
  String? _lastEvent;
  DateTime? _lastEventAt;
  DateTime? _lastRefreshAt;
  Duration? _lastRefreshDuration;

  int get eventCount => _eventCount;
  String? get lastEvent => _lastEvent;
  DateTime? get lastEventAt => _lastEventAt;
  DateTime? get lastRefreshAt => _lastRefreshAt;
  Duration? get lastRefreshDuration => _lastRefreshDuration;

  void recordEvent(SirisEvent event) {
    _eventCount += 1;
    _lastEvent = event.runtimeType.toString();
    _lastEventAt = event.occurredAt;
  }

  void recordRefresh(Duration duration) {
    _lastRefreshAt = DateTime.now();
    _lastRefreshDuration = duration;
  }
}
