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

class HyperBackupTask {
  const HyperBackupTask({
    required this.taskId,
    required this.name,
    required this.state,
    required this.running,
    required this.failed,
    this.lastResult,
    this.lastFinishAt,
    this.nextRunAt,
    this.destination,
  });

  final String taskId;
  final String name;
  final String state;
  final String? lastResult;
  final String? lastFinishAt;
  final String? nextRunAt;
  final String? destination;
  final bool running;
  final bool failed;

  factory HyperBackupTask.fromJson(Map<String, dynamic> json) => HyperBackupTask(
        taskId: json['task_id'] as String? ?? 'unknown',
        name: json['name'] as String? ?? 'Backup task',
        state: json['state'] as String? ?? 'unknown',
        lastResult: json['last_result'] as String?,
        lastFinishAt: json['last_finish_at'] as String?,
        nextRunAt: json['next_run_at'] as String?,
        destination: json['destination'] as String?,
        running: json['running'] as bool? ?? false,
        failed: json['failed'] as bool? ?? false,
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
    required this.backupTasks,
    required this.runningBackupTasks,
    required this.failedBackupTasks,
    this.model,
    this.dsmVersion,
    this.highestUsedPercent,
    this.latestBackupFinishAt,
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
  final List<HyperBackupTask> backupTasks;
  final int runningBackupTasks;
  final int failedBackupTasks;
  final String? latestBackupFinishAt;
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
        backupTasks: (json['backup_tasks'] as List? ?? const [])
            .whereType<Map<String, dynamic>>()
            .map(HyperBackupTask.fromJson)
            .toList(growable: false),
        runningBackupTasks: (json['running_backup_tasks'] as num?)?.toInt() ?? 0,
        failedBackupTasks: (json['failed_backup_tasks'] as num?)?.toInt() ?? 0,
        latestBackupFinishAt: json['latest_backup_finish_at'] as String?,
        error: json['error'] as String?,
      );
}
