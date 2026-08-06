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
  final List<MetricSample> _disk = [];
  final List<MetricSample> _receive = [];
  final List<MetricSample> _transmit = [];
  Timer? _timer;
  HostMetrics? _metrics;
  String? _error;
  int _refreshCount = 0;
  bool _refreshing = false;

  @override
  void initState() {
    super.initState();
    _initialise();
    _timer = Timer.periodic(const Duration(seconds: 10), (_) => _refresh());
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  Future<void> _initialise() async {
    await _loadHistory();
    await _refresh();
  }

  Future<void> _loadHistory() async {
    try {
      final history = await _service.fetchHostHistory();
      if (!mounted) return;
      setState(() {
        _replaceHistory(_cpu, history, (item) => item.cpuPercent);
        _replaceHistory(_memory, history, (item) => item.memoryPercent);
        _replaceHistory(_disk, history, (item) => item.diskPercent);
      });
    } catch (_) {
      // Live metrics remain available when history cannot be loaded.
    }
  }

  void _replaceHistory(
    List<MetricSample> target,
    List<HostMetricHistorySample> history,
    double? Function(HostMetricHistorySample) selector,
  ) {
    target
      ..clear()
      ..addAll(
        history.where((item) => selector(item) != null).map(
              (item) => MetricSample(time: item.sampledAt, value: selector(item)!),
            ),
      );
  }

  Future<void> _refresh() async {
    if (_refreshing) return;
    _refreshing = true;
    try {
      final metrics = await _service.fetchHostMetrics();
      if (!mounted) return;
      setState(() {
        _metrics = metrics;
        _error = metrics.available ? null : metrics.error;
        _appendLiveSample(_cpu, metrics.generatedAt, metrics.cpuPercent, 720);
        _appendLiveSample(_memory, metrics.generatedAt, metrics.memoryPercent, 720);
        _appendLiveSample(_disk, metrics.generatedAt, metrics.diskPercent, 720);
        _appendLiveSample(
          _receive,
          metrics.generatedAt,
          metrics.networkReceiveBytesPerSecond,
          60,
        );
        _appendLiveSample(
          _transmit,
          metrics.generatedAt,
          metrics.networkTransmitBytesPerSecond,
          60,
        );
      });

      _refreshCount++;
      if (_refreshCount % 6 == 0) await _loadHistory();
    } catch (error) {
      if (mounted) setState(() => _error = error.toString());
    } finally {
      _refreshing = false;
    }
  }

  void _appendLiveSample(
    List<MetricSample> samples,
    DateTime time,
    double? value,
    int maximum,
  ) {
    if (value == null) return;
    if (samples.isNotEmpty &&
        time.difference(samples.last.time).abs() < const Duration(seconds: 5)) {
      samples[samples.length - 1] = MetricSample(time: time, value: value);
    } else {
      samples.add(MetricSample(time: time, value: value));
    }
    if (samples.length > maximum) {
      samples.removeRange(0, samples.length - maximum);
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
        Row(
          children: [
            Expanded(child: Text('Server', style: Theme.of(context).textTheme.titleLarge)),
            Text(
              '24-hour system history',
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                  ),
            ),
          ],
        ),
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
                    _HostMetric(label: 'Download', value: HostMetrics.formatRate(metrics.networkReceiveBytesPerSecond)),
                    _HostMetric(label: 'Upload', value: HostMetrics.formatRate(metrics.networkTransmitBytesPerSecond)),
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
        const SizedBox(height: 12),
        MetricLineChart(title: 'Root disk usage', samples: List.unmodifiable(_disk), valueSuffix: '%', maxY: 100),
        const SizedBox(height: 12),
        MetricLineChart(title: 'Network received', samples: List.unmodifiable(_receive), valueSuffix: ' B/s'),
        const SizedBox(height: 12),
        MetricLineChart(title: 'Network transmitted', samples: List.unmodifiable(_transmit), valueSuffix: ' B/s'),
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
