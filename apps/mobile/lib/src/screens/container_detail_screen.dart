import 'dart:async';

import 'package:flutter/material.dart';

import '../models/docker_summary.dart';
import '../services/homelab_service.dart';
import '../widgets/metric_line_chart.dart';
import 'container_logs_screen.dart';

class ContainerDetailScreen extends StatefulWidget {
  const ContainerDetailScreen({required this.initialContainer, super.key});

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
  bool _acting = false;
  String? _error;

  bool get _isProtected => _container.name.startsWith('sirisos-');

  @override
  void initState() {
    super.initState();
    _container = widget.initialContainer;
    _recordSample(_container);
    _timer = Timer.periodic(const Duration(seconds: 5), (_) => _refresh(silent: true));
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
      _memorySamples.add(MetricSample(time: now, value: container.memoryPercent!));
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
      final updated = summary.containers.where((item) => item.containerId == _container.containerId);
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
      if (mounted) setState(() => _error = 'Could not refresh container data.');
    } finally {
      _refreshing = false;
      if (mounted && !silent) setState(() {});
    }
  }

  void _openLogs() {
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => ContainerLogsScreen(
          containerId: _container.containerId,
          containerName: _container.name,
        ),
      ),
    );
  }

  Future<void> _confirmAction(String action) async {
    final verb = action[0].toUpperCase() + action.substring(1);
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text('$verb ${_container.name}?'),
        content: Text(
          action == 'stop'
              ? 'This will stop the container and its service will become unavailable.'
              : 'SirisOS will send a $action command to this container.',
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(context, true), child: Text(verb)),
        ],
      ),
    );
    if (confirmed != true || !mounted) return;

    setState(() {
      _acting = true;
      _error = null;
    });
    try {
      await _service.performContainerAction(_container.containerId, action);
      await Future<void>.delayed(const Duration(seconds: 1));
      await _refresh();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('${_container.name}: $action command completed.')),
        );
      }
    } catch (error) {
      if (mounted) setState(() => _error = error.toString());
    } finally {
      if (mounted) setState(() => _acting = false);
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
          IconButton(onPressed: _openLogs, tooltip: 'View logs', icon: const Icon(Icons.terminal_rounded)),
          IconButton(
            onPressed: _refreshing ? null : _refresh,
            tooltip: 'Refresh container',
            icon: _refreshing
                ? const SizedBox.square(dimension: 20, child: CircularProgressIndicator(strokeWidth: 2))
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
                          backgroundColor: statusColor.withValues(alpha: 0.14),
                          child: Icon(Icons.inventory_2_rounded, color: statusColor),
                        ),
                        const SizedBox(width: 16),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(_container.name, style: Theme.of(context).textTheme.titleLarge),
                              const SizedBox(height: 4),
                              Text(_container.status, style: TextStyle(color: statusColor)),
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
                    value: _container.cpuPercent == null ? '—' : '${_container.cpuPercent!.toStringAsFixed(1)}%',
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: _MetricCard(
                    icon: Icons.memory_rounded,
                    label: 'Memory',
                    value: _container.memoryUsageLabel,
                    detail: _container.memoryPercent == null ? null : '${_container.memoryPercent!.toStringAsFixed(1)}%',
                  ),
                ),
              ],
            ),
            const SizedBox(height: 16),
            MetricLineChart(title: 'CPU history', samples: List.unmodifiable(_cpuSamples), valueSuffix: '%', maxY: 100),
            const SizedBox(height: 16),
            MetricLineChart(title: 'Memory history', samples: List.unmodifiable(_memorySamples), valueSuffix: '%', maxY: 100),
            const SizedBox(height: 16),
            FilledButton.tonalIcon(onPressed: _openLogs, icon: const Icon(Icons.terminal_rounded), label: const Text('View container logs')),
            const SizedBox(height: 16),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(20),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('Container controls', style: Theme.of(context).textTheme.titleMedium),
                    const SizedBox(height: 8),
                    Text(
                      _isProtected
                          ? 'Core SirisOS services are protected from in-app lifecycle controls.'
                          : 'Every action requires confirmation and is applied only to this container.',
                      style: TextStyle(color: scheme.onSurfaceVariant),
                    ),
                    const SizedBox(height: 16),
                    if (_acting)
                      const Center(child: CircularProgressIndicator())
                    else
                      Wrap(
                        spacing: 10,
                        runSpacing: 10,
                        children: [
                          if (!_container.isRunning)
                            FilledButton.icon(
                              onPressed: _isProtected ? null : () => _confirmAction('start'),
                              icon: const Icon(Icons.play_arrow_rounded),
                              label: const Text('Start'),
                            ),
                          if (_container.isRunning) ...[
                            FilledButton.tonalIcon(
                              onPressed: _isProtected ? null : () => _confirmAction('restart'),
                              icon: const Icon(Icons.restart_alt_rounded),
                              label: const Text('Restart'),
                            ),
                            OutlinedButton.icon(
                              onPressed: _isProtected ? null : () => _confirmAction('stop'),
                              icon: const Icon(Icons.stop_rounded),
                              label: const Text('Stop'),
                            ),
                          ],
                        ],
                      ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 16),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(20),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('Container details', style: Theme.of(context).textTheme.titleMedium),
                    const SizedBox(height: 16),
                    _DetailRow(label: 'Image', value: _container.image),
                    _DetailRow(label: 'Container ID', value: _container.containerId),
                    _DetailRow(label: 'State', value: _container.state),
                    _DetailRow(label: 'Status', value: _container.status),
                    _DetailRow(label: 'Health', value: _container.health ?? 'No health check'),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 16),
            Text(
              'Live data refreshes every 5 seconds. Charts retain the latest 30 samples while this screen is open.',
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.bodySmall?.copyWith(color: scheme.onSurfaceVariant),
            ),
          ],
        ),
      ),
    );
  }
}

class _MetricCard extends StatelessWidget {
  const _MetricCard({required this.icon, required this.label, required this.value, this.detail});
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
            style: Theme.of(context).textTheme.bodySmall?.copyWith(color: Theme.of(context).colorScheme.onSurfaceVariant),
          ),
          const SizedBox(height: 3),
          SelectableText(value),
        ],
      ),
    );
  }
}
