import 'package:flutter/material.dart';

import '../models/exercise_progress.dart';
import '../services/gym_service.dart';
import '../widgets/metric_line_chart.dart';

class ExerciseProgressScreen extends StatefulWidget {
  const ExerciseProgressScreen({super.key});

  @override
  State<ExerciseProgressScreen> createState() => _ExerciseProgressScreenState();
}

class _ExerciseProgressScreenState extends State<ExerciseProgressScreen> {
  final GymService _service = GymService();
  late Future<List<ExerciseProgress>> _future;

  @override
  void initState() {
    super.initState();
    _future = _service.fetchExercises();
  }

  Future<void> _refresh() async {
    final next = _service.fetchExercises();
    setState(() {
      _future = next;
    });
    await next;
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Exercise progress')),
      body: FutureBuilder<List<ExerciseProgress>>(
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
          final exercises = snapshot.data ?? const <ExerciseProgress>[];
          if (exercises.isEmpty) {
            return const Center(
              child: Padding(
                padding: EdgeInsets.all(28),
                child: Text(
                    'Log workouts to begin building exercise progression data.'),
              ),
            );
          }
          return RefreshIndicator(
            onRefresh: _refresh,
            child: ListView.separated(
              padding: const EdgeInsets.all(20),
              itemCount: exercises.length,
              separatorBuilder: (_, __) => const SizedBox(height: 12),
              itemBuilder: (context, index) {
                final item = exercises[index];
                return Card(
                  child: ListTile(
                    leading: const CircleAvatar(
                        child: Icon(Icons.trending_up_rounded)),
                    title: Text(item.exercise),
                    subtitle: Text(
                      '${item.workoutCount} workouts · ${item.setCount} sets · latest ${item.latestWeightKg.toStringAsFixed(1)} kg × ${item.latestReps}',
                    ),
                    trailing: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      crossAxisAlignment: CrossAxisAlignment.end,
                      children: [
                        Text(
                            '${item.bestEstimatedOneRepMaxKg.toStringAsFixed(1)} kg'),
                        const Text('best e1RM'),
                      ],
                    ),
                    onTap: () => Navigator.of(context).push<void>(
                      MaterialPageRoute<void>(
                        builder: (_) => _ExerciseDetailScreen(progress: item),
                      ),
                    ),
                  ),
                );
              },
            ),
          );
        },
      ),
    );
  }
}

class _ExerciseDetailScreen extends StatefulWidget {
  const _ExerciseDetailScreen({required this.progress});

  final ExerciseProgress progress;

  @override
  State<_ExerciseDetailScreen> createState() => _ExerciseDetailScreenState();
}

class _ExerciseDetailScreenState extends State<_ExerciseDetailScreen> {
  final GymService _service = GymService();
  late Future<ProgressiveOverloadSuggestion> _suggestion;
  late Future<DeloadSuggestion> _deload;
  late String? _muscleGroup;
  bool _tagging = false;

  @override
  void initState() {
    super.initState();
    _suggestion = _service.fetchSuggestion(widget.progress.exercise);
    _deload = _service.fetchDeloadSuggestion(widget.progress.exercise);
    _muscleGroup = widget.progress.muscleGroup;
  }

