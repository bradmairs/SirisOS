class ExerciseHistoryPoint {
  const ExerciseHistoryPoint({
    required this.date,
    required this.workoutName,
    required this.weightKg,
    required this.reps,
    required this.rir,
    required this.volumeKg,
    required this.estimatedOneRepMaxKg,
  });

  factory ExerciseHistoryPoint.fromJson(Map<String, dynamic> json) =>
      ExerciseHistoryPoint(
        date: DateTime.parse(json['workout_date'] as String),
        workoutName: json['workout_name'] as String,
        weightKg: (json['weight_kg'] as num).toDouble(),
        reps: json['reps'] as int,
        rir: json['rir'] as int?,
        volumeKg: (json['volume_kg'] as num).toDouble(),
        estimatedOneRepMaxKg:
            (json['estimated_one_rep_max_kg'] as num).toDouble(),
      );

  final DateTime date;
  final String workoutName;
  final double weightKg;
  final int reps;
  final int? rir;
  final double volumeKg;
  final double estimatedOneRepMaxKg;
}

class ExerciseProgress {
  const ExerciseProgress({
    required this.exercise,
    required this.setCount,
    required this.workoutCount,
    required this.latestDate,
    required this.latestWeightKg,
    required this.latestReps,
    required this.bestWeightKg,
    required this.bestEstimatedOneRepMaxKg,
    required this.bestSetVolumeKg,
    required this.history,
  });

  factory ExerciseProgress.fromJson(Map<String, dynamic> json) =>
      ExerciseProgress(
        exercise: json['exercise'] as String,
        setCount: json['set_count'] as int,
        workoutCount: json['workout_count'] as int,
        latestDate: DateTime.parse(json['latest_date'] as String),
        latestWeightKg: (json['latest_weight_kg'] as num).toDouble(),
        latestReps: json['latest_reps'] as int,
        bestWeightKg: (json['best_weight_kg'] as num).toDouble(),
        bestEstimatedOneRepMaxKg:
            (json['best_estimated_one_rep_max_kg'] as num).toDouble(),
        bestSetVolumeKg: (json['best_set_volume_kg'] as num).toDouble(),
        history: (json['history'] as List<dynamic>)
            .whereType<Map<String, dynamic>>()
            .map(ExerciseHistoryPoint.fromJson)
            .toList(growable: false),
      );

  final String exercise;
  final int setCount;
  final int workoutCount;
  final DateTime latestDate;
  final double latestWeightKg;
  final int latestReps;
  final double bestWeightKg;
  final double bestEstimatedOneRepMaxKg;
  final double bestSetVolumeKg;
  final List<ExerciseHistoryPoint> history;
}
