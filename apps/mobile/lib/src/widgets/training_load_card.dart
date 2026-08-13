import 'package:flutter/material.dart';

import '../models/training_load.dart';
import '../services/training_load_service.dart';
import '../theme/app_theme.dart';

class TrainingLoadCard extends StatefulWidget {
  const TrainingLoadCard({super.key});

  @override
  State<TrainingLoadCard> createState() => _TrainingLoadCardState();
}

class _TrainingLoadCardState extends State<TrainingLoadCard> {
  final _service = TrainingLoadService();
  late Future<WeeklyTrainingLoad> _future;

  @override
  void initState() {
    super.initState();
    _future = _service.fetchWeeklyLoad();
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<WeeklyTrainingLoad>(
      future: _future,
      builder: (context, snapshot) {
        if (snapshot.connectionState == ConnectionState.waiting) {
          return const Card(
            child: Padding(
              padding: EdgeInsets.all(20),
              child: SizedBox(
                height: 40,
                child:
                    Center(child: CircularProgressIndicator(strokeWidth: 2)),
              ),
            ),
          );
        }
        if (snapshot.hasError || !snapshot.hasData) {
          return const SizedBox.shrink();
        }
        final load = snapshot.data!;
        return Card(
          child: Padding(
            padding: const EdgeInsets.all(20),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Expanded(
                      child: Text('Weekly training load',
                          style: Theme.of(context).textTheme.titleMedium),
                    ),
                    if (load.combinedIndex != null)
                      Text(
                        '${load.combinedIndex!.round()}',
                        style: Theme.of(context)
                            .textTheme
                            .headlineSmall
                            ?.copyWith(
                                fontWeight: FontWeight.w800,
                                color: AppTheme.primaryBright),
                      ),
                  ],
                ),
                const SizedBox(height: 6),
                Text(
                  load.assessment,
                  style: TextStyle(
                      color: Theme.of(context).colorScheme.onSurfaceVariant),
                ),
                const SizedBox(height: 14),
                Row(
                  children: [
                    Expanded(
                      child: _ModalityRatio(
                          label: 'Running', ratio: load.runningRatio),
                    ),
                    const SizedBox(width: 16),
                    Expanded(
                      child:
                          _ModalityRatio(label: 'Strength', ratio: load.gymRatio),
                    ),
                  ],
                ),
              ],
            ),
          ),
        );
      },
    );
  }
}

class _ModalityRatio extends StatelessWidget {
  const _ModalityRatio({required this.label, required this.ratio});

  final String label;
  final double? ratio;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label,
            style:
                TextStyle(color: Theme.of(context).colorScheme.onSurfaceVariant)),
        const SizedBox(height: 2),
        Text(
          ratio == null ? 'Not enough history yet' : '${ratio!.round()}% of usual',
          style: Theme.of(context)
              .textTheme
              .titleMedium
              ?.copyWith(fontWeight: FontWeight.w700),
        ),
      ],
    );
  }
}
