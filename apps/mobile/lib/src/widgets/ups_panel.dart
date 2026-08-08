import 'package:flutter/material.dart';

import '../config/display_config.dart';
import '../models/ups_snapshot.dart';
import '../services/ups_service.dart';
import 'siris_design_system.dart';

class UpsPanel extends StatefulWidget {
  const UpsPanel({super.key});

  @override
  State<UpsPanel> createState() => _UpsPanelState();
}

class _UpsPanelState extends State<UpsPanel> {
  final UpsService _service = UpsService();
  late Future<UpsSnapshot> _future;

  @override
  void initState() {
    super.initState();
    _future = _service.fetchSnapshot();
  }

  @override
  Widget build(BuildContext context) => FutureBuilder<UpsSnapshot>(
        future: _future,
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting) {
            return const SirisPanel(
              title: 'UPS',
              icon: Icons.battery_charging_full_rounded,
              child: LinearProgressIndicator(),
            );
          }
          if (snapshot.hasError || !snapshot.hasData) {
            return const SirisPanel(
              title: 'UPS',
              icon: Icons.battery_alert_rounded,
              child: Text('UPS status unavailable.'),
            );
          }

          final data = snapshot.data!;
          if (!data.configured) {
            return const SirisPanel(
              title: 'UPS',
              subtitle: 'Optional NUT integration',
              icon: Icons.battery_charging_full_rounded,
              child: Text('Set NUT_HOST to enable UPS monitoring.'),
            );
          }

          final status = !data.available || data.lowBattery
              ? SirisStatus.critical
              : data.onBattery
                  ? SirisStatus.warning
                  : SirisStatus.success;
          final label = !data.available
              ? 'Unavailable'
              : data.lowBattery
                  ? 'Low battery'
                  : data.onBattery
                      ? 'On battery'
                      : 'Online';

          return SirisPanel(
            title: DisplayConfig.upsLabel(
              description: data.description,
              canonicalName: data.upsName,
            ),
            subtitle: data.status ?? 'Network UPS Tools',
            icon: Icons.battery_charging_full_rounded,
            trailing: SirisStatusChip(label: label, status: status),
            child: Wrap(
              spacing: 28,
              runSpacing: 16,
              children: [
                SirisMetric(
                  label: 'Battery',
                  value: data.batteryChargePercent == null
                      ? '—'
                      : '${data.batteryChargePercent!.toStringAsFixed(0)}%',
                ),
                SirisMetric(
                  label: 'Runtime',
                  value: _runtime(data.batteryRuntimeSeconds),
                ),
                SirisMetric(
                  label: 'Load',
                  value: data.loadPercent == null
                      ? '—'
                      : '${data.loadPercent!.toStringAsFixed(0)}%',
                ),
                SirisMetric(
                  label: 'Input',
                  value: data.inputVoltage == null
                      ? '—'
                      : '${data.inputVoltage!.toStringAsFixed(0)} V',
                ),
              ],
            ),
          );
        },
      );

  static String _runtime(double? seconds) {
    if (seconds == null) return '—';
    final duration = Duration(seconds: seconds.round());
    final hours = duration.inHours;
    final minutes = duration.inMinutes.remainder(60);
    if (hours > 0) return '${hours}h ${minutes}m';
    return '${duration.inMinutes} min';
  }
}
