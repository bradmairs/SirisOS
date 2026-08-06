import 'dart:async';

import 'package:flutter/material.dart';

import '../models/docker_summary.dart';
import '../services/homelab_service.dart';
import '../widgets/metric_line_chart.dart';

class ContainerDetailScreen extends StatefulWidget {
  const ContainerDetailScreen({
    required this.initialContainer,
    super.key,
  });

  final DockerContainerInfo initialContainer;

  @override
  State<ContainerDetailScreen> createState() => _ContainerDetailScreenState();
}

class _ContainerDetailScreenState extends State<ContainerDetailScreen> {
  static const _maxSamples = 30;

  final HomelabService _service = HomelabService();
  final List<MetricSample> _cpuSamples = [];
  final List<MetricSample> _memorySamples = [];
  Timer? _timer;
  late DockerContainerInfo _container;
  bool _refreshing = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _container = widget.initialContainer;
    _recordSample(_container);
    _timer = Timer.periodic(
      const Duration(seconds: 5),
      (_) => _refresh(silent: true),
    );
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  void _recordSample(DockerContainerInfo container) {
    final now = DateTime.now();
    if (container.cpuPercent != null) {
      _cpuSamples.add(MetricSample(time: now, value: container.cpuPercent!));
    }
    if (container.memoryPercent != null) {
      _memorySamples.add(
        MetricSample(time: now, value: container.memoryPercent!),
      );
    }

    if (_cpuSamples.length > _maxSamples) {
      _cpuSamples.removeRange(0, _cpuSamples.length - _maxSamples);
    }
    if (_memorySamples.length > _maxSamples) {
      _memorySamples.removeRange(0, _memorySamples.length - _maxSamples);
    }
  }

  Future<void> _refresh({bool silent = false}) async {
    if (_refreshing) return;

    if (!silent) {
      setState(() {
        _refreshing = true;
        _error = null;
      });
    } else {
      _refreshing = true;
    }

    try {
      final summary = await _service.fetchDockerSummary();
      final updated = summary.containers.where(
        (item) => item.containerId == _container.containerId,
      );

      if (!mounted) return;

      if (updated.isEmpty) {
        setState(() => _error = 'This container is no longer available.');
      } else {
        setState(() {
          _container = updated.first;
          _recordSample(_container);
          _error = null;
        });
      }
    } catch (_) {
      if (mounted) {
        setState(() => _error = 'Could not refresh container data.');
      }
    } finally {
      _refreshing = false;
      if (mounted && !silent) setState(() {});
    }
  }

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final statusColor = _container.isUnhealthy
        ? scheme.error
        : _container.isRunning
            ? scheme.primary
            : scheme.onSurfaceVariant;

    return Scaffold(
      appBar: AppBar(
        title: Text(_container.name),
        actions: [
          IconButton(
            onPressed: _refreshing ? null : _refresh,
            tooltip: 'Refresh container',
            icon: _refreshing
                ? const SizedBox.square(
                    dimension: 20,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.refresh_rounded),
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: _refresh,
        child: ListView(
          padding: const EdgeInsets.all(20),
          children: [
            Card(
              child: Padding(
                padding: const EdgeInsets.all(22),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        CircleAvatar(
                          radius: 26,
                          backgroundColor:
                              statusColor.withValues(alpha: 0.14),
                          child: Icon(
                            Icons.inventory_2_rounded,
                            color: statusColor,
                          ),
                        ),
                        const SizedBox(width: 16),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                _container.name,
                                style: Theme.of(context).textTheme.titleLarge,
                              ),
                              const SizedBox(height: 4),
                              Text(
                                _container.status,
                                style: TextStyle(color: statusColor),
                              ),
                            ],
                          ),
                        ),
                      ],
                    ),
                    if (_error != null) ...[
                      const SizedBox(height: 18),
                      Text(_error!, style: TextStyle(color: scheme.error)),
                    ],
                  ],
                ),
              ),
            ),
            const SizedBox(height: 16),
            Row(
              children: [
                Expanded(
                  child: _MetricCard(
                    icon: Icons.speed_rounded,
                    label: 'CPU',
                    value: _container.cpuPercent == null
                        ? '—'
                        : '${_container.cpuPercent!.toStringAsFixed(1)}%',
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: _MetricCard(
                    icon: Icons.memory_rounded,
                    label: 'Memory',
                    value: _container.memoryUsageLabel,
                    detail: _container.memoryPercent == null
                        ? null
                        : '${_container.memoryPercent!.toStringAsFixed(1)}%',
                  ),
                ),
              ],
            ),
            const SizedBox(height: 16),
            MetricLineChart(
              title: 'CPU history',
              samples: List.unmodifiable(_cpuSamples),
              valueSuffix: '%',
              maxY: 100,
            ),
            const SizedBox(height: 16),
            MetricLineChart(
              title: 'Memory history',
              samples: List.unmodifiable(_memorySamples),
              valueSuffix: '%',
              maxY: 100,
            ),
            const SizedBox(height: 16),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(20),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Container details',
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                    const SizedBox(height: 16),
                    _DetailRow(label: 'Image', value: _container.image),
                    _DetailRow(
                      label: 'Container ID',
                      value: _container.containerId,
                    ),
                    _DetailRow(label: 'State', value: _container.state),
                    _DetailRow(label: 'Status', value: _container.status),
                    _DetailRow(
                      label: 'Health',
                      value: _container.health ?? 'No health check',
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 16),
            Text(
              'Live data refreshes every 5 seconds. Charts retain the latest 30 samples while this screen is open.',
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    color: scheme.onSurfaceVariant,
                  ),
            ),
          ],
        ),
      ),
    );
  }
}

class _MetricCard extends StatelessWidget {
  const _MetricCard({
    required this.icon,
    required this.label,
    required this.value,
    this.detail,
  });

  final IconData icon;
  final String label;
  final String value;
  final String? detail;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(18),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(icon, color: scheme.primary),
            const SizedBox(height: 14),
            Text(label, style: TextStyle(color: scheme.onSurfaceVariant)),
            const SizedBox(height: 4),
            Text(value, style: Theme.of(context).textTheme.titleLarge),
            if (detail != null) ...[
              const SizedBox(height: 2),
              Text(detail!, style: Theme.of(context).textTheme.bodySmall),
            ],
          ],
        ),
      ),
    );
  }
}

class _DetailRow extends StatelessWidget {
  const _DetailRow({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            label,
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
                  color: Theme.of(context).colorScheme.onSurfaceVariant,
                ),
          ),
          const SizedBox(height: 3),
          SelectableText(value),
        ],
      ),
    );
  }
}
