enum TrainingConflictStatus { insufficientData, clear, reducedRecovery, conflict }

extension TrainingConflictStatusValue on TrainingConflictStatus {
  static TrainingConflictStatus fromApiValue(String value) => switch (value) {
        'clear' => TrainingConflictStatus.clear,
        'reduced_recovery' => TrainingConflictStatus.reducedRecovery,
        'conflict' => TrainingConflictStatus.conflict,
        _ => TrainingConflictStatus.insufficientData,
      };
}

class TrainingConflictCheck {
  const TrainingConflictCheck({
    required this.referenceDate,
    required this.status,
    required this.reasons,
    required this.trained,
    required this.sessionSummary,
    required this.guidance,
  });

  factory TrainingConflictCheck.fromJson(Map<String, dynamic> json) =>
      TrainingConflictCheck(
        referenceDate: DateTime.parse(json['reference_date'] as String),
        status: TrainingConflictStatusValue.fromApiValue(json['status'] as String),
        reasons: (json['reasons'] as List<dynamic>)
            .whereType<String>()
            .toList(growable: false),
        trained: json['trained'] as bool,
        sessionSummary: json['session_summary'] as String?,
        guidance: json['guidance'] as String,
      );

  final DateTime referenceDate;
  final TrainingConflictStatus status;
  final List<String> reasons;
  final bool trained;
  final String? sessionSummary;
  final String guidance;
}
