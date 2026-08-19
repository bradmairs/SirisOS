import 'training_load.dart';

enum ImprovementRecordType { weight, estimatedOneRepMax, setVolume }

extension ImprovementRecordTypeValue on ImprovementRecordType {
  static ImprovementRecordType fromApiValue(String value) => switch (value) {
        'weight' => ImprovementRecordType.weight,
        'estimated_one_rep_max' => ImprovementRecordType.estimatedOneRepMax,
        _ => ImprovementRecordType.setVolume,
      };

  String get label => switch (this) {
        ImprovementRecordType.weight => 'heaviest weight',
        ImprovementRecordType.estimatedOneRepMax => 'best estimated 1RM',
        ImprovementRecordType.setVolume => 'best set volume',
      };
}

class ExerciseImprovement {
  const ExerciseImprovement({
    required this.exercise,
    required this.recordType,
    required this.value,
    required this.previousValue,
  });

  factory ExerciseImprovement.fromJson(Map<String, dynamic> json) =>
      ExerciseImprovement(
        exercise: json['exercise'] as String,
        recordType:
            ImprovementRecordTypeValue.fromApiValue(json['record_type'] as String),
        value: (json['value'] as num).toDouble(),
        previousValue: (json['previous_value'] as num).toDouble(),
      );

  final String exercise;
  final ImprovementRecordType recordType;
  final double value;
  final double previousValue;
}

class WeeklyCoachReport {
  const WeeklyCoachReport({
    required this.weekStart,
    required this.weekEnd,
    required this.headline,
    this.synthesizedHeadline,
    required this.trainingLoad,
    required this.runningDistanceKm,
    required this.runningDistanceKmDelta,
    required this.runCount,
    required this.runCountDelta,
    required this.gymVolumeKg,
    required this.gymVolumeKgDelta,
    required this.gymSessionCount,
    required this.gymSessionCountDelta,
    required this.improvements,
  });

  factory WeeklyCoachReport.fromJson(Map<String, dynamic> json) =>
      WeeklyCoachReport(
        weekStart: DateTime.parse(json['week_start'] as String),
        weekEnd: DateTime.parse(json['week_end'] as String),
        headline: json['headline'] as String,
        synthesizedHeadline: json['synthesized_headline'] as String?,
        trainingLoad: WeeklyTrainingLoad.fromJson(
            json['training_load'] as Map<String, dynamic>),
        runningDistanceKm: (json['running_distance_km'] as num).toDouble(),
        runningDistanceKmDelta:
            (json['running_distance_km_delta'] as num?)?.toDouble(),
        runCount: json['run_count'] as int,
        runCountDelta: json['run_count_delta'] as int?,
        gymVolumeKg: (json['gym_volume_kg'] as num).toDouble(),
        gymVolumeKgDelta: (json['gym_volume_kg_delta'] as num?)?.toDouble(),
        gymSessionCount: json['gym_session_count'] as int,
        gymSessionCountDelta: json['gym_session_count_delta'] as int?,
        improvements: (json['improvements'] as List<dynamic>)
            .whereType<Map<String, dynamic>>()
            .map(ExerciseImprovement.fromJson)
            .toList(growable: false),
      );

  final DateTime weekStart;
  final DateTime weekEnd;
  final String headline;
  final String? synthesizedHeadline;
  final WeeklyTrainingLoad trainingLoad;
  final double runningDistanceKm;
  final double? runningDistanceKmDelta;
  final int runCount;
  final int? runCountDelta;
  final double gymVolumeKg;
  final double? gymVolumeKgDelta;
  final int gymSessionCount;
  final int? gymSessionCountDelta;
  final List<ExerciseImprovement> improvements;
}
