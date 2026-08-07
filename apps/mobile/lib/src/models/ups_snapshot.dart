class UpsSnapshot {
  const UpsSnapshot({
    required this.configured,
    required this.available,
    required this.onBattery,
    required this.lowBattery,
    this.upsName,
    this.description,
    this.status,
    this.batteryChargePercent,
    this.batteryRuntimeSeconds,
    this.loadPercent,
    this.inputVoltage,
    this.outputVoltage,
    this.error,
  });

  final bool configured;
  final bool available;
  final String? upsName;
  final String? description;
  final String? status;
  final bool onBattery;
  final bool lowBattery;
  final double? batteryChargePercent;
  final double? batteryRuntimeSeconds;
  final double? loadPercent;
  final double? inputVoltage;
  final double? outputVoltage;
  final String? error;

  factory UpsSnapshot.fromJson(Map<String, dynamic> json) => UpsSnapshot(
        configured: json['configured'] as bool? ?? false,
        available: json['available'] as bool? ?? false,
        upsName: json['ups_name'] as String?,
        description: json['description'] as String?,
        status: json['status'] as String?,
        onBattery: json['on_battery'] as bool? ?? false,
        lowBattery: json['low_battery'] as bool? ?? false,
        batteryChargePercent: (json['battery_charge_percent'] as num?)?.toDouble(),
        batteryRuntimeSeconds: (json['battery_runtime_seconds'] as num?)?.toDouble(),
        loadPercent: (json['load_percent'] as num?)?.toDouble(),
        inputVoltage: (json['input_voltage'] as num?)?.toDouble(),
        outputVoltage: (json['output_voltage'] as num?)?.toDouble(),
        error: json['error'] as String?,
      );
}
