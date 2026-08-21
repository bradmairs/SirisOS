import 'dart:async';

import 'package:flutter/foundation.dart' show defaultTargetPlatform, TargetPlatform;
import 'package:flutter/material.dart';

import '../core/siris_event_bus.dart';
import '../models/health_metric_summary.dart';
import '../models/health_snapshot.dart';
import '../services/health_kit_sync_service.dart';
import '../services/health_service.dart';
import '../theme/app_theme.dart';
import 'health_metric_history_screen.dart';
import 'running_screen.dart' show showAddRunDialog;

void _openMetricHistory(BuildContext context, String metricType) {
  Navigator.of(context).push<void>(
    MaterialPageRoute<void>(
      builder: (_) => HealthMetricHistoryScreen(metricType: metricType),
    ),
  );
}

class HealthScreen extends StatefulWidget {
  const HealthScreen({super.key});

  @override
  State<HealthScreen> createState() => _HealthScreenState();
}

class _HealthScreenState extends State<HealthScreen> {
  final HealthService _service = HealthService();
  final HealthKitSyncService _healthKitSync = HealthKitSyncService();
  late Future<HealthSnapshot> _future;
  late Future<List<HealthMetricSummary>> _summaryFuture;
  late Future<List<UnloggedHealthWorkout>> _unloggedWorkoutsFuture;
  late Future<List<DailyReadinessPoint>> _readinessHistoryFuture;
  StreamSubscription<SirisEvent>? _eventSubscription;
  bool _syncing = false;
  String? _syncError;
  DateTime? _lastSyncTime;

  bool get _healthKitSupported => defaultTargetPlatform == TargetPlatform.iOS;

  @override
  void initState() {
    super.initState();
    _future = _service.fetchSnapshot();
    _summaryFuture = _service.fetchSummary();
    _unloggedWorkoutsFuture = _service.fetchUnloggedWorkouts();
    _readinessHistoryFuture = _service.fetchReadinessHistory();
    _eventSubscription =
        SirisEventBus.instance.on<ModuleDataChanged>().listen((event) {
      if (event.moduleId == 'health') _refresh();
    });
    if (_healthKitSupported) {
      _healthKitSync.lastSyncTime().then((value) {
        if (mounted) setState(() => _lastSyncTime = value);
      });
      _syncHealthKit();
    }
  }

  @override
  void dispose() {
    _eventSubscription?.cancel();
    super.dispose();
  }

  Future<void> _refresh() async {
    final next = _service.fetchSnapshot();
    final nextSummary = _service.fetchSummary();
    final nextUnloggedWorkouts = _service.fetchUnloggedWorkouts();
    final nextReadinessHistory = _service.fetchReadinessHistory();
    setState(() {
      _future = next;
      _summaryFuture = nextSummary;
      _unloggedWorkoutsFuture = nextUnloggedWorkouts;
      _readinessHistoryFuture = nextReadinessHistory;
    });
    await next;
  }

