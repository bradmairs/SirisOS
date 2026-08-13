import 'package:flutter/material.dart';

import '../models/health_metric_summary.dart';
import '../models/health_snapshot.dart';
import '../services/health_service.dart';
import '../theme/app_theme.dart';

class HealthScreen extends StatefulWidget {
  const HealthScreen({super.key});

  @override
  State<HealthScreen> createState() => _HealthScreenState();
}

class _HealthScreenState extends State<HealthScreen> {
  final HealthService _service = HealthService();
  late Future<HealthSnapshot> _future;
  late Future<List<HealthMetricSummary>> _summaryFuture;

  @override
  void initState() {
    super.initState();
    _future = _service.fetchSnapshot();
    _summaryFuture = _service.fetchSummary();
  }

  Future<void> _refresh() async {
    final next = _service.fetchSnapshot();
    final nextSummary = _service.fetchSummary();
    setState(() {
      _future = next;
      _summaryFuture = nextSummary;
    });
    await next;
  }

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      child: FutureBuilder<HealthSnapshot>(
        future: _future,
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting) {
            return const Center(child: CircularProgressIndicator());
          }
          if (snapshot.hasError) {
            return _HealthError(message: snapshot.error.toString(), onRetry: _refresh);
          }

          final data = snapshot.data!;
          return RefreshIndicator(
            onRefresh: _refresh,
            child: LayoutBuilder(
              builder: (context, constraints) {
                final columns = constraints.maxWidth >= 1100
                    ? 3
                    : constraints.maxWidth >= 650
                        ? 2
                        : 1;
                final horizontalPadding = constraints.maxWidth >= 900 ? 28.0 : 20.0;
                final availableWidth = constraints.maxWidth - horizontalPadding * 2;
                final tileWidth = (availableWidth - (columns - 1) * 16) / columns;

                return ListView(
                  physics: const AlwaysScrollableScrollPhysics(),
                  padding: EdgeInsets.fromLTRB(horizontalPadding, 24, horizontalPadding, 32),
                  children: [
                    Row(
                      children: [
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text('Health', style: Theme.of(context).textTheme.headlineMedium),
                              const SizedBox(height: 6),
                              Text(
                                'Live Apple Health data through Health Auto Export.',
                                style: TextStyle(color: Theme.of(context).colorScheme.onSurfaceVariant),
                              ),
                            ],
                          ),
                        ),
                        IconButton.filledTonal(
                          onPressed: _refresh,
                          tooltip: 'Refresh Apple Health',
                          icon: const Icon(Icons.refresh_rounded),
                        ),
                      ],
                    ),
                    const SizedBox(height: 20),
                    _ConnectionCard(snapshot: data),
                    const SizedBox(height: 20),
                    if (data.available && data.metrics.isNotEmpty) ...[
                      Text('Latest metrics', style: Theme.of(context).textTheme.titleLarge),
                      const SizedBox(height: 12),
                      Wrap(
                        spacing: 16,
                        runSpacing: 16,
                        children: data.metrics
                            .map((metric) => SizedBox(width: tileWidth, child: _MetricTile(metric: metric)))
                            .toList(growable: false),
                      ),
                    ] else if (data.available)
                      const _EmptyMetrics(),
                    const SizedBox(height: 20),
                    _RecoveryBaselineSection(future: _summaryFuture),
                    const SizedBox(height: 20),
                    _IntegrationDetails(snapshot: data),
                  ],
                );
              },
            ),
          );
        },
      ),
    );
  }
}

class _RecoveryBaselineSection extends StatelessWidget {
  const _RecoveryBaselineSection({required this.future});

