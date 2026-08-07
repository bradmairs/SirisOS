import 'dart:async';

enum SirisConnectorState {
  disconnected,
  connecting,
  healthy,
  degraded,
  failed,
  disabled,
}

class SirisConnectorHealth {
  const SirisConnectorHealth({
    required this.state,
    required this.message,
    this.lastAttemptAt,
    this.lastSuccessAt,
    this.consecutiveFailures = 0,
  });

  final SirisConnectorState state;
  final String message;
  final DateTime? lastAttemptAt;
  final DateTime? lastSuccessAt;
  final int consecutiveFailures;

  bool get isHealthy => state == SirisConnectorState.healthy;
  bool get hasError =>
      state == SirisConnectorState.degraded || state == SirisConnectorState.failed;

  SirisConnectorHealth copyWith({
    SirisConnectorState? state,
    String? message,
    DateTime? lastAttemptAt,
    DateTime? lastSuccessAt,
    int? consecutiveFailures,
  }) =>
      SirisConnectorHealth(
        state: state ?? this.state,
        message: message ?? this.message,
        lastAttemptAt: lastAttemptAt ?? this.lastAttemptAt,
        lastSuccessAt: lastSuccessAt ?? this.lastSuccessAt,
        consecutiveFailures: consecutiveFailures ?? this.consecutiveFailures,
      );
}

class SirisConnectorDisabledException implements Exception {
  const SirisConnectorDisabledException(this.message);

  final String message;

  @override
  String toString() => message;
}

abstract class SirisConnector {
  String get id;
  String get label;
  Duration get refreshInterval;

  bool get enabled => true;

  Future<void> connect();
  Future<void> refresh();
  Future<void> disconnect() async {}
}