  Future<void> _syncHealthKit() async {
    setState(() {
      _syncing = true;
      _syncError = null;
    });
    try {
      final result = await _healthKitSync.sync();
      if (!mounted) return;
      setState(() => _lastSyncTime = DateTime.now());
      if (result.hadNewData) {
        await _refresh();
      }
    } catch (error) {
      if (!mounted) return;
      setState(() => _syncError = error.toString());
    } finally {
      if (mounted) setState(() => _syncing = false);
    }
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
                                _healthKitSupported
                                    ? 'Synced directly from Apple Health on this iPhone.'
                                    : 'Apple Health sync runs on the iOS app.',
                                style: TextStyle(color: Theme.of(context).colorScheme.onSurfaceVariant),
                              ),
                            ],
                          ),
                        ),
                        if (_healthKitSupported)
                          IconButton.filledTonal(
                            onPressed: _syncing ? null : _syncHealthKit,
                            tooltip: 'Sync Apple Health now',
                            icon: _syncing
                                ? const SizedBox(
                                    width: 18,
                                    height: 18,
                                    child: CircularProgressIndicator(strokeWidth: 2),
                                  )
                                : const Icon(Icons.sync_rounded),
                          )
                        else
                          IconButton.filledTonal(
                            onPressed: _refresh,
                            tooltip: 'Refresh',
                            icon: const Icon(Icons.refresh_rounded),
                          ),
                      ],
                    ),
                    const SizedBox(height: 20),
                    _ConnectionCard(snapshot: data, syncError: _syncError, healthKitSupported: _healthKitSupported),
                    const SizedBox(height: 20),
                    _ReadinessSection(future: _readinessHistoryFuture),
                    const SizedBox(height: 20),
                    if (data.available && data.metrics.isNotEmpty) ...[
                      Text('Today', style: Theme.of(context).textTheme.titleLarge),
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
                    _UnloggedWorkoutsCard(future: _unloggedWorkoutsFuture, onLogged: _refresh),
                    const SizedBox(height: 20),
                    _IntegrationDetails(snapshot: data, lastSyncTime: _lastSyncTime),
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

class _ReadinessSection extends StatelessWidget {
  const _ReadinessSection({required this.future});

  final Future<List<DailyReadinessPoint>> future;

  static Color _scoreColor(int score) {
    if (score >= 70) return AppTheme.success;
    if (score >= 40) return const Color(0xFFFFB020);
    return const Color(0xFFE5484D);
  }

  static String _scoreLabel(int score) {
    if (score >= 85) return 'Great';
    if (score >= 70) return 'Good';
    if (score >= 40) return 'Fair';
    return 'Low';
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<List<DailyReadinessPoint>>(
      future: future,
      builder: (context, snapshot) {
        final points = snapshot.data ?? const <DailyReadinessPoint>[];
        if (snapshot.connectionState == ConnectionState.waiting) {
          return const SizedBox.shrink();
        }
        final scored = points.where((point) => point.score != null).toList(growable: false);
        if (scored.isEmpty) {
          return Card(
            child: Padding(
              padding: const EdgeInsets.all(20),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('Readiness', style: Theme.of(context).textTheme.titleLarge),
                  const SizedBox(height: 6),
                  Text(
                    'Not enough synced heart rate variability or sleep history yet to '
                    'compute a readiness score.',
                    style: TextStyle(color: Theme.of(context).colorScheme.onSurfaceVariant),
                  ),
                ],
              ),
            ),
          );
        }

        final today = scored.last;
        final color = _scoreColor(today.score!);
        return Card(
          child: Padding(
            padding: const EdgeInsets.all(20),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text('Readiness', style: Theme.of(context).textTheme.titleLarge),
                          const SizedBox(height: 4),
                          Text(
                            'Today, vs your own HRV and sleep baseline.',
                            style: TextStyle(color: Theme.of(context).colorScheme.onSurfaceVariant, fontSize: 12),
                          ),
                        ],
                      ),
                    ),
                    Column(
                      crossAxisAlignment: CrossAxisAlignment.end,
                      children: [
                        Text(
                          '${today.score}',
                          style: Theme.of(context).textTheme.headlineMedium?.copyWith(
                                color: color,
                                fontWeight: FontWeight.w800,
                              ),
                        ),
                        Text(_scoreLabel(today.score!), style: TextStyle(color: color, fontWeight: FontWeight.w600)),
                      ],
                    ),
                  ],
                ),
                const SizedBox(height: 16),
                SizedBox(
                  height: 120,
                  width: double.infinity,
                  child: scored.length < 2
                      ? Center(
                          child: Icon(Icons.show_chart_rounded, size: 36, color: Theme.of(context).colorScheme.onSurfaceVariant),
                        )
                      : CustomPaint(
                          painter: _ReadinessChartPainter(
                            samples: scored,
                            lineColor: color,
                            gridColor: Theme.of(context).colorScheme.outlineVariant.withValues(alpha: 0.4),
                            fillColor: color.withValues(alpha: 0.12),
                          ),
                        ),
                ),
              ],
            ),
          ),
        );
      },
    );
  }
}

class _ReadinessChartPainter extends CustomPainter {
  const _ReadinessChartPainter({
    required this.samples,
    required this.lineColor,
    required this.gridColor,
    required this.fillColor,
  });

  final List<DailyReadinessPoint> samples;
  final Color lineColor;
  final Color gridColor;
  final Color fillColor;

