import 'package:flutter/material.dart';

import '../core/muscle_readiness.dart';
import '../models/exercise_progress.dart';
import '../services/gym_service.dart';
import '../theme/app_theme.dart';
import 'body_diagram.dart';

class _MuscleMapData {
  const _MuscleMapData({
    required this.workload,
    required this.fatigue,
    required this.untagged,
  });

  final List<MuscleGroupWorkload> workload;
  final List<MuscleGroupFatigue> fatigue;
  final List<String> untagged;
}

class MuscleMapCard extends StatefulWidget {
  const MuscleMapCard({this.days = 7, super.key});

  final int days;

  @override
  State<MuscleMapCard> createState() => _MuscleMapCardState();
}

class _MuscleMapCardState extends State<MuscleMapCard> {
  static const _groupOrder = ['chest', 'back', 'legs', 'shoulders', 'arms', 'core'];

  final GymService _service = GymService();
  late Future<_MuscleMapData> _dataFuture;
  bool _front = true;

  @override
  void initState() {
    super.initState();
    _dataFuture = _load();
  }

  Future<_MuscleMapData> _load() async {
    final results = await Future.wait([
      _service.fetchMuscleGroupWorkload(days: widget.days),
      _service.fetchMuscleGroupFatigue(),
      _service.fetchUntaggedExercises(),
    ]);
    return _MuscleMapData(
      workload: results[0] as List<MuscleGroupWorkload>,
      fatigue: results[1] as List<MuscleGroupFatigue>,
      untagged: results[2] as List<String>,
    );
  }

  static Color _colorForFatigue(double fraction) {
    final hsl = HSLColor.fromColor(AppTheme.primary);
    final ready = hsl.withLightness(0.84).withSaturation(0.45).toColor();
    final fatigued = HSLColor.fromColor(AppTheme.primaryBright).toColor();
    return Color.lerp(ready, fatigued, fraction.clamp(0.0, 1.0))!;
  }

  static String _readinessLabel(MuscleGroupFatigue item) => MuscleReadiness.label(
        MuscleReadiness.level(
          daysSinceTrained: item.daysSinceTrained,
          fatigueFraction: item.fatigueFraction,
        ),
      );

  static String? _readyInLabel(MuscleGroupFatigue item) {
    final days = MuscleReadiness.daysUntilReady(
      readyAt: item.readyAt,
      fatigueFraction: item.fatigueFraction,
      now: DateTime.now(),
    );
    if (days == null) return null;
    if (days == 0) return 'Ready now';
    return 'Ready in ~$days day${days == 1 ? '' : 's'}';
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<_MuscleMapData>(
      future: _dataFuture,
      builder: (context, snapshot) {
        if (snapshot.connectionState == ConnectionState.waiting) {
          return const Card(
            child: Padding(
              padding: EdgeInsets.all(20),
              child: SizedBox(
                height: 60,
                child: Center(child: CircularProgressIndicator(strokeWidth: 2)),
              ),
            ),
          );
        }
        final data = snapshot.data;
        if (snapshot.hasError || data == null) {
          return const SizedBox.shrink();
        }

        final fatigueByGroup = {for (final item in data.fatigue) item.muscleGroup: item};
        final volumeByGroup = {for (final item in data.workload) item.muscleGroup: item};
        final colors = {
          for (final item in data.fatigue) item.muscleGroup: _colorForFatigue(item.fatigueFraction),
        };
        final untagged = data.untagged;

        return Card(
          child: Padding(
            padding: const EdgeInsets.all(20),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Expanded(
                      child: Text('Muscle map', style: Theme.of(context).textTheme.titleMedium),
                    ),
                    SegmentedButton<bool>(
                      segments: const [
                        ButtonSegment(value: true, label: Text('Front')),
                        ButtonSegment(value: false, label: Text('Back')),
                      ],
                      selected: {_front},
                      showSelectedIcon: false,
                      onSelectionChanged: (selection) => setState(() => _front = selection.first),
                    ),
                  ],
                ),
                const SizedBox(height: 4),
                Text(
                  'Shade shows estimated fatigue: lighter as a muscle group recovers, '
                  'darker while recently trained hard. Estimated from your own volume and a '
                  'general 3-day recovery window -- not a physiological measurement.',
                  style: TextStyle(
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                    fontSize: 12,
                  ),
                ),
                const SizedBox(height: 14),
                Center(
                  child: SizedBox(
                    height: 260,
                    child: BodyDiagram(front: _front, colors: colors),
                  ),
                ),
                const SizedBox(height: 14),
                ..._groupOrder.map((group) {
                  final fatigue = fatigueByGroup[group];
                  final volume = volumeByGroup[group];
                  final label = group[0].toUpperCase() + group.substring(1);
                  final readyIn = fatigue == null ? null : _readyInLabel(fatigue);
                  return Padding(
                    padding: const EdgeInsets.symmetric(vertical: 5),
                    child: Row(
                      children: [
                        Container(
                          width: 12,
                          height: 12,
                          decoration: BoxDecoration(
                            color: fatigue == null
                                ? AppTheme.surfaceRaised
                                : _colorForFatigue(fatigue.fatigueFraction),
                            shape: BoxShape.circle,
                            border: Border.all(color: AppTheme.border),
                          ),
                        ),
                        const SizedBox(width: 10),
                        Expanded(child: Text(label, style: Theme.of(context).textTheme.bodyMedium)),
                        Text(
                          fatigue == null ? 'No data yet' : _readinessLabel(fatigue),
                          style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 13),
                        ),
                        if (readyIn != null) ...[
                          const SizedBox(width: 8),
                          Text(
                            readyIn,
                            style: TextStyle(
                                color: Theme.of(context).colorScheme.onSurfaceVariant, fontSize: 12),
                          ),
                        ],
                        const SizedBox(width: 8),
                        Text(
                          '${(volume?.totalVolumeKg ?? 0).toStringAsFixed(0)} kg',
                          style: TextStyle(
                              color: Theme.of(context).colorScheme.onSurfaceVariant, fontSize: 12),
                        ),
                      ],
                    ),
                  );
                }),
                if (untagged.isNotEmpty)
                  Padding(
                    padding: const EdgeInsets.only(top: 10),
                    child: Text(
                      '${untagged.length} exercise${untagged.length == 1 ? '' : 's'} not yet tagged -- open one from Exercise progress to tag it.',
                      style: TextStyle(
                          color: Theme.of(context).colorScheme.onSurfaceVariant, fontSize: 12),
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
