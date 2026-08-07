import 'package:flutter/material.dart';

import '../models/unifi_snapshot.dart';
import '../services/unifi_service.dart';
import 'siris_design_system.dart';

class UniFiPanel extends StatefulWidget {
  const UniFiPanel({super.key});

  @override
  State<UniFiPanel> createState() => _UniFiPanelState();
}

class _UniFiPanelState extends State<UniFiPanel> {
  final UniFiService _service = UniFiService();
  late Future<UniFiSnapshot> _future = _service.fetchSnapshot();

  @override
  Widget build(BuildContext context) => FutureBuilder<UniFiSnapshot>(
        future: _future,
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting) {
            return const SirisPanel(
              title: 'UniFi',
              icon: Icons.wifi_rounded,
              child: LinearProgressIndicator(),
            );
          }
          if (snapshot.hasError) {
            return SirisPanel(
              title: 'UniFi',
              icon: Icons.wifi_off_rounded,
              child: Text(snapshot.error.toString()),
            );
          }
          final data = snapshot.data!;
          if (!data.configured) {
            return const SirisPanel(
              title: 'UniFi',
              icon: Icons.wifi_rounded,
              child: Text('Not configured'),
            );
          }
          final status = !data.available
              ? SirisStatus.critical
              : data.offlineDevices > 0
                  ? SirisStatus.warning
                  : SirisStatus.success;
          return SirisPanel(
            title: 'UniFi',
            subtitle: data.siteName,
            icon: Icons.wifi_rounded,
            trailing: SirisStatusChip(
              label: data.available
                  ? data.offlineDevices > 0
                      ? '${data.offlineDevices} offline'
                      : 'Healthy'
                  : 'Unavailable',
              status: status,
            ),
            child: Wrap(
              spacing: 22,
              runSpacing: 16,
              children: [
                SirisMetric(
                  label: 'Devices',
                  value: '${data.onlineDevices}/${data.totalDevices}',
                  detail: 'online',
                  icon: Icons.router_rounded,
                ),
                SirisMetric(
                  label: 'APs',
                  value: '${data.accessPoints}',
                  icon: Icons.wifi_tethering_rounded,
                ),
                SirisMetric(
                  label: 'Clients',
                  value: '${data.connectedClients}',
                  icon: Icons.devices_rounded,
                ),
                SirisMetric(
                  label: 'WAN',
                  value: '${data.wanInterfaces}',
                  detail: 'interfaces',
                  icon: Icons.public_rounded,
                ),
              ],
            ),
          );
        },
      );
}