  @override
  void paint(Canvas canvas, Size size) {
    const topPadding = 6.0;
    const bottomPadding = 6.0;
    final chartHeight = size.height - topPadding - bottomPadding;

    final gridPaint = Paint()
      ..color = gridColor
      ..strokeWidth = 1;
    for (var i = 0; i <= 2; i++) {
      final y = topPadding + chartHeight * i / 2;
      canvas.drawLine(Offset(0, y), Offset(size.width, y), gridPaint);
    }

    final points = <Offset>[];
    for (var i = 0; i < samples.length; i++) {
      final x = samples.length == 1 ? 0.0 : size.width * i / (samples.length - 1);
      final normalised = (samples[i].score! / 100).clamp(0.0, 1.0);
      final y = topPadding + chartHeight * (1 - normalised);
      points.add(Offset(x, y));
    }

    final linePath = Path()..moveTo(points.first.dx, points.first.dy);
    for (final point in points.skip(1)) {
      linePath.lineTo(point.dx, point.dy);
    }
    final fillPath = Path.from(linePath)
      ..lineTo(points.last.dx, topPadding + chartHeight)
      ..lineTo(points.first.dx, topPadding + chartHeight)
      ..close();

    canvas.drawPath(fillPath, Paint()..color = fillColor);
    canvas.drawPath(
      linePath,
      Paint()
        ..color = lineColor
        ..style = PaintingStyle.stroke
        ..strokeWidth = 2.5
        ..strokeCap = StrokeCap.round
        ..strokeJoin = StrokeJoin.round,
    );
    canvas.drawCircle(points.last, 4, Paint()..color = lineColor);
  }

  @override
  bool shouldRepaint(covariant _ReadinessChartPainter oldDelegate) {
    return oldDelegate.samples != samples || oldDelegate.lineColor != lineColor;
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
              "Today's total (or latest reading) vs your trailing 14-day average. Tap a row for its trend.",
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
    final friendlyUnit = healthMetricFriendlyUnit(item.unit);
    return InkWell(
      onTap: () => _openMetricHistory(context, item.metricType),
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 8),
        child: Row(
          children: [
            Expanded(
              child: Text(
                healthMetricDisplayName(item.metricType),
                style: Theme.of(context).textTheme.bodyMedium,
              ),
            ),
            Text(
              '${item.latestValue.toStringAsFixed(1)}${friendlyUnit != null ? ' $friendlyUnit' : ''}',
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
      ),
    );
  }
}

class _UnloggedWorkoutsCard extends StatelessWidget {
  const _UnloggedWorkoutsCard({required this.future, required this.onLogged});

  final Future<List<UnloggedHealthWorkout>> future;
  final Future<void> Function() onLogged;

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<List<UnloggedHealthWorkout>>(
      future: future,
      builder: (context, snapshot) {
        final items = snapshot.data ?? const <UnloggedHealthWorkout>[];
        if (snapshot.connectionState == ConnectionState.waiting ||
            snapshot.hasError ||
            items.isEmpty) {
          return const SizedBox.shrink();
        }
        return Card(
          child: Padding(
            padding: const EdgeInsets.all(20),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Not yet logged in SirisOS', style: Theme.of(context).textTheme.titleMedium),
                const SizedBox(height: 4),
                Text(
                  'Apple Health has runs or strength workouts from the last 30 days with no '
                  'matching entry in SirisRun or SirisGym on the same day. Runs can be quick-logged '
                  'from their Apple Health data; strength sessions need sets re-entered manually.',
                  style: TextStyle(color: Theme.of(context).colorScheme.onSurfaceVariant, fontSize: 12),
                ),
                const SizedBox(height: 12),
                ...items.map((item) => _UnloggedWorkoutRow(workout: item, onLogged: onLogged)),
              ],
            ),
          ),
        );
      },
    );
  }
}

class _UnloggedWorkoutRow extends StatelessWidget {
  const _UnloggedWorkoutRow({required this.workout, required this.onLogged});

  final UnloggedHealthWorkout workout;
  final Future<void> Function() onLogged;

  static String _dateLabel(DateTime value) => '${value.day}/${value.month}/${value.year}';

  Future<void> _logRun(BuildContext context) async {
    final distanceKm = workout.distanceM! / 1000;
    final paceSecondsPerKm = (workout.durationSeconds! / distanceKm).round();
    final newRecords = await showAddRunDialog(
      context,
      initialDate: workout.startDate,
      initialDistanceKm: distanceKm,
      initialPaceSecondsPerKm: paceSecondsPerKm,
      initialHeartRate: workout.avgHr?.round(),
    );
    if (newRecords != null) await onLogged();
  }

  @override
  Widget build(BuildContext context) {
    final muted = Theme.of(context).colorScheme.onSurfaceVariant;
    final parts = <String>[_dateLabel(workout.startDate)];
    if (workout.distanceM != null) {
      parts.add('${(workout.distanceM! / 1000).toStringAsFixed(1)} km');
    }
    if (workout.durationSeconds != null) {
      parts.add('${(workout.durationSeconds! / 60).round()} min');
    }
    final canQuickLog =
        workout.category == 'running' && workout.distanceM != null && workout.durationSeconds != null;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Row(
        children: [
          Icon(
            workout.category == 'running' ? Icons.directions_run_rounded : Icons.fitness_center_rounded,
            color: muted,
            size: 20,
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(workout.workoutType, style: const TextStyle(fontWeight: FontWeight.w700)),
                Text(parts.join(' · '), style: TextStyle(color: muted, fontSize: 12)),
              ],
            ),
          ),
          if (canQuickLog)
            TextButton(onPressed: () => _logRun(context), child: const Text('Log this run')),
        ],
      ),
    );
  }
}

