class HomeAssistantEntity {
  const HomeAssistantEntity({
    required this.entityId,
    required this.state,
    required this.name,
    required this.domain,
    this.lastChanged,
  });

  final String entityId;
  final String state;
  final String name;
  final String domain;
  final DateTime? lastChanged;

  factory HomeAssistantEntity.fromJson(Map<String, dynamic> json) =>
      HomeAssistantEntity(
        entityId: json['entity_id'] as String? ?? '',
        state: json['state'] as String? ?? 'unknown',
        name: json['name'] as String? ?? json['entity_id'] as String? ?? '',
        domain: json['domain'] as String? ?? '',
        lastChanged: DateTime.tryParse(json['last_changed'] as String? ?? ''),
      );
}

class HomeAssistantSnapshot {
  const HomeAssistantSnapshot({
    required this.configured,
    required this.available,
    required this.total,
    required this.unavailable,
    required this.entities,
    this.error,
  });

  final bool configured;
  final bool available;
  final int total;
  final int unavailable;
  final List<HomeAssistantEntity> entities;
  final String? error;

  factory HomeAssistantSnapshot.fromJson(Map<String, dynamic> json) {
    final raw = json['entities'];
    return HomeAssistantSnapshot(
      configured: json['configured'] as bool? ?? false,
      available: json['available'] as bool? ?? false,
      total: json['total'] as int? ?? 0,
      unavailable: json['unavailable'] as int? ?? 0,
      entities: raw is List
          ? raw
              .whereType<Map<String, dynamic>>()
              .map(HomeAssistantEntity.fromJson)
              .toList(growable: false)
          : const [],
      error: json['error'] as String?,
    );
  }
}
