class SynologyVolume {
  const SynologyVolume({required this.name, required this.status, this.usedPercent});
  final String name;
  final String status;
  final double? usedPercent;

  factory SynologyVolume.fromJson(Map<String, dynamic> json) => SynologyVolume(
        name: json['name'] as String? ?? 'Volume',
        status: json['status'] as String? ?? 'unknown',
        usedPercent: (json['used_percent'] as num?)?.toDouble(),
      );
}

class SynologyDisk {
  const SynologyDisk({required this.name, required this.status, this.model, this.temperatureC});
  final String name;
  final String status;
  final String? model;
  final double? temperatureC;

  factory SynologyDisk.fromJson(Map<String, dynamic> json) => SynologyDisk(
        name: json['name'] as String? ?? 'Disk',
        status: json['status'] as String? ?? 'unknown',
        model: json['model'] as String?,
        temperatureC: (json['temperature_c'] as num?)?.toDouble(),
      );
}

class SynologyBackupTask {
  const SynologyBackupTask({
    required this.taskId, required this.name, required this.status,
    required this.enabled, this.lastResult, this.lastRunAt, this.nextRunAt,
    this.destination,
  });
  final String taskId;
  final String name;
  final String status;
  final bool enabled;
  final String? lastResult;
  final DateTime? lastRunAt;
  final DateTime? nextRunAt;
  final String? destination;

  factory SynologyBackupTask.fromJson(Map<String, dynamic> json) => SynologyBackupTask(
        taskId: json['task_id'] as String? ?? 'unknown',
        name: json['name'] as String? ?? 'Backup',
        status: json['status'] as String? ?? 'unknown',
        enabled: json['enabled'] as bool? ?? true,
        lastResult: json['last_result'] as String?,
        lastRunAt: DateTime.tryParse(json['last_run_at'] as String? ?? ''),
        nextRunAt: DateTime.tryParse(json['next_run_at'] as String? ?? ''),
        destination: json['destination'] as String?,
      );
}

class SynologyBackupHistory {
  const SynologyBackupHistory({
    required this.taskName, required this.status,
    this.taskId, this.startedAt, this.finishedAt, this.message,
  });
  final String? taskId;
  final String taskName;
  final String status;
  final DateTime? startedAt;
  final DateTime? finishedAt;
  final String? message;

  factory SynologyBackupHistory.fromJson(Map<String, dynamic> json) => SynologyBackupHistory(
        taskId: json['task_id'] as String?,
        taskName: json['task_name'] as String? ?? 'Backup',
        status: json['status'] as String? ?? 'unknown',
        startedAt: DateTime.tryParse(json['started_at'] as String? ?? ''),
        finishedAt: DateTime.tryParse(json['finished_at'] as String? ?? ''),
        message: json['message'] as String?,
      );
}

class SynologySnapshot {
  const SynologySnapshot({
    required this.configured,
    required this.available,
    required this.volumes,
    required this.disks,
    required this.unhealthyVolumes,
    required this.unhealthyDisks,
    required this.backupApiAvailable,
    required this.backupMonitoringAvailable,
    required this.backupTasks,
    required this.backupHistory,
    required this.failedBackupTasks,
    required this.staleBackupTasks,
    this.model,
    this.dsmVersion,
    this.highestUsedPercent,
    this.lastSuccessfulBackupAt,
    this.backupError,
    this.error,
  });

  final bool configured;
  final bool available;
  final String? model;
  final String? dsmVersion;
  final List<SynologyVolume> volumes;
  final List<SynologyDisk> disks;
  final int unhealthyVolumes;
  final int unhealthyDisks;
  final double? highestUsedPercent;
  final bool backupApiAvailable;
  final bool backupMonitoringAvailable;
  final List<SynologyBackupTask> backupTasks;
  final List<SynologyBackupHistory> backupHistory;
  final int failedBackupTasks;
  final int staleBackupTasks;
  final DateTime? lastSuccessfulBackupAt;
  final String? backupError;
  final String? error;

  factory SynologySnapshot.fromJson(Map<String, dynamic> json) => SynologySnapshot(
        configured: json['configured'] as bool? ?? false,
        available: json['available'] as bool? ?? false,
        model: json['model'] as String?,
        dsmVersion: json['dsm_version'] as String?,
        volumes: (json['volumes'] as List? ?? const [])
            .whereType<Map<String, dynamic>>()
            .map(SynologyVolume.fromJson)
            .toList(growable: false),
        disks: (json['disks'] as List? ?? const [])
            .whereType<Map<String, dynamic>>()
            .map(SynologyDisk.fromJson)
            .toList(growable: false),
        unhealthyVolumes: (json['unhealthy_volumes'] as num?)?.toInt() ?? 0,
        unhealthyDisks: (json['unhealthy_disks'] as num?)?.toInt() ?? 0,
        highestUsedPercent: (json['highest_used_percent'] as num?)?.toDouble(),
        backupApiAvailable: json['backup_api_available'] as bool? ?? false,
        backupMonitoringAvailable: json['backup_monitoring_available'] as bool? ?? false,
        backupTasks: (json['backup_tasks'] as List? ?? const [])
            .whereType<Map<String, dynamic>>()
            .map(SynologyBackupTask.fromJson)
            .toList(growable: false),
        backupHistory: (json['backup_history'] as List? ?? const [])
            .whereType<Map<String, dynamic>>()
            .map(SynologyBackupHistory.fromJson)
            .toList(growable: false),
        failedBackupTasks: (json['failed_backup_tasks'] as num?)?.toInt() ?? 0,
        staleBackupTasks: (json['stale_backup_tasks'] as num?)?.toInt() ?? 0,
        lastSuccessfulBackupAt: DateTime.tryParse(json['last_successful_backup_at'] as String? ?? ''),
        backupError: json['backup_error'] as String?,
        error: json['error'] as String?,
      );
}
