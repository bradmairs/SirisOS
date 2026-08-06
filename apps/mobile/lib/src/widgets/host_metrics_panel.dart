import 'dart:async';

import 'package:flutter/material.dart';

import '../models/host_metrics.dart';
import '../services/homelab_service.dart';
import 'metric_line_chart.dart';

class HostMetricsPanel extends StatefulWidget {
  const HostMetricsPanel({super.key});

  @override
  State<HostMetricsPanel> createState() => _HostMetricsPanelState();
}

class _HostMetricsPanelState extends State<HostMetricsPanel> {
  final HomelabService _service = HomelabService();
  final List<MetricSample> _cpu = [];
  final List<MetricSample> _memory = [];
  Timer? _timer;
  HostMetrics? _metrics;
  String? _error;

  @override
  void initState() {
    super.initState();
    _refresh();
    _timer = Timer.periodic(const Duration(seconds: 10), (_) => _refresh());
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  Future<void> _refresh() async {
    try {
      final metrics = await _service.fetchHostMetrics();
      if (!mounted) return;
      setState(() {
        _metrics = metrics;
        _error = metrics.available ? null : metrics.error;
        if (metrics.cpuPercent != null) {
          _cpu.add(MetricSample(time: metrics.generatedAt, value: metrics.cpuPercent!));
        }
        if (metrics.memoryPercent != null) {
          _memory.add(MetricSample(time: metrics.generatedAt, value: metrics.memoryPercent!));
        }
        if (_cpu.length > 30) _cpu.removeAt(0);
        if (_memory.length > 30) _memory.removeAt(0);
      });
    } catch (error) {
      if (mounted) setState(() => _error = error.toString());
    }
  }

  @override
  Widget build(BuildContext context) {
    final metrics = _metrics;
    if (metrics == null && _error == null) {
      return const Card(
        child: Padding(
          padding: EdgeInsets.all(24),
          child: Center(child: CircularProgressIndicator()),
        ),
      );
    }
    if (metrics == null || !metrics.available) {
      return Card(
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Text(_error ?? 'Host metrics are unavailable.'),
        ),
      );
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('Server', style: Theme.of(context).textTheme.titleLarge),
        const SizedBox(height: 12),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(18),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(metrics.hostname ?? 'SirisOS host', style: Theme.of(context).textTheme.titleMedium),
                const SizedBox(height: 16),
                Wrap(
                  spacing: 12,
                  runSpacing: 12,
                  children: [
                    _HostMetric(label: 'CPU', value: metrics.cpuPercent == null ? 'Warming up' : '${metrics.cpuPercent!.toStringAsFixed(1)}%'),
                    _HostMetric(label: 'Memory', value: metrics.memoryPercent == null ? '—' : '${metrics.memoryPercent!.toStringAsFixed(1)}%', detail: '${HostMetrics.formatBytes(metrics.memoryUsedBytes)} / ${HostMetrics.formatBytes(metrics.memoryTotalBytes)}'),
                    _HostMetric(label: 'Disk', value: metrics.diskPercent == null ? '—' : '${metrics.diskPercent!.toStringAsFixed(1)}%', detail: '${HostMetrics.formatBytes(metrics.diskUsedBytes)} / ${HostMetrics.formatBytes(metrics.diskTotalBytes)}'),
                    _HostMetric(label: 'Load', value: metrics.load1m?.toStringAsFixed(2) ?? '—'),
                    _HostMetric(label: 'Uptime', value: metrics.uptimeLabel),
                  ],
                ),
              ],
            ),
          ),
        ),
        const SizedBox(height: 12),
        MetricLineChart(title: 'Host CPU', samples: List.unmodifiable(_cpu), valueSuffix: '%', maxY: 100),
        const SizedBox(height: 12),
        MetricLineChart(title: 'Host memory', samples: List.unmodifiable(_memory), valueSuffix: '%', maxY: 100),
      ],
    );
  }
}

class _HostMetric extends StatelessWidget {
  const _HostMetric({required this.label, required this.value, this.detail});

  final String label;
  final String value;
  final String? detail;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Container(
      width: 150,
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: scheme.surfaceContainerHighest.withValues(alpha: 0.45),
        borderRadius: BorderRadius.circular(16),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label, style: Theme.of(context).textTheme.bodySmall?.copyWith(color: scheme.onSurfaceVariant)),
          const SizedBox(height: 4),
          Text(value, style: Theme.of(context).textTheme.titleMedium),
          if (detail != null) ...[
            const SizedBox(height: 2),
            Text(detail!, style: Theme.of(context).textTheme.bodySmall, maxLines: 1, overflow: TextOverflow.ellipsis),
          ],
        ],
      ),
    );
  }
}
