class RunRecord {
  const RunRecord({
    required this.id,
    required this.runDate,
    required this.runType,
    required this.distanceKm,
    required this.averagePaceSecondsPerKm,
    required this.averageHeartRate,
    required this.effortScore,
    required this.fitnessScore,
  });

  factory RunRecord.fromJson(Map<String, dynamic> json) => RunRecord(
        id: json['id'] as int,
        runDate: DateTime.parse(json['run_date'] as String),
        runType: json['run_type'] as String,
        distanceKm: (json['distance_km'] as num).toDouble(),
        averagePaceSecondsPerKm: json['average_pace_seconds_per_km'] as int,
        averageHeartRate: json['average_heart_rate'] as int,
        effortScore: (json['effort_score'] as num).toDouble(),
        fitnessScore: (json['fitness_score'] as num).toDouble(),
      );

  final int id;
  final DateTime runDate;
  final String runType;
  final double distanceKm;
  final int averagePaceSecondsPerKm;
  final int averageHeartRate;
  final double effortScore;
  final double fitnessScore;

  String get paceLabel {
    final minutes = averagePaceSecondsPerKm ~/ 60;
    final seconds = averagePaceSecondsPerKm % 60;
    return '$minutes:${seconds.toString().padLeft(2, '0')}/km';
  }
}
