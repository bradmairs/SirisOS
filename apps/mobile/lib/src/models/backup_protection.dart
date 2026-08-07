class BackupTaskProtection {
  const BackupTaskProtection({
    required this.taskId,
    required this.taskName,
    required this.completions,
    required this.successes,
    required this.failures,
    required this.successRatePercent,
    required this.lastFinishAt,
    required this.lastResult,
  });

  final String taskId;
  final String taskName;
  final int completions;
  final int successes;
  final int failures;
  final double? successRatePercent;
  final DateTime? lastFinishAt;
  final String? lastResult;

  factory BackupTaskProtection.fromJson(Map<String, dynamic> json) => BackupTaskProtection(
        taskId: json['task_id'] as String? ?? '',
        taskName: json['task_name'] as String? ?? 'Backup task',
        completions: json['completions'] as int? ?? 0,
        successes: json['successes'] as int? ?? 0,
        failures: json['failures'] as int? ?? 0,
        successRatePercent: (json['success_rate_percent'] as num?)?.toDouble(),
        lastFinishAt: DateTime.tryParse(json['last_finish_at'] as String? ?? ''),
        lastResult: json['last_result'] as String?,
      );
}

class BackupProtectionSummary {
  const BackupProtectionSummary({
    required this.days,
    required this.completions,
    required this.successes,
    required this.failures,
    required this.successRatePercent,
    required this.lastFinishAt,
    required this.lastFailureAt,
    required this.protected,
    required this.tasks,
  });

  final int days;
  final int completions;
  final int successes;
  final int failures;
  final double? successRatePercent;
  final DateTime? lastFinishAt;
  final DateTime? lastFailureAt;
  final bool? protected;
  final List<BackupTaskProtection> tasks;

  factory BackupProtectionSummary.fromJson(Map<String, dynamic> json) => BackupProtectionSummary(
        days: json['days'] as int? ?? 30,
        completions: json['completions'] as int? ?? 0,
        successes: json['successes'] as int? ?? 0,
        failures: json['failures'] as int? ?? 0,
        successRatePercent: (json['success_rate_percent'] as num?)?.toDouble(),
        lastFinishAt: DateTime.tryParse(json['last_finish_at'] as String? ?? ''),
        lastFailureAt: DateTime.tryParse(json['last_failure_at'] as String? ?? ''),
        protected: json['protected'] as bool?,
        tasks: (json['tasks'] as List? ?? const [])
            .whereType<Map<String, dynamic>>()
            .map(BackupTaskProtection.fromJson)
            .toList(growable: false),
      );
}
