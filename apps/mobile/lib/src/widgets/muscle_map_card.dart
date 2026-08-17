import 'package:flutter/material.dart';

import '../models/exercise_progress.dart';
import '../services/gym_service.dart';
import '../theme/app_theme.dart';

class MuscleMapCard extends StatefulWidget {
  const MuscleMapCard({this.days = 7, super.key});

  final int days;

  @override
  State<MuscleMapCard> createState() => _MuscleMapCardState();
}

class _MuscleMapCardState extends State<MuscleMapCard> {
  final GymService _service = GymService();
  late Future<List<MuscleGroupWorkload>> _workloadFuture;
  late Future<List<String>> _untaggedFuture;

  @override
  void initState() {
    super.initState();
    _workloadFuture = _service.fetchMuscleGroupWorkload(days: widget.days);
    _untaggedFuture = _service.fetchUntaggedExercises();
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<List<MuscleGroupWorkload>>(
      future: _workloadFuture,
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
        final workload = snapshot.data;
        if (snapshot.hasError || workload == null) {
          return const SizedBox.shrink();
        }
        final maxVolume = workload.fold<double>(
            0, (max, item) => item.totalVolumeKg > max ? item.totalVolumeKg : max);

        return Card(
          child: Padding(
            padding: const EdgeInsets.all(20),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Muscle map', style: Theme.of(context).textTheme.titleMedium),
                const SizedBox(height: 4),
                Text(
                  'Weekly volume by muscle group, for tagged exercises.',
                  style: TextStyle(color: Theme.of(context).colorScheme.onSurfaceVariant),
                ),
                const SizedBox(height: 14),
                if (maxVolume == 0)
                  const Padding(
                    padding: EdgeInsets.symmetric(vertical: 4),
                    child: Text('No tagged workouts in this window yet.'),
                  )
                else
                  ...workload.map((item) => _MuscleGroupBar(item: item, maxVolume: maxVolume)),
                FutureBuilder<List<String>>(
                  future: _untaggedFuture,
                  builder: (context, untaggedSnapshot) {
                    final untagged = untaggedSnapshot.data ?? const <String>[];
                    if (untagged.isEmpty) return const SizedBox.shrink();
                    return Padding(
                      padding: const EdgeInsets.only(top: 10),
                      child: Text(
                        '${untagged.length} exercise${untagged.length == 1 ? '' : 's'} not yet tagged -- open one from Exercise progress to tag it.',
                        style: TextStyle(
                            color: Theme.of(context).colorScheme.onSurfaceVariant, fontSize: 12),
                      ),
                    );
                  },
                ),
              ],
            ),
          ),
        );
      },
    );
  }
}

class _MuscleGroupBar extends StatelessWidget {
  const _MuscleGroupBar({required this.item, required this.maxVolume});

  final MuscleGroupWorkload item;
  final double maxVolume;

  @override
  Widget build(BuildContext context) {
    final fraction = maxVolume == 0 ? 0.0 : (item.totalVolumeKg / maxVolume).clamp(0.0, 1.0);
    final label = item.muscleGroup[0].toUpperCase() + item.muscleGroup.substring(1);
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(child: Text(label, style: Theme.of(context).textTheme.bodyMedium)),
              Text(
                '${item.totalVolumeKg.toStringAsFixed(0)} kg',
                style: const TextStyle(fontWeight: FontWeight.w700),
              ),
            ],
          ),
          const SizedBox(height: 4),
          ClipRRect(
            borderRadius: BorderRadius.circular(4),
            child: LinearProgressIndicator(
              value: fraction,
              minHeight: 8,
              backgroundColor: AppTheme.surfaceRaised,
              valueColor: const AlwaysStoppedAnimation(AppTheme.primaryBright),
            ),
          ),
        ],
      ),
    );
  }
}
