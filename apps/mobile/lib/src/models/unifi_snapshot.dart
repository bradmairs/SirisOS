class UniFiDevice {
  const UniFiDevice({
    required this.id,
    required this.name,
    required this.model,
    required this.state,
    required this.firmwareUpdatable,
    required this.isAccessPoint,
    this.ipAddress,
    this.firmwareVersion,
  });

  final String id;
  final String name;
  final String model;
  final String state;
  final String? ipAddress;
  final String? firmwareVersion;
  final bool firmwareUpdatable;
  final bool isAccessPoint;

  factory UniFiDevice.fromJson(Map<String, dynamic> json) => UniFiDevice(
        id: json['id'] as String? ?? '',
        name: json['name'] as String? ?? 'UniFi device',
        model: json['model'] as String? ?? 'Unknown',
        state: json['state'] as String? ?? 'UNKNOWN',
        ipAddress: json['ip_address'] as String?,
        firmwareVersion: json['firmware_version'] as String?,
        firmwareUpdatable: json['firmware_updatable'] as bool? ?? false,
        isAccessPoint: json['is_access_point'] as bool? ?? false,
      );
}

class UniFiSnapshot {
  const UniFiSnapshot({
    required this.configured,
    required this.available,
    required this.totalDevices,
    required this.onlineDevices,
    required this.offlineDevices,
    required this.accessPoints,
    required this.connectedClients,
    required this.wanInterfaces,
    required this.devices,
    this.siteId,
    this.siteName,
    this.error,
  });

  final bool configured;
  final bool available;
  final String? siteId;
  final String? siteName;
  final int totalDevices;
  final int onlineDevices;
  final int offlineDevices;
  final int accessPoints;
  final int connectedClients;
  final int wanInterfaces;
  final List<UniFiDevice> devices;
  final String? error;

  factory UniFiSnapshot.fromJson(Map<String, dynamic> json) {
    final raw = json['devices'];
    return UniFiSnapshot(
      configured: json['configured'] as bool? ?? false,
      available: json['available'] as bool? ?? false,
      siteId: json['site_id'] as String?,
      siteName: json['site_name'] as String?,
      totalDevices: json['total_devices'] as int? ?? 0,
      onlineDevices: json['online_devices'] as int? ?? 0,
      offlineDevices: json['offline_devices'] as int? ?? 0,
      accessPoints: json['access_points'] as int? ?? 0,
      connectedClients: json['connected_clients'] as int? ?? 0,
      wanInterfaces: json['wan_interfaces'] as int? ?? 0,
      devices: raw is List
          ? raw
              .whereType<Map<String, dynamic>>()
              .map(UniFiDevice.fromJson)
              .toList(growable: false)
          : const [],
      error: json['error'] as String?,
    );
  }
}