class _ConnectionCard extends StatelessWidget {
  const _ConnectionCard({
    required this.snapshot,
    required this.syncError,
    required this.healthKitSupported,
  });

  final HealthSnapshot snapshot;
  final String? syncError;
  final bool healthKitSupported;

  @override
  Widget build(BuildContext context) {
    final available = snapshot.available;
    final everSynced = snapshot.endpointConfigured;
    final accent = available
        ? AppTheme.success
        : everSynced
            ? Theme.of(context).colorScheme.error
            : Theme.of(context).colorScheme.secondary;
    final title = available
        ? 'Apple Health synced'
        : everSynced
            ? 'Apple Health data is stale'
            : 'Apple Health not synced yet';
    final message = available
        ? '${snapshot.metrics.length} health metrics from the last sync.'
        : everSynced
            ? 'No new data in the last 48 hours. Open the app on your iPhone to sync.'
            : healthKitSupported
                ? 'Open this screen on your iPhone and grant Apple Health access to start syncing.'
                : 'Open the SirisOS iOS app to grant Apple Health access and sync.';

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
                  if (syncError != null) ...[
                    const SizedBox(height: 10),
                    Text('Sync error: $syncError', style: TextStyle(color: Theme.of(context).colorScheme.error, fontSize: 12)),
                  ] else if (snapshot.error != null && snapshot.error!.isNotEmpty) ...[
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
    return GestureDetector(
      onTap: () => _openMetricHistory(context, metric.name),
      child: Card(
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
            mainAxisSize: MainAxisSize.min,
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
              const SizedBox(height: 16),
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
      ),
    );
  }
}

class _IntegrationDetails extends StatelessWidget {
  const _IntegrationDetails({required this.snapshot, required this.lastSyncTime});

  final HealthSnapshot snapshot;
  final DateTime? lastSyncTime;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Sync', style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 12),
            const _DetailRow(label: 'Source', value: 'Apple HealthKit (on-device)'),
            const SizedBox(height: 8),
            _DetailRow(label: 'Data freshness', value: snapshot.available ? 'Up to date' : 'Stale'),
            const SizedBox(height: 8),
            _DetailRow(
              label: 'Last synced on this device',
              value: lastSyncTime == null ? 'Never' : _formatRelative(lastSyncTime!),
            ),
            const SizedBox(height: 8),
            _DetailRow(
              label: 'Metrics tracked',
              value: snapshot.tools.isEmpty
                  ? 'None'
                  : snapshot.tools.map(healthMetricDisplayName).join(', '),
            ),
          ],
        ),
      ),
    );
  }

  String _formatRelative(DateTime time) {
    final diff = DateTime.now().difference(time);
    if (diff.inMinutes < 1) return 'Just now';
    if (diff.inMinutes < 60) return '${diff.inMinutes}m ago';
    if (diff.inHours < 24) return '${diff.inHours}h ago';
    return '${diff.inDays}d ago';
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
    'heart_rate_variability' || 'hrv' => (icon: Icons.timeline_rounded, color: const Color(0xFF5DD8C8)),
    'sleep_analysis' || 'sleep' || 'sleep_duration' => (icon: Icons.bedtime_rounded, color: const Color(0xFF8B7CFF)),
    'body_mass' || 'weight' => (icon: Icons.monitor_weight_rounded, color: const Color(0xFFC45BFF)),
    'active_energy_burned' || 'active_energy' => (icon: Icons.local_fire_department_rounded, color: const Color(0xFFFF9D3D)),
    'vo2_max' || 'vo2max' => (icon: Icons.air_rounded, color: const Color(0xFF63D83A)),
    'blood_oxygen' => (icon: Icons.bloodtype_rounded, color: const Color(0xFFE0446E)),
    'respiratory_rate' => (icon: Icons.air_rounded, color: const Color(0xFF4FA8E8)),
    'body_fat_percentage' => (icon: Icons.pie_chart_rounded, color: const Color(0xFFC45BFF)),
    'flights_climbed' => (icon: Icons.stairs_rounded, color: const Color(0xFFFF9D3D)),
    _ => (icon: Icons.favorite_rounded, color: AppTheme.primary),
  };
}
