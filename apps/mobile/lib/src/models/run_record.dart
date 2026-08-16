enum RunningRecordType { longestRun, lowestHeartRateAtPace }

extension RunningRecordTypeValue on RunningRecordType {
  static RunningRecordType fromApiValue(String value) => switch (value) {
        'longest_run' => RunningRecordType.longestRun,
        _ => RunningRecordType.lowestHeartRateAtPace,
      };

  String get label => switch (this) {
        RunningRecordType.longestRun => 'longest run',
        RunningRecordType.lowestHeartRateAtPace => 'lowest heart rate at pace',
      };
}

class RunningPersonalRecord {
  const RunningPersonalRecord({
    required this.recordType,
    required this.value,
    required this.previousValue,
    required this.paceSecondsPerKm,
  });

  factory RunningPersonalRecord.fromJson(Map<String, dynamic> json) =>
      RunningPersonalRecord(
        recordType:
            RunningRecordTypeValue.fromApiValue(json['record_type'] as String),
        value: (json['value'] as num).toDouble(),
        previousValue: (json['previous_value'] as num?)?.toDouble(),
        paceSecondsPerKm: json['pace_seconds_per_km'] as int?,
      );

  final RunningRecordType recordType;
  final double value;
  final double? previousValue;
  final int? paceSecondsPerKm;
}

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
    this.newRecords = const [],
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
        newRecords: (json['new_records'] as List? ?? const [])
            .whereType<Map<String, dynamic>>()
            .map(RunningPersonalRecord.fromJson)
            .toList(growable: false),
      );

  final int id;
  final DateTime runDate;
  final String runType;
  final double distanceKm;
  final int averagePaceSecondsPerKm;
  final int averageHeartRate;
  final double effortScore;
  final double fitnessScore;
  final List<RunningPersonalRecord> newRecords;

  String get paceLabel {
    final minutes = averagePaceSecondsPerKm ~/ 60;
    final seconds = averagePaceSecondsPerKm % 60;
    return '$minutes:${seconds.toString().padLeft(2, '0')}/km';
  }
}
