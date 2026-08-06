class DockerContainerInfo {
  const DockerContainerInfo({
    required this.name,
    required this.image,
    required this.state,
    required this.status,
    required this.health,
  });

  factory DockerContainerInfo.fromJson(Map<String, dynamic> json) {
    return DockerContainerInfo(
      name: json['name'] as String? ?? 'Unknown',
      image: json['image'] as String? ?? 'Unknown image',
      state: json['state'] as String? ?? 'unknown',
      status: json['status'] as String? ?? 'unknown',
      health: json['health'] as String?,
    );
  }

  final String name;
  final String image;
  final String state;
  final String status;
  final String? health;

  bool get isRunning => state.toLowerCase() == 'running';
  bool get isUnhealthy => health?.toLowerCase() == 'unhealthy';
}

class DockerSummary {
  const DockerSummary({
    required this.available,
    required this.total,
    required this.running,
    required this.stopped,
    required this.unhealthy,
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
      containers: containers,
      error: json['error'] as String?,
    );
  }

  final bool available;
  final int total;
  final int running;
  final int stopped;
  final int unhealthy;
  final List<DockerContainerInfo> containers;
  final String? error;
}
