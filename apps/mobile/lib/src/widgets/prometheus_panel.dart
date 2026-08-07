import 'package:flutter/material.dart';

import '../models/prometheus_snapshot.dart';
import '../services/prometheus_service.dart';
import 'siris_design_system.dart';

class PrometheusPanel extends StatefulWidget {
  const PrometheusPanel({super.key});

  @override
  State<PrometheusPanel> createState() => _PrometheusPanelState();
}

class _PrometheusPanelState extends State<PrometheusPanel> {
  final PrometheusService _service = PrometheusService();
  late final Future<PrometheusSnapshot> _future = _service.fetchSnapshot();

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<PrometheusSnapshot>(
      future: _future,
      builder: (context, snapshot) {
        if (snapshot.connectionState == ConnectionState.waiting) {
          return const SirisPanel(
            title: 'Prometheus',
            icon: Icons.monitor_heart_rounded,
            child: LinearProgressIndicator(),
          );
        }
        if (snapshot.hasError || !snapshot.hasData) {
          return const SirisPanel(
            title: 'Prometheus',
            icon: Icons.monitor_heart_rounded,
            child: Text('Prometheus status unavailable.'),
          );
        }

        final data = snapshot.data!;
        if (!data.configured) {
          return const SirisPanel(
            title: 'Prometheus',
            subtitle: 'Optional integration',
            icon: Icons.monitor_heart_rounded,
            child: Text('Set PROMETHEUS_URL to enable Prometheus monitoring.'),
          );
        }

        final status = !data.available
            ? SirisStatus.critical
            : data.unhealthyTargets > 0
                ? SirisStatus.warning
                : SirisStatus.success;
        final label = !data.available
            ? 'Unavailable'
            : data.unhealthyTargets > 0
                ? '${data.unhealthyTargets} down'
                : 'Healthy';

        return SirisPanel(
          title: 'Prometheus',
          subtitle: 'Scrape target health',
          icon: Icons.monitor_heart_rounded,
          trailing: SirisStatusChip(label: label, status: status),
          child: Wrap(
            spacing: 28,
            runSpacing: 16,
            children: [
              SirisMetric(label: 'Targets', value: '${data.totalTargets}'),
              SirisMetric(label: 'Healthy', value: '${data.healthyTargets}'),
              SirisMetric(label: 'Down', value: '${data.unhealthyTargets}'),
            ],
          ),
        );
      },
    );
  }
}
