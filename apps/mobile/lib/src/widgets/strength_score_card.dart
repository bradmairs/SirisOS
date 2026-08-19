import 'package:flutter/material.dart';

import '../models/exercise_progress.dart';
import '../services/gym_service.dart';
import '../theme/app_theme.dart';

class StrengthScoreCard extends StatefulWidget {
  const StrengthScoreCard({super.key});

  @override
  State<StrengthScoreCard> createState() => _StrengthScoreCardState();
}

class _StrengthScoreCardState extends State<StrengthScoreCard> {
  static const _groupOrder = ['chest', 'back', 'legs', 'shoulders', 'arms', 'core'];

  final GymService _service = GymService();
  late Future<StrengthScore> _future;

  @override
  void initState() {
    super.initState();
    _future = _service.fetchStrengthScore();
  }

  static String _percent(double? value) => value == null ? '--' : '${(value * 100).round()}%';

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<StrengthScore>(
      future: _future,
      builder: (context, snapshot) {
        if (snapshot.connectionState == ConnectionState.waiting) {
          return const Card(
            child: Padding(
              padding: EdgeInsets.all(20),
              child: SizedBox(
                height: 40,
                child: Center(child: CircularProgressIndicator(strokeWidth: 2)),
              ),
            ),
          );
        }
        final score = snapshot.data;
        if (snapshot.hasError || score == null) {
          return const SizedBox.shrink();
        }
        final byGroup = {for (final item in score.byMuscleGroup) item.muscleGroup: item};

        return Card(
          child: Padding(
            padding: const EdgeInsets.all(20),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Expanded(
                      child: Text('Strength score', style: Theme.of(context).textTheme.titleMedium),
                    ),
                    if (score.overallScore != null)
                      Text(
                        _percent(score.overallScore),
                        style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                              fontWeight: FontWeight.w800,
                              color: AppTheme.primaryBright,
                            ),
                      ),
                  ],
                ),
                const SizedBox(height: 4),
                Text(
                  'Current estimated 1RM versus your own all-time best, per lift -- '
                  'never compared to anyone else.',
                  style: TextStyle(color: Theme.of(context).colorScheme.onSurfaceVariant, fontSize: 12),
                ),
                const SizedBox(height: 14),
                if (score.overallScore == null)
                  const Padding(
                    padding: EdgeInsets.symmetric(vertical: 4),
                    child: Text('Log and tag a few exercises to see your strength score.'),
                  )
                else
                  ..._groupOrder.map((group) {
                    final item = byGroup[group];
                    final label = group[0].toUpperCase() + group.substring(1);
                    return Padding(
                      padding: const EdgeInsets.symmetric(vertical: 5),
                      child: Row(
                        children: [
                          Expanded(child: Text(label, style: Theme.of(context).textTheme.bodyMedium)),
                          if (item != null && item.exerciseCount > 0) ...[
                            Text(
                              '${item.exerciseCount} lift${item.exerciseCount == 1 ? '' : 's'}',
                              style: TextStyle(
                                  color: Theme.of(context).colorScheme.onSurfaceVariant, fontSize: 12),
                            ),
                            const SizedBox(width: 10),
                            Text(_percent(item.score), style: const TextStyle(fontWeight: FontWeight.w700)),
                          ] else
                            Text(
                              'No data yet',
                              style: TextStyle(color: Theme.of(context).colorScheme.onSurfaceVariant),
                            ),
                        ],
                      ),
                    );
                  }),
              ],
            ),
          ),
        );
      },
    );
  }
}
