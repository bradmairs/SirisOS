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

class DailyReadinessPoint {
  const DailyReadinessPoint({
    required this.day,
    required this.score,
    required this.hrvRatio,
    required this.sleepRatio,
  });

  factory DailyReadinessPoint.fromJson(Map<String, dynamic> json) =>
      DailyReadinessPoint(
        day: DateTime.parse(json['day'] as String),
        score: json['score'] as int?,
        hrvRatio: (json['hrv_ratio'] as num?)?.toDouble(),
        sleepRatio: (json['sleep_ratio'] as num?)?.toDouble(),
      );

  final DateTime day;
  final int? score;
  final double? hrvRatio;
  final double? sleepRatio;
}

class UnloggedHealthWorkout {
  const UnloggedHealthWorkout({
    required this.externalId,
    required this.workoutType,
    required this.category,
    required this.startDate,
    required this.durationSeconds,
    required this.distanceM,
    required this.avgHr,
  });

  factory UnloggedHealthWorkout.fromJson(Map<String, dynamic> json) =>
      UnloggedHealthWorkout(
        externalId: json['external_id'] as String,
        workoutType: json['workout_type'] as String,
        category: json['category'] as String,
        startDate: DateTime.parse(json['start_date'] as String),
        durationSeconds: (json['duration_seconds'] as num?)?.toDouble(),
        distanceM: (json['distance_m'] as num?)?.toDouble(),
        avgHr: (json['avg_hr'] as num?)?.toDouble(),
      );

  final String externalId;
  final String workoutType;
  final String category;
  final DateTime startDate;
  final double? durationSeconds;
  final double? distanceM;
  final double? avgHr;
}