  final Future<List<HealthMetricSummary>> future;

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<List<HealthMetricSummary>>(
      future: future,
      builder: (context, snapshot) {
        final items = snapshot.data ?? const <HealthMetricSummary>[];
        if (snapshot.connectionState == ConnectionState.waiting || items.isEmpty) {
          return const SizedBox.shrink();
        }
        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Recovery vs your baseline', style: Theme.of(context).textTheme.titleLarge),
            const SizedBox(height: 4),
            Text(
              'Latest reading vs your trailing 14-day average.',
              style: TextStyle(color: Theme.of(context).colorScheme.onSurfaceVariant, fontSize: 12),
            ),
            const SizedBox(height: 12),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  children: items
                      .map((item) => _RecoveryBaselineRow(item: item))
                      .toList(growable: false),
                ),
              ),
            ),
          ],
        );
      },
    );
  }
}

class _RecoveryBaselineRow extends StatelessWidget {
  const _RecoveryBaselineRow({required this.item});

  final HealthMetricSummary item;

  @override
  Widget build(BuildContext context) {
    final ratio = item.baselineRatio;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Row(
        children: [
          Expanded(
            child: Text(
              item.metricType.replaceAll('_', ' '),
              style: Theme.of(context).textTheme.bodyMedium,
            ),
          ),
          Text(
            '${item.latestValue.toStringAsFixed(1)}${item.unit != null ? ' ${item.unit}' : ''}',
            style: const TextStyle(fontWeight: FontWeight.w700),
          ),
          const SizedBox(width: 10),
          SizedBox(
            width: 90,
            child: Text(
              ratio == null ? 'Not enough history' : '${ratio.round()}% of usual',
              textAlign: TextAlign.right,
              style: TextStyle(color: Theme.of(context).colorScheme.onSurfaceVariant, fontSize: 12),
            ),
          ),
        ],
      ),
    );
  }
}

class _ConnectionCard extends StatelessWidget {
  const _ConnectionCard({required this.snapshot});

  final HealthSnapshot snapshot;

  @override
  Widget build(BuildContext context) {
    final available = snapshot.available;
    final configured = snapshot.endpointConfigured;
    final accent = available
        ? AppTheme.success
        : configured
            ? Theme.of(context).colorScheme.error
            : Theme.of(context).colorScheme.secondary;
    final title = available
        ? 'Apple Health connected'
        : configured
            ? 'iPhone Health server offline'
            : 'Apple Health not configured';
    final message = available
        ? '${snapshot.metrics.length} health metrics loaded from your iPhone.'
        : configured
            ? 'Open Health Auto Export on your iPhone, keep it in the foreground, and confirm the phone is connected to the same network.'
            : 'Add the MCP URL and bearer token to the SirisOS server .env file, then rebuild the API.';

    return Card(
      child: Container(
        padding: const EdgeInsets.all(22),
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(18),
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [accent.withValues(alpha: 0.12), Colors.transparent],
          ),
        ),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Container(
              width: 52,
              height: 52,
              decoration: BoxDecoration(
                color: accent.withValues(alpha: 0.14),
                borderRadius: BorderRadius.circular(16),
                border: Border.all(color: accent.withValues(alpha: 0.35)),
              ),
              child: Icon(Icons.favorite_rounded, color: accent, size: 28),
            ),
            const SizedBox(width: 16),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(title, style: Theme.of(context).textTheme.titleLarge),
                  const SizedBox(height: 6),
                  Text(message, style: TextStyle(color: Theme.of(context).colorScheme.onSurfaceVariant)),
                  if (snapshot.error != null && snapshot.error!.isNotEmpty) ...[
                    const SizedBox(height: 10),
                    Text(snapshot.error!, style: TextStyle(color: Theme.of(context).colorScheme.error, fontSize: 12)),
                  ],
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _MetricTile extends StatelessWidget {
  const _MetricTile({required this.metric});

  final HealthMetric metric;

  @override
  Widget build(BuildContext context) {
    final details = _metricStyle(metric.name);
    return Card(
      child: Container(
        constraints: const BoxConstraints(minHeight: 154),
        padding: const EdgeInsets.all(20),
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(18),
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [details.color.withValues(alpha: 0.09), Colors.transparent],
          ),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Container(
                  width: 42,
                  height: 42,
                  decoration: BoxDecoration(
                    color: details.color.withValues(alpha: 0.14),
                    borderRadius: BorderRadius.circular(13),
                  ),
                  child: Icon(details.icon, color: details.color),
                ),
                const SizedBox(width: 12),
                Expanded(child: Text(metric.displayName, style: Theme.of(context).textTheme.titleMedium)),
              ],
            ),
            const Spacer(),
            Text(
              metric.displayValue,
              style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                    color: details.color,
                    fontWeight: FontWeight.w800,
                  ),
            ),
            if (metric.date != null) ...[
              const SizedBox(height: 6),
              Text(metric.date!, maxLines: 1, overflow: TextOverflow.ellipsis, style: TextStyle(color: Theme.of(context).colorScheme.onSurfaceVariant, fontSize: 12)),
            ],
          ],
        ),
      ),
    );
  }
}

