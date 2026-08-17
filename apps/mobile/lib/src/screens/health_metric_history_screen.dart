import 'package:flutter/material.dart';

import '../models/health_metric_summary.dart';
import '../models/health_snapshot.dart';
import '../services/health_service.dart';
import '../widgets/metric_line_chart.dart';

class HealthMetricHistoryScreen extends StatefulWidget {
  const HealthMetricHistoryScreen({required this.metricType, super.key});

  final String metricType;

  @override
  State<HealthMetricHistoryScreen> createState() =>
      _HealthMetricHistoryScreenState();
}

class _HealthMetricHistoryScreenState
    extends State<HealthMetricHistoryScreen> {
  final HealthService _service = HealthService();
  late Future<List<DailyMetricPoint>> _future;

  @override
  void initState() {
    super.initState();
    _future = _service.fetchMetricHistory(widget.metricType, days: 30);
  }

  Future<void> _refresh() async {
    final next = _service.fetchMetricHistory(widget.metricType, days: 30);
    setState(() => _future = next);
    await next;
  }

  @override
  Widget build(BuildContext context) {
    final displayName =
        HealthMetric.fromJson({'name': widget.metricType}).displayName;
    return Scaffold(
      appBar: AppBar(title: Text(displayName)),
      body: FutureBuilder<List<DailyMetricPoint>>(
        future: _future,
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting) {
            return const Center(child: CircularProgressIndicator());
          }
          if (snapshot.hasError) {
            return Center(
              child: FilledButton.icon(
                onPressed: _refresh,
                icon: const Icon(Icons.refresh_rounded),
                label: const Text('Retry'),
              ),
            );
          }
          final points = snapshot.data ?? const <DailyMetricPoint>[];
          if (points.isEmpty) {
            return const Center(
              child: Padding(
                padding: EdgeInsets.all(28),
                child: Text('No history for this metric yet.'),
              ),
            );
          }
          final unit = points.last.unit ?? '';
          return RefreshIndicator(
            onRefresh: _refresh,
            child: ListView(
              padding: const EdgeInsets.all(20),
              children: [
                MetricLineChart(
                  title: '$displayName -- last 30 days',
                  samples: points
                      .map((point) =>
                          MetricSample(time: point.day, value: point.value))
                      .toList(growable: false),
                  valueSuffix: unit.isEmpty ? '' : ' $unit',
                ),
                const SizedBox(height: 20),
                Text('Daily history', style: Theme.of(context).textTheme.titleLarge),
                const SizedBox(height: 10),
                ...points.reversed.map(
                  (point) => Card(
                    child: ListTile(
                      title: Text(
                          '${point.value.toStringAsFixed(point.value == point.value.roundToDouble() ? 0 : 1)}${unit.isEmpty ? '' : ' $unit'}'),
                      subtitle: Text(
                          '${point.day.day}/${point.day.month}/${point.day.year}'),
                      trailing: Text(
                        '${point.sampleCount} sample${point.sampleCount == 1 ? '' : 's'}',
                        style: TextStyle(
                            color: Theme.of(context).colorScheme.onSurfaceVariant),
                      ),
                    ),
                  ),
                ),
              ],
            ),
          );
        },
      ),
    );
  }
}
