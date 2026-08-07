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

class SynologySnapshot {
  const SynologySnapshot({
    required this.configured,
    required this.available,
    required this.volumes,
    required this.disks,
    required this.unhealthyVolumes,
    required this.unhealthyDisks,
    required this.backupApiAvailable,
    this.model,
    this.dsmVersion,
    this.highestUsedPercent,
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
        error: json['error'] as String?,
      );
}
