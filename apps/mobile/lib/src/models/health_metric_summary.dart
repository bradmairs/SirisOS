class HealthMetricSummary {
  const HealthMetricSummary({
    required this.metricType,
    required this.unit,
    required this.latestValue,
    required this.latestTimestamp,
    required this.baselineAverage,
    required this.baselineRatio,
    required this.baselineSampleCount,
  });

  factory HealthMetricSummary.fromJson(Map<String, dynamic> json) =>
      HealthMetricSummary(
        metricType: json['metric_type'] as String,
        unit: json['unit'] as String?,
        latestValue: (json['latest_value'] as num).toDouble(),
        latestTimestamp: DateTime.parse(json['latest_timestamp'] as String),
        baselineAverage: (json['baseline_average'] as num?)?.toDouble(),
        baselineRatio: (json['baseline_ratio'] as num?)?.toDouble(),
        baselineSampleCount: json['baseline_sample_count'] as int,
      );

  final String metricType;
  final String? unit;
  final double latestValue;
  final DateTime latestTimestamp;
  final double? baselineAverage;
  final double? baselineRatio;
  final int baselineSampleCount;
}

class DailyMetricPoint {
  const DailyMetricPoint({
    required this.day,
    required this.value,
    required this.unit,
    required this.sampleCount,
  });

  factory DailyMetricPoint.fromJson(Map<String, dynamic> json) =>
      DailyMetricPoint(
        day: DateTime.parse(json['day'] as String),
        value: (json['value'] as num).toDouble(),
        unit: json['unit'] as String?,
        sampleCount: json['sample_count'] as int,
      );

  final DateTime day;
  final double value;
  final String? unit;
  final int sampleCount;
}
