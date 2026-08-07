import 'package:flutter/material.dart';

import '../models/grafana_snapshot.dart';
import '../services/grafana_service.dart';
import 'siris_design_system.dart';

class GrafanaPanel extends StatefulWidget {
  const GrafanaPanel({super.key});

  @override
  State<GrafanaPanel> createState() => _GrafanaPanelState();
}

class _GrafanaPanelState extends State<GrafanaPanel> {
  final GrafanaService _service = GrafanaService();
  late Future<GrafanaSnapshot> _future;

  @override
  void initState() {
    super.initState();
    _future = _service.fetchSnapshot();
  }

  @override
  Widget build(BuildContext context) => FutureBuilder<GrafanaSnapshot>(
        future: _future,
        builder: (context, snapshot) {
          final data = snapshot.data;
          final loading = snapshot.connectionState == ConnectionState.waiting;
          final status = data == null
              ? SirisStatus.neutral
              : !data.configured
                  ? SirisStatus.neutral
                  : data.available
                      ? SirisStatus.success
                      : SirisStatus.warning;
          final label = loading
              ? 'Loading'
              : data == null
                  ? 'Unavailable'
                  : !data.configured
                      ? 'Not configured'
                      : data.available
                          ? 'Connected'
                          : 'Needs attention';

          return SirisPanel(
            title: 'Grafana',
            subtitle: data?.version == null ? 'Dashboard observability' : 'Grafana ${data!.version}',
            icon: Icons.analytics_rounded,
            trailing: SirisStatusChip(label: label, status: status),
            child: Row(
              children: [
                Expanded(
                  child: SirisMetric(
                    label: 'Dashboards',
                    value: data?.available == true ? '${data!.dashboardCount}' : '—',
                    icon: Icons.dashboard_rounded,
                  ),
                ),
                Expanded(
                  child: SirisMetric(
                    label: 'Rendering',
                    value: data?.renderingEnabled == true ? 'Enabled' : 'Optional',
                    icon: Icons.image_rounded,
                  ),
                ),
              ],
            ),
          );
        },
      );
}
