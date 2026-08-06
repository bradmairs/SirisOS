class HostMetricHistorySample {
  const HostMetricHistorySample({
    required this.sampledAt,
    required this.hostname,
    required this.cpuPercent,
    required this.memoryPercent,
    required this.diskPercent,
    required this.load1m,
  });

  factory HostMetricHistorySample.fromJson(Map<String, dynamic> json) =>
      HostMetricHistorySample(
        sampledAt: DateTime.tryParse(json['sampled_at'] as String? ?? '') ??
            DateTime.now(),
        hostname: json['hostname'] as String?,
        cpuPercent: (json['cpu_percent'] as num?)?.toDouble(),
        memoryPercent: (json['memory_percent'] as num?)?.toDouble(),
        diskPercent: (json['disk_percent'] as num?)?.toDouble(),
        load1m: (json['load_1m'] as num?)?.toDouble(),
      );

  final DateTime sampledAt;
  final String? hostname;
  final double? cpuPercent;
  final double? memoryPercent;
  final double? diskPercent;
  final double? load1m;
}

class HostMetrics {
  const HostMetrics({
    required this.available,
    required this.hostname,
    required this.cpuPercent,
    required this.memoryPercent,
    required this.memoryUsedBytes,
    required this.memoryTotalBytes,
    required this.diskPercent,
    required this.diskUsedBytes,
    required this.diskTotalBytes,
    required this.load1m,
    required this.uptimeSeconds,
    required this.generatedAt,
    required this.error,
  });

  factory HostMetrics.fromJson(Map<String, dynamic> json) => HostMetrics(
        available: json['available'] as bool? ?? false,
        hostname: json['hostname'] as String?,
        cpuPercent: (json['cpu_percent'] as num?)?.toDouble(),
        memoryPercent: (json['memory_percent'] as num?)?.toDouble(),
        memoryUsedBytes: json['memory_used_bytes'] as int?,
        memoryTotalBytes: json['memory_total_bytes'] as int?,
        diskPercent: (json['disk_percent'] as num?)?.toDouble(),
        diskUsedBytes: json['disk_used_bytes'] as int?,
        diskTotalBytes: json['disk_total_bytes'] as int?,
        load1m: (json['load_1m'] as num?)?.toDouble(),
        uptimeSeconds: (json['uptime_seconds'] as num?)?.toDouble(),
        generatedAt: DateTime.tryParse(json['generated_at'] as String? ?? '') ??
            DateTime.now(),
        error: json['error'] as String?,
      );

  final bool available;
  final String? hostname;
  final double? cpuPercent;
  final double? memoryPercent;
  final int? memoryUsedBytes;
  final int? memoryTotalBytes;
  final double? diskPercent;
  final int? diskUsedBytes;
  final int? diskTotalBytes;
  final double? load1m;
  final double? uptimeSeconds;
  final DateTime generatedAt;
  final String? error;

  String get uptimeLabel {
    final seconds = uptimeSeconds?.round();
    if (seconds == null) return '—';
    final days = seconds ~/ 86400;
    final hours = (seconds % 86400) ~/ 3600;
    return days > 0 ? '${days}d ${hours}h' : '${hours}h';
  }

  static String formatBytes(int? bytes) {
    if (bytes == null) return '—';
    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    var value = bytes.toDouble();
    var index = 0;
    while (value >= 1024 && index < units.length - 1) {
      value /= 1024;
      index++;
    }
    return '${value.toStringAsFixed(value >= 100 ? 0 : 1)} ${units[index]}';
  }
}
