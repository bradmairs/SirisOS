import 'siris_connector.dart';
import 'siris_integration_manager.dart';

enum SirisCapabilityKind { read, control, execute, navigate }

enum SirisCapabilityRisk { none, low, medium, high }

class SirisCapability {
  const SirisCapability({
    required this.id,
    required this.title,
    required this.description,
    required this.providerId,
    required this.kind,
    required this.risk,
    this.requiresConfirmation = false,
  });

  final String id;
  final String title;
  final String description;
  final String providerId;
  final SirisCapabilityKind kind;
  final SirisCapabilityRisk risk;
  final bool requiresConfirmation;
}

class SirisCapabilityStatus {
  const SirisCapabilityStatus({
    required this.capability,
    required this.available,
    required this.reason,
  });

  final SirisCapability capability;
  final bool available;
  final String reason;
}

/// Declarative registry answering "what can SirisOS do?" independently of
/// the future Action Framework that will execute those capabilities.
class SirisCapabilityRegistry {
  SirisCapabilityRegistry._();

  static final SirisCapabilityRegistry instance = SirisCapabilityRegistry._();

  static const List<SirisCapability> _capabilities = [
    SirisCapability(
      id: 'docker.observe',
      title: 'Observe Docker',
      description: 'Read container, host, health and update state.',
      providerId: 'docker',
      kind: SirisCapabilityKind.read,
      risk: SirisCapabilityRisk.none,
    ),
    SirisCapability(
      id: 'docker.restart',
      title: 'Restart Docker container',
      description: 'Restart a selected Docker container through the Docker connector.',
      providerId: 'docker',
      kind: SirisCapabilityKind.control,
      risk: SirisCapabilityRisk.medium,
      requiresConfirmation: true,
    ),
    SirisCapability(
      id: 'home_assistant.observe',
      title: 'Observe Home Assistant',
      description: 'Read cached Home Assistant entity state.',
      providerId: 'home_assistant',
      kind: SirisCapabilityKind.read,
      risk: SirisCapabilityRisk.none,
    ),
    SirisCapability(
      id: 'home_assistant.control',
      title: 'Control Home Assistant entity',
      description: 'Use the existing allow-listed Home Assistant controls.',
      providerId: 'home_assistant',
      kind: SirisCapabilityKind.control,
      risk: SirisCapabilityRisk.low,
    ),
    SirisCapability(
      id: 'synology.observe',
      title: 'Observe Synology',
      description: 'Read DSM storage, disk and Hyper Backup state.',
      providerId: 'synology',
      kind: SirisCapabilityKind.read,
      risk: SirisCapabilityRisk.none,
    ),
    SirisCapability(
      id: 'unifi.observe',
      title: 'Observe UniFi',
      description: 'Read controller, site, device, client and WAN state.',
      providerId: 'unifi',
      kind: SirisCapabilityKind.read,
      risk: SirisCapabilityRisk.none,
    ),
    SirisCapability(
      id: 'prometheus.query',
      title: 'Query Prometheus',
      description: 'Run bounded authenticated instant PromQL queries.',
      providerId: 'prometheus',
      kind: SirisCapabilityKind.read,
      risk: SirisCapabilityRisk.none,
    ),
    SirisCapability(
      id: 'grafana.browse',
      title: 'Browse Grafana',
      description: 'Discover and open Grafana dashboards through SirisOS.',
      providerId: 'grafana',
      kind: SirisCapabilityKind.navigate,
      risk: SirisCapabilityRisk.none,
    ),
    SirisCapability(
      id: 'storage.observe',
      title: 'Observe host storage',
      description: 'Read host filesystem capacity and utilisation.',
      providerId: 'storage',
      kind: SirisCapabilityKind.read,
      risk: SirisCapabilityRisk.none,
    ),
    SirisCapability(
      id: 'ups.observe',
      title: 'Observe UPS',
      description: 'Read NUT power state, battery, runtime and load.',
      providerId: 'ups',
      kind: SirisCapabilityKind.read,
      risk: SirisCapabilityRisk.none,
    ),
  ];

  List<SirisCapability> get capabilities =>
      List<SirisCapability>.unmodifiable(_capabilities);

  SirisCapability? capability(String id) {
    for (final item in _capabilities) {
      if (item.id == id) return item;
    }
    return null;
  }

  SirisCapabilityStatus statusFor(
    String id, {
    Map<String, SirisConnectorHealth>? health,
  }) {
    final item = capability(id);
    if (item == null) {
      throw ArgumentError.value(id, 'id', 'Unknown SirisOS capability');
    }
    return status(item, health: health);
  }

  SirisCapabilityStatus status(
    SirisCapability capability, {
    Map<String, SirisConnectorHealth>? health,
  }) {
    final providerHealth =
        (health ?? SirisIntegrationManager.instance.health)[capability.providerId];
    if (providerHealth == null) {
      return SirisCapabilityStatus(
        capability: capability,
        available: false,
        reason: 'Provider is not registered.',
      );
    }
    return switch (providerHealth.state) {
      SirisConnectorState.healthy => SirisCapabilityStatus(
          capability: capability,
          available: true,
          reason: 'Provider is healthy.',
        ),
      SirisConnectorState.degraded => SirisCapabilityStatus(
          capability: capability,
          available: capability.kind == SirisCapabilityKind.read,
          reason: capability.kind == SirisCapabilityKind.read
              ? 'Provider is degraded; read capability remains available.'
              : 'Provider is degraded; control capability is unavailable.',
        ),
      SirisConnectorState.connecting => SirisCapabilityStatus(
          capability: capability,
          available: false,
          reason: 'Provider is still connecting.',
        ),
      SirisConnectorState.failed => SirisCapabilityStatus(
          capability: capability,
          available: false,
          reason: 'Provider has failed.',
        ),
      SirisConnectorState.disabled => SirisCapabilityStatus(
          capability: capability,
          available: false,
          reason: 'Provider is disabled or unconfigured.',
        ),
      SirisConnectorState.disconnected => SirisCapabilityStatus(
          capability: capability,
          available: false,
          reason: 'Provider is disconnected.',
        ),
    };
  }

  List<SirisCapabilityStatus> statuses({
    Map<String, SirisConnectorHealth>? health,
  }) => capabilities
      .map((item) => status(item, health: health))
      .toList(growable: false);
}
