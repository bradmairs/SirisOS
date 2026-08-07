class DockerContainerInfo {
  const DockerContainerInfo({
    required this.containerId,
    required this.name,
    required this.image,
    required this.state,
    required this.status,
    required this.health,
    required this.cpuPercent,
    required this.memoryUsageBytes,
    required this.memoryLimitBytes,
    required this.memoryPercent,
    required this.updateAvailable,
    required this.updateCheckError,
  });

  factory DockerContainerInfo.fromJson(Map<String, dynamic> json) {
    return DockerContainerInfo(
      containerId: json['container_id'] as String? ?? '',
      name: json['name'] as String? ?? 'Unknown',
      image: json['image'] as String? ?? 'Unknown image',
      state: json['state'] as String? ?? 'unknown',
      status: json['status'] as String? ?? 'unknown',
      health: json['health'] as String?,
      cpuPercent: (json['cpu_percent'] as num?)?.toDouble(),
      memoryUsageBytes: json['memory_usage_bytes'] as int?,
      memoryLimitBytes: json['memory_limit_bytes'] as int?,
      memoryPercent: (json['memory_percent'] as num?)?.toDouble(),
      updateAvailable: json['update_available'] as bool? ?? false,
      updateCheckError: json['update_check_error'] as String?,
    );
  }

  final String containerId;
  final String name;
  final String image;
  final String state;
  final String status;
  final String? health;
  final double? cpuPercent;
  final int? memoryUsageBytes;
  final int? memoryLimitBytes;
  final double? memoryPercent;
  final bool updateAvailable;
  final String? updateCheckError;

  bool get isRunning => state.toLowerCase() == 'running';
  bool get isUnhealthy => health?.toLowerCase() == 'unhealthy';

  String get memoryUsageLabel {
    final usage = memoryUsageBytes;
    if (usage == null) return '—';
    return _formatBytes(usage);
  }

  static String _formatBytes(int bytes) {
    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    var value = bytes.toDouble();
    var unitIndex = 0;

    while (value >= 1024 && unitIndex < units.length - 1) {
      value /= 1024;
      unitIndex++;
    }

    final decimals = value >= 100 || unitIndex == 0 ? 0 : 1;
    return '${value.toStringAsFixed(decimals)} ${units[unitIndex]}';
  }
}

class DockerSummary {
  const DockerSummary({
    required this.available,
    required this.total,
    required this.running,
    required this.stopped,
    required this.unhealthy,
    required this.updatesAvailable,
    required this.containers,
    required this.error,
  });

  factory DockerSummary.fromJson(Map<String, dynamic> json) {
    final rawContainers = json['containers'];
    final containers = rawContainers is List
        ? rawContainers
            .whereType<Map<String, dynamic>>()
            .map(DockerContainerInfo.fromJson)
            .toList(growable: false)
        : const <DockerContainerInfo>[];

    return DockerSummary(
      available: json['available'] as bool? ?? false,
      total: json['total'] as int? ?? 0,
      running: json['running'] as int? ?? 0,
      stopped: json['stopped'] as int? ?? 0,
      unhealthy: json['unhealthy'] as int? ?? 0,
      updatesAvailable: json['updates_available'] as int? ??
          containers.where((item) => item.updateAvailable).length,
      containers: containers,
      error: json['error'] as String?,
    );
  }

  final bool available;
  final int total;
  final int running;
  final int stopped;
  final int unhealthy;
  final int updatesAvailable;
  final List<DockerContainerInfo> containers;
  final String? error;
}