  Future<void> _pickMuscleGroup() async {
    setState(() => _tagging = true);
    try {
      final groups = await _service.fetchMuscleGroups();
      if (!mounted) return;
      final selected = await showDialog<String>(
        context: context,
        builder: (_) => SimpleDialog(
          title: const Text('Tag muscle group'),
          children: groups
              .map((group) => SimpleDialogOption(
                    onPressed: () => Navigator.pop(context, group),
                    child: Text(group[0].toUpperCase() + group.substring(1)),
                  ))
              .toList(growable: false),
        ),
      );
      if (selected == null) return;
      await _service.tagExercise(widget.progress.exercise, selected);
      if (mounted) setState(() => _muscleGroup = selected);
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Could not save muscle group tag.')),
        );
      }
    } finally {
      if (mounted) setState(() => _tagging = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final progress = widget.progress;
    final chartSamples = progress.history
        .map((point) => MetricSample(
              time: point.date,
              value: point.estimatedOneRepMaxKg,
            ))
        .toList(growable: false);

    return Scaffold(
      appBar: AppBar(title: Text(progress.exercise)),
      body: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          ActionChip(
            avatar: _tagging
                ? const SizedBox(
                    width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2))
                : const Icon(Icons.fitness_center_rounded, size: 18),
            label: Text(_muscleGroup == null
                ? 'Tag muscle group'
                : _muscleGroup![0].toUpperCase() + _muscleGroup!.substring(1)),
            onPressed: _tagging ? null : _pickMuscleGroup,
          ),
          const SizedBox(height: 14),
          Wrap(
            spacing: 12,
            runSpacing: 12,
            children: [
              _RecordCard(
                  label: 'Heaviest weight',
                  value: '${progress.bestWeightKg.toStringAsFixed(1)} kg'),
              _RecordCard(
                  label: 'Best estimated 1RM',
                  value:
                      '${progress.bestEstimatedOneRepMaxKg.toStringAsFixed(1)} kg'),
              _RecordCard(
                  label: 'Best set volume',
                  value: '${progress.bestSetVolumeKg.toStringAsFixed(0)} kg'),
            ],
          ),
          const SizedBox(height: 18),
          FutureBuilder<ProgressiveOverloadSuggestion>(
            future: _suggestion,
            builder: (context, snapshot) {
              if (!snapshot.hasData) return const SizedBox.shrink();
              final suggestion = snapshot.data!;
              if (suggestion.status == ProgressiveOverloadStatus.noData) {
                return const SizedBox.shrink();
              }
              final icon =
                  suggestion.status == ProgressiveOverloadStatus.progress
                      ? Icons.trending_up_rounded
                      : Icons.replay_rounded;
              return Padding(
                padding: const EdgeInsets.only(bottom: 18),
                child: Card(
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Icon(icon,
                            color: Theme.of(context).colorScheme.primary),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                'Next session suggestion',
                                style: Theme.of(context).textTheme.titleSmall,
                              ),
                              const SizedBox(height: 4),
                              Text(suggestion.rationale),
                            ],
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              );
            },
          ),
          FutureBuilder<DeloadSuggestion>(
            future: _deload,
            builder: (context, snapshot) {
              if (!snapshot.hasData) return const SizedBox.shrink();
              final deload = snapshot.data!;
              if (deload.status != DeloadStatus.deloadRecommended) {
                return const SizedBox.shrink();
              }
              return Padding(
                padding: const EdgeInsets.only(bottom: 18),
                child: Card(
                  color: Theme.of(context).colorScheme.errorContainer,
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Icon(Icons.battery_2_bar_rounded,
                            color: Theme.of(context).colorScheme.onErrorContainer),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                'Consider a deload',
                                style: Theme.of(context).textTheme.titleSmall?.copyWith(
                                      color: Theme.of(context).colorScheme.onErrorContainer,
                                    ),
                              ),
                              const SizedBox(height: 4),
                              Text(
                                deload.rationale,
                                style: TextStyle(
                                  color: Theme.of(context).colorScheme.onErrorContainer,
                                ),
                              ),
                            ],
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              );
            },
          ),
          MetricLineChart(
            title: 'Estimated 1RM trend',
            samples: chartSamples,
            valueSuffix: ' kg',
          ),
          const SizedBox(height: 20),
          Text('Set history', style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: 10),
          ...progress.history.reversed.map(
            (point) => Card(
              child: ListTile(
                title: Text(
                    '${point.weightKg.toStringAsFixed(1)} kg × ${point.reps}'),
                subtitle: Text(
                  '${point.workoutName} · ${point.date.day}/${point.date.month}/${point.date.year}${point.rir == null ? '' : ' · ${point.rir} RIR'}',
                ),
                trailing: Text(
                    '${point.estimatedOneRepMaxKg.toStringAsFixed(1)} kg e1RM'),
              ),
            ),
          ),
          const SizedBox(height: 10),
          Text(
            'Estimated 1RM uses the Epley formula and is intended for personal trend tracking rather than an exact maximum-lift prediction.',
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
                  color: Theme.of(context).colorScheme.onSurfaceVariant,
                ),
          ),
        ],
      ),
    );
  }
}

class _RecordCard extends StatelessWidget {
  const _RecordCard({required this.label, required this.value});
  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: 180,
      child: Card(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(value, style: Theme.of(context).textTheme.titleLarge),
              const SizedBox(height: 4),
              Text(label),
            ],
          ),
        ),
      ),
    );
  }
}
