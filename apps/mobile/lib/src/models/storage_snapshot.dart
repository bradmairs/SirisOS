class StorageVolume {
  const StorageVolume({
    required this.mountpoint,
    required this.device,
    required this.filesystem,
    required this.sizeBytes,
    required this.availableBytes,
    required this.usedBytes,
    required this.usedPercent,
  });

  final String mountpoint;
  final String device;
  final String filesystem;
  final int sizeBytes;
  final int availableBytes;
  final int usedBytes;
  final double usedPercent;

  factory StorageVolume.fromJson(Map<String, dynamic> json) => StorageVolume(
        mountpoint: json['mountpoint'] as String? ?? 'unknown',
        device: json['device'] as String? ?? 'unknown',
        filesystem: json['filesystem'] as String? ?? 'unknown',
        sizeBytes: (json['size_bytes'] as num?)?.toInt() ?? 0,
        availableBytes: (json['available_bytes'] as num?)?.toInt() ?? 0,
        usedBytes: (json['used_bytes'] as num?)?.toInt() ?? 0,
        usedPercent: (json['used_percent'] as num?)?.toDouble() ?? 0,
      );
}

class StorageSnapshot {
  const StorageSnapshot({
    required this.available,
    required this.volumes,
    required this.totalBytes,
    required this.usedBytes,
    required this.availableBytes,
    required this.highestUsedPercent,
    this.error,
  });

  final bool available;
  final List<StorageVolume> volumes;
  final int totalBytes;
  final int usedBytes;
  final int availableBytes;
  final double? highestUsedPercent;
  final String? error;

  factory StorageSnapshot.fromJson(Map<String, dynamic> json) => StorageSnapshot(
        available: json['available'] as bool? ?? false,
        volumes: (json['volumes'] as List? ?? const [])
            .whereType<Map<String, dynamic>>()
            .map(StorageVolume.fromJson)
            .toList(growable: false),
        totalBytes: (json['total_bytes'] as num?)?.toInt() ?? 0,
        usedBytes: (json['used_bytes'] as num?)?.toInt() ?? 0,
        availableBytes: (json['available_bytes'] as num?)?.toInt() ?? 0,
        highestUsedPercent: (json['highest_used_percent'] as num?)?.toDouble(),
        error: json['error'] as String?,
      );
}
