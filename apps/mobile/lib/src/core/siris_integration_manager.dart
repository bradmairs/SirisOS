import 'dart:async';

import 'siris_connector.dart';
import 'siris_event_bus.dart';
import 'siris_scheduler.dart';

class IntegrationHealthChanged extends SirisEvent {
  IntegrationHealthChanged({
    required this.connectorId,
    required this.health,
    super.occurredAt,
  });

  final String connectorId;
  final SirisConnectorHealth health;
}

class IntegrationRefreshed extends SirisEvent {
  IntegrationRefreshed({
    required this.connectorId,
    required this.duration,
    super.occurredAt,
  });

  final String connectorId;
  final Duration duration;
}

class SirisIntegrationManager {
  SirisIntegrationManager._();

  static final SirisIntegrationManager instance = SirisIntegrationManager._();

  final Map<String, SirisConnector> _connectors = {};
  final Map<String, SirisConnectorHealth> _health = {};

  List<SirisConnector> get connectors =>
      List<SirisConnector>.unmodifiable(_connectors.values);

  Map<String, SirisConnectorHealth> get health =>
      Map<String, SirisConnectorHealth>.unmodifiable(_health);

  SirisConnectorHealth? healthFor(String connectorId) => _health[connectorId];

  Future<void> register(SirisConnector connector) async {
    await unregister(connector.id);
    _connectors[connector.id] = connector;

    if (!connector.enabled) {
      _setHealth(
        connector.id,
        const SirisConnectorHealth(
          state: SirisConnectorState.disabled,
          message: 'Integration disabled',
        ),
      );
      return;
    }

    _setHealth(
      connector.id,
      SirisConnectorHealth(
        state: SirisConnectorState.connecting,
        message: 'Connecting',
        lastAttemptAt: DateTime.now(),
      ),
    );

    try {
      await connector.connect();
      _setHealth(
        connector.id,
        SirisConnectorHealth(
          state: SirisConnectorState.healthy,
          message: 'Connected',
          lastAttemptAt: DateTime.now(),
          lastSuccessAt: DateTime.now(),
        ),
      );
      await refresh(connector.id);
      SirisScheduler.instance.register(
        SirisScheduledJob(
          id: _jobId(connector.id),
          interval: connector.refreshInterval,
          run: () => refresh(connector.id),
        ),
      );
    } catch (error) {
      _recordFailure(connector.id, error);
    }
  }

  Future<void> refresh(String connectorId) async {
    final connector = _connectors[connectorId];
    if (connector == null || !connector.enabled) return;

    final previous = _health[connectorId];
    final attemptAt = DateTime.now();
    final stopwatch = Stopwatch()..start();

    try {
      await connector.refresh();
      stopwatch.stop();
      _setHealth(
        connectorId,
        SirisConnectorHealth(
          state: SirisConnectorState.healthy,
          message: 'Healthy',
          lastAttemptAt: attemptAt,
          lastSuccessAt: DateTime.now(),
        ),
      );
      SirisEventBus.instance.publish(
        IntegrationRefreshed(
          connectorId: connectorId,
          duration: stopwatch.elapsed,
        ),
      );
    } catch (error) {
      stopwatch.stop();
      _recordFailure(connectorId, error, previous: previous);
    }
  }

  Future<void> unregister(String connectorId) async {
    SirisScheduler.instance.unregister(_jobId(connectorId));
    final connector = _connectors.remove(connectorId);
    if (connector != null) {
      await connector.disconnect();
    }
    _health.remove(connectorId);
  }

  Future<void> dispose() async {
    final ids = _connectors.keys.toList(growable: false);
    for (final id in ids) {
      await unregister(id);
    }
  }

  void _recordFailure(
    String connectorId,
    Object error, {
    SirisConnectorHealth? previous,
  }) {
    final prior = previous ?? _health[connectorId];
    final failures = (prior?.consecutiveFailures ?? 0) + 1;
    _setHealth(
      connectorId,
      SirisConnectorHealth(
        state: failures >= 3
            ? SirisConnectorState.failed
            : SirisConnectorState.degraded,
        message: error.toString(),
        lastAttemptAt: DateTime.now(),
        lastSuccessAt: prior?.lastSuccessAt,
        consecutiveFailures: failures,
      ),
    );
  }

  void _setHealth(String connectorId, SirisConnectorHealth next) {
    _health[connectorId] = next;
    SirisEventBus.instance.publish(
      IntegrationHealthChanged(connectorId: connectorId, health: next),
    );
  }

  static String _jobId(String connectorId) => 'integration.$connectorId.refresh';
}
