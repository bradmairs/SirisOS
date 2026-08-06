class HealthMetric {
  const HealthMetric({
    required this.name,
    required this.value,
    required this.unit,
    required this.date,
  });

  factory HealthMetric.fromJson(Map<String, dynamic> json) => HealthMetric(
        name: json['name'] as String? ?? 'metric',
        value: json['value'],
        unit: json['unit'] as String?,
        date: json['date'] as String?,
      );

  final String name;
  final Object? value;
  final String? unit;
  final String? date;

  String get displayName => switch (name.toLowerCase()) {
        'step_count' || 'steps' => 'Steps',
        'resting_heart_rate' => 'Resting heart rate',
        'sleep_analysis' || 'sleep' || 'sleep_duration' => 'Sleep',
        'body_mass' || 'weight' => 'Weight',
        'active_energy_burned' || 'active_energy' => 'Active energy',
        'vo2_max' || 'vo2max' => 'VO₂ max',
        _ => name
            .split('_')
            .map((word) => word.isEmpty ? word : '${word[0].toUpperCase()}${word.substring(1)}')
            .join(' '),
      };

  String get displayValue {
    final raw = value;
    if (raw == null) return '—';
    final formatted = raw is num
        ? raw.toDouble() == raw.toDouble().roundToDouble()
            ? raw.toInt().toString()
            : raw.toDouble().toStringAsFixed(1)
        : raw.toString();
    return unit == null || unit!.isEmpty ? formatted : '$formatted $unit';
  }
}

class HealthSnapshot {
  const HealthSnapshot({
    required this.available,
    required this.endpointConfigured,
    required this.tools,
    required this.metrics,
    required this.error,
  });

  factory HealthSnapshot.fromJson(Map<String, dynamic> json) => HealthSnapshot(
        available: json['available'] as bool? ?? false,
        endpointConfigured: json['endpoint_configured'] as bool? ?? false,
        tools: (json['tools'] as List? ?? const [])
            .whereType<String>()
            .toList(growable: false),
        metrics: (json['metrics'] as List? ?? const [])
            .whereType<Map<String, dynamic>>()
            .map(HealthMetric.fromJson)
            .toList(growable: false),
        error: json['error'] as String?,
      );

  final bool available;
  final bool endpointConfigured;
  final List<String> tools;
  final List<HealthMetric> metrics;
  final String? error;
}
