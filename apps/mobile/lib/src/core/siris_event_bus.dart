import 'dart:async';

/// Base event shared by SirisOS modules.
abstract class SirisEvent {
  SirisEvent({DateTime? occurredAt}) : occurredAt = occurredAt ?? DateTime.now();

  final DateTime occurredAt;
}

class MissionControlRefreshed extends SirisEvent {
  MissionControlRefreshed({required this.source, super.occurredAt});

  final String source;
}

class ModuleDataChanged extends SirisEvent {
  ModuleDataChanged({required this.moduleId, this.reason, super.occurredAt});

  final String moduleId;
  final String? reason;
}

class SirisEventBus {
  SirisEventBus._();

  static final SirisEventBus instance = SirisEventBus._();

  final StreamController<SirisEvent> _controller =
      StreamController<SirisEvent>.broadcast(sync: true);

  Stream<SirisEvent> get events => _controller.stream;

  Stream<T> on<T extends SirisEvent>() => events.where((event) => event is T).cast<T>();

  void publish(SirisEvent event) {
    if (!_controller.isClosed) _controller.add(event);
  }

  Future<void> dispose() => _controller.close();
}
