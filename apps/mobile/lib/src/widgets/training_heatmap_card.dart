import 'package:flutter/material.dart';

import '../models/training_load.dart';
import '../services/training_load_service.dart';
import '../theme/app_theme.dart';

class TrainingHeatmapCard extends StatefulWidget {
  const TrainingHeatmapCard({this.days = 84, super.key});

  final int days;

  @override
  State<TrainingHeatmapCard> createState() => _TrainingHeatmapCardState();
}

class _TrainingHeatmapCardState extends State<TrainingHeatmapCard> {
  final _service = TrainingLoadService();
  late Future<List<DailyTrainingIntensity>> _future;

  @override
  void initState() {
    super.initState();
    _future = _service.fetchHeatmap(days: widget.days);
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<List<DailyTrainingIntensity>>(
      future: _future,
      builder: (context, snapshot) {
        if (snapshot.connectionState == ConnectionState.waiting) {
          return const Card(
            child: Padding(
              padding: EdgeInsets.all(20),
              child: SizedBox(
                height: 100,
                child: Center(child: CircularProgressIndicator(strokeWidth: 2)),
              ),
            ),
          );
        }
        final data = snapshot.data;
        if (snapshot.hasError || data == null || data.isEmpty) {
          return const SizedBox.shrink();
        }
        return Card(
          child: Padding(
            padding: const EdgeInsets.all(20),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Training volume', style: Theme.of(context).textTheme.titleMedium),
                const SizedBox(height: 4),
                Text(
                  'Daily intensity relative to your own busiest day, gym and running combined.',
                  style: TextStyle(color: Theme.of(context).colorScheme.onSurfaceVariant),
                ),
                const SizedBox(height: 14),
                SingleChildScrollView(
                  scrollDirection: Axis.horizontal,
                  reverse: true,
                  child: _HeatmapGrid(days: data),
                ),
              ],
            ),
          ),
        );
      },
    );
  }
}

class _HeatmapGrid extends StatelessWidget {
  const _HeatmapGrid({required this.days});

  final List<DailyTrainingIntensity> days;

  static const _cellSize = 14.0;
  static const _cellGap = 3.0;

  @override
  Widget build(BuildContext context) {
    // Pad the front so the grid aligns to Monday-start weeks, matching the
    // rest of the app's week convention (TrainingLoadService._week_start).
    final leadingBlanks = days.first.day.weekday - 1;
    final cells = <DailyTrainingIntensity?>[
      ...List<DailyTrainingIntensity?>.filled(leadingBlanks, null),
      ...days,
    ];
    final weekCount = (cells.length / 7).ceil();
    final weeks = List.generate(weekCount, (weekIndex) {
      final start = weekIndex * 7;
      return cells.sublist(start, (start + 7).clamp(0, cells.length));
    });

    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        for (final week in weeks) ...[
          Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              for (var dayIndex = 0; dayIndex < 7; dayIndex++)
                Padding(
                  padding: const EdgeInsets.only(bottom: _cellGap),
                  child: dayIndex < week.length && week[dayIndex] != null
                      ? _DayCell(day: week[dayIndex]!)
                      : const SizedBox(width: _cellSize, height: _cellSize),
                ),
            ],
          ),
          const SizedBox(width: _cellGap),
        ],
      ],
    );
  }
}

class _DayCell extends StatelessWidget {
  const _DayCell({required this.day});

  final DailyTrainingIntensity day;

  Color get _color {
    if (day.intensity <= 0) return AppTheme.surfaceRaised;
    return AppTheme.primaryBright.withValues(alpha: 0.15 + day.intensity.clamp(0.0, 1.0) * 0.85);
  }

  String get _label {
    final date = day.day;
    final dateLabel = '${date.day}/${date.month}/${date.year}';
    if (day.intensity <= 0) return '$dateLabel · rest day';
    final parts = <String>[];
    if (day.gymVolumeKg > 0) parts.add('${day.gymVolumeKg.toStringAsFixed(0)} kg lifted');
    if (day.runningEffortScore > 0) {
      parts.add('${day.runningEffortScore.toStringAsFixed(0)} running effort');
    }
    return '$dateLabel · ${parts.join(', ')}';
  }

  @override
  Widget build(BuildContext context) {
    return Tooltip(
      message: _label,
      child: Container(
        width: _HeatmapGrid._cellSize,
        height: _HeatmapGrid._cellSize,
        decoration: BoxDecoration(
          color: _color,
          borderRadius: BorderRadius.circular(3),
        ),
      ),
    );
  }
}
