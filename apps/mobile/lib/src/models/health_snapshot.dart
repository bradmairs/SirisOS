// Shared between HealthMetric, the Recovery baseline rows, and the metric
// history screen -- every place a raw metric_type/unit string from the
// backend reaches the UI. Raw values are whatever the ingestion source used
// (HealthKit's own SCREAMING_SNAKE_CASE enum names, e.g. "BEATS_PER_MINUTE"),
// never meant for display as-is.
String healthMetricDisplayName(String name) => switch (name.toLowerCase()) {
      'step_count' || 'steps' => 'Steps',
      'resting_heart_rate' => 'Resting heart rate',
      'heart_rate_variability' || 'hrv' => 'Heart rate variability',
      'sleep_analysis' || 'sleep' || 'sleep_duration' => 'Sleep',
      'body_mass' || 'weight' => 'Weight',
      'active_energy_burned' || 'active_energy' => 'Active energy',
      'vo2_max' || 'vo2max' => 'VO₂ max',
      'blood_oxygen' => 'Blood oxygen',
      'respiratory_rate' => 'Respiratory rate',
      'body_fat_percentage' => 'Body fat',
      'flights_climbed' => 'Flights climbed',
      _ => name
          .split('_')
          .map((word) => word.isEmpty ? word : '${word[0].toUpperCase()}${word.substring(1).toLowerCase()}')
          .join(' '),
    };

const Map<String, String?> _knownUnits = {
  'beats_per_minute': 'bpm',
  'count': null, // "7,500" reads better than "7500 count"
  'kilogram': 'kg',
  'gram': 'g',
  'percent': '%',
  'millisecond': 'ms',
  'second': 's',
  'hour': 'hr',
  'minute': 'min',
  'kilocalorie': 'kcal',
  'meter': 'm',
  'kilometer': 'km',
  'degree_celsius': '°C',
  'respirations_per_minute': 'breaths/min',
};

String? healthMetricFriendlyUnit(String? raw) {
  if (raw == null || raw.isEmpty) return null;
  final key = raw.toLowerCase();
  if (_knownUnits.containsKey(key)) return _knownUnits[key];
  return key.replaceAll('_', ' ');
}

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

  String get displayName => healthMetricDisplayName(name);

  String get displayValue {
    final raw = value;
    if (raw == null) return '—';
    final formatted = raw is num
        ? raw.toDouble() == raw.toDouble().roundToDouble()
            ? raw.toInt().toString()
            : raw.toDouble().toStringAsFixed(1)
        : raw.toString();
    final friendlyUnit = healthMetricFriendlyUnit(unit);
    return friendlyUnit == null || friendlyUnit.isEmpty ? formatted : '$formatted $friendlyUnit';
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
