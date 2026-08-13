class WeeklyTrainingLoad {
  const WeeklyTrainingLoad({
    required this.weekStart,
    required this.weekEnd,
    required this.runningLoad,
    required this.runningBaseline,
    required this.runningRatio,
    required this.gymLoad,
    required this.gymBaseline,
    required this.gymRatio,
    required this.combinedIndex,
    required this.assessment,
  });

  factory WeeklyTrainingLoad.fromJson(Map<String, dynamic> json) =>
      WeeklyTrainingLoad(
        weekStart: DateTime.parse(json['week_start'] as String),
        weekEnd: DateTime.parse(json['week_end'] as String),
        runningLoad: (json['running_load'] as num).toDouble(),
        runningBaseline: (json['running_baseline'] as num?)?.toDouble(),
        runningRatio: (json['running_ratio'] as num?)?.toDouble(),
        gymLoad: (json['gym_load'] as num).toDouble(),
        gymBaseline: (json['gym_baseline'] as num?)?.toDouble(),
        gymRatio: (json['gym_ratio'] as num?)?.toDouble(),
        combinedIndex: (json['combined_index'] as num?)?.toDouble(),
        assessment: json['assessment'] as String,
      );

  final DateTime weekStart;
  final DateTime weekEnd;
  final double runningLoad;
  final double? runningBaseline;
  final double? runningRatio;
  final double gymLoad;
  final double? gymBaseline;
  final double? gymRatio;
  final double? combinedIndex;
  final String assessment;
}
