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
    this.muscleGroup,
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
        muscleGroup: json['muscle_group'] as String?,
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
  final String? muscleGroup;
}

class MuscleGroupWorkload {
  const MuscleGroupWorkload({
    required this.muscleGroup,
    required this.totalVolumeKg,
    required this.setCount,
    required this.exerciseCount,
  });

  factory MuscleGroupWorkload.fromJson(Map<String, dynamic> json) =>
      MuscleGroupWorkload(
        muscleGroup: json['muscle_group'] as String,
        totalVolumeKg: (json['total_volume_kg'] as num).toDouble(),
        setCount: json['set_count'] as int,
        exerciseCount: json['exercise_count'] as int,
      );

  final String muscleGroup;
  final double totalVolumeKg;
  final int setCount;
  final int exerciseCount;
}

class MuscleGroupFatigue {
  const MuscleGroupFatigue({
    required this.muscleGroup,
    required this.fatigueFraction,
    this.lastTrainedDate,
    this.daysSinceTrained,
    this.readyAt,
  });

  factory MuscleGroupFatigue.fromJson(Map<String, dynamic> json) =>
      MuscleGroupFatigue(
        muscleGroup: json['muscle_group'] as String,
        fatigueFraction: (json['fatigue_fraction'] as num).toDouble(),
        lastTrainedDate: json['last_trained_date'] == null
            ? null
            : DateTime.parse(json['last_trained_date'] as String),
        daysSinceTrained: json['days_since_trained'] as int?,
        readyAt: json['ready_at'] == null
            ? null
            : DateTime.parse(json['ready_at'] as String),
      );

  final String muscleGroup;
  final double fatigueFraction;
  final DateTime? lastTrainedDate;
  final int? daysSinceTrained;
  final DateTime? readyAt;
}

enum ProgressiveOverloadStatus { progress, repeat, noData }

extension ProgressiveOverloadStatusValue on ProgressiveOverloadStatus {
  static ProgressiveOverloadStatus fromApiValue(String value) =>
      switch (value) {
        'progress' => ProgressiveOverloadStatus.progress,
        'repeat' => ProgressiveOverloadStatus.repeat,
        _ => ProgressiveOverloadStatus.noData,
      };
}

class ProgressiveOverloadSuggestion {
  const ProgressiveOverloadSuggestion({
    required this.exercise,
    required this.status,
    required this.suggestedWeightKg,
    required this.suggestedReps,
    required this.rationale,
    required this.basedOnWorkoutDate,
  });

  factory ProgressiveOverloadSuggestion.fromJson(Map<String, dynamic> json) =>
      ProgressiveOverloadSuggestion(
        exercise: json['exercise'] as String,
        status: ProgressiveOverloadStatusValue.fromApiValue(
            json['status'] as String),
        suggestedWeightKg: (json['suggested_weight_kg'] as num?)?.toDouble(),
        suggestedReps: json['suggested_reps'] as int?,
        rationale: json['rationale'] as String,
        basedOnWorkoutDate: json['based_on_workout_date'] == null
            ? null
            : DateTime.parse(json['based_on_workout_date'] as String),
      );

  final String exercise;
  final ProgressiveOverloadStatus status;
  final double? suggestedWeightKg;
  final int? suggestedReps;
  final String rationale;
  final DateTime? basedOnWorkoutDate;
}

enum DeloadStatus { deloadRecommended, onTrack, insufficientData }

extension DeloadStatusValue on DeloadStatus {
  static DeloadStatus fromApiValue(String value) => switch (value) {
        'deload_recommended' => DeloadStatus.deloadRecommended,
        'on_track' => DeloadStatus.onTrack,
        _ => DeloadStatus.insufficientData,
      };
}

class DeloadSuggestion {
  const DeloadSuggestion({
    required this.exercise,
    required this.status,
    required this.rationale,
    required this.sessionDates,
  });

  factory DeloadSuggestion.fromJson(Map<String, dynamic> json) =>
      DeloadSuggestion(
        exercise: json['exercise'] as String,
        status: DeloadStatusValue.fromApiValue(json['status'] as String),
        rationale: json['rationale'] as String,
        sessionDates: (json['session_dates'] as List<dynamic>?)
            ?.whereType<String>()
            .map(DateTime.parse)
            .toList(growable: false),
      );

  final String exercise;
  final DeloadStatus status;
  final String rationale;
  final List<DateTime>? sessionDates;
}
