class GrafanaDashboardInfo {
  const GrafanaDashboardInfo({
    required this.uid,
    required this.title,
    required this.url,
    this.folderTitle,
    this.tags = const [],
  });

  final String uid;
  final String title;
  final String url;
  final String? folderTitle;
  final List<String> tags;

  factory GrafanaDashboardInfo.fromJson(Map<String, dynamic> json) =>
      GrafanaDashboardInfo(
        uid: json['uid'] as String? ?? '',
        title: json['title'] as String? ?? '',
        url: json['url'] as String? ?? '',
        folderTitle: json['folder_title'] as String?,
        tags: (json['tags'] as List?)
                ?.whereType<String>()
                .toList(growable: false) ??
            const [],
      );
}

class GrafanaSnapshot {
  const GrafanaSnapshot({
    required this.configured,
    required this.available,
    required this.dashboardCount,
    required this.dashboards,
    required this.renderingEnabled,
    this.version,
    this.error,
  });

  final bool configured;
  final bool available;
  final int dashboardCount;
  final List<GrafanaDashboardInfo> dashboards;
  final bool renderingEnabled;
  final String? version;
  final String? error;

  factory GrafanaSnapshot.fromJson(Map<String, dynamic> json) {
    final raw = json['dashboards'];
    return GrafanaSnapshot(
      configured: json['configured'] as bool? ?? false,
      available: json['available'] as bool? ?? false,
      dashboardCount: json['dashboard_count'] as int? ?? 0,
      dashboards: raw is List
          ? raw
              .whereType<Map<String, dynamic>>()
              .map(GrafanaDashboardInfo.fromJson)
              .toList(growable: false)
          : const [],
      renderingEnabled: json['rendering_enabled'] as bool? ?? false,
      version: json['version'] as String?,
      error: json['error'] as String?,
    );
  }
}