class _IntegrationDetails extends StatelessWidget {
  const _IntegrationDetails({required this.snapshot});

  final HealthSnapshot snapshot;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Integration', style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 12),
            _DetailRow(label: 'MCP endpoint', value: snapshot.endpointConfigured ? 'Configured' : 'Not configured'),
            const SizedBox(height: 8),
            _DetailRow(label: 'Connection', value: snapshot.available ? 'Online' : 'Offline'),
            const SizedBox(height: 8),
            _DetailRow(label: 'Discovered tools', value: snapshot.tools.isEmpty ? 'None' : snapshot.tools.join(', ')),
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
  Widget build(BuildContext context) => Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(width: 140, child: Text(label, style: TextStyle(color: Theme.of(context).colorScheme.onSurfaceVariant))),
          Expanded(child: Text(value, style: const TextStyle(fontWeight: FontWeight.w600))),
        ],
      );
}

class _EmptyMetrics extends StatelessWidget {
  const _EmptyMetrics();

  @override
  Widget build(BuildContext context) => const Card(
        child: Padding(
          padding: EdgeInsets.all(24),
          child: Text('The Health server is connected, but no supported metrics were returned yet.'),
        ),
      );
}

class _HealthError extends StatelessWidget {
  const _HealthError({required this.message, required this.onRetry});

  final String message;
  final Future<void> Function() onRetry;

  @override
  Widget build(BuildContext context) => Center(
        child: Padding(
          padding: const EdgeInsets.all(32),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(Icons.favorite_border_rounded, size: 54, color: Theme.of(context).colorScheme.onSurfaceVariant),
              const SizedBox(height: 18),
              Text('Health data unavailable', style: Theme.of(context).textTheme.titleLarge),
              const SizedBox(height: 8),
              Text(message, textAlign: TextAlign.center, style: TextStyle(color: Theme.of(context).colorScheme.onSurfaceVariant)),
              const SizedBox(height: 20),
              FilledButton.icon(onPressed: onRetry, icon: const Icon(Icons.refresh_rounded), label: const Text('Try again')),
            ],
          ),
        ),
      );
}

({IconData icon, Color color}) _metricStyle(String name) {
  return switch (name.toLowerCase()) {
    'step_count' || 'steps' => (icon: Icons.directions_walk_rounded, color: const Color(0xFF38BDF8)),
    'resting_heart_rate' => (icon: Icons.monitor_heart_rounded, color: const Color(0xFFFF5D8F)),
    'sleep_analysis' || 'sleep' || 'sleep_duration' => (icon: Icons.bedtime_rounded, color: const Color(0xFF8B7CFF)),
    'body_mass' || 'weight' => (icon: Icons.monitor_weight_rounded, color: const Color(0xFFC45BFF)),
    'active_energy_burned' || 'active_energy' => (icon: Icons.local_fire_department_rounded, color: const Color(0xFFFF9D3D)),
    'vo2_max' || 'vo2max' => (icon: Icons.air_rounded, color: const Color(0xFF63D83A)),
    _ => (icon: Icons.favorite_rounded, color: AppTheme.primary),
  };
}
