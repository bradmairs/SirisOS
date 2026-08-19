import 'package:flutter/material.dart';

import '../models/exercise_progress.dart';
import '../models/gym_workout.dart';
import '../models/workout_template.dart';
import '../services/gym_service.dart';
import '../widgets/metric_line_chart.dart';
import '../widgets/muscle_map_card.dart';
import '../widgets/strength_score_card.dart';
import '../widgets/training_heatmap_card.dart';
import '../widgets/training_load_card.dart';
import 'exercise_progress_screen.dart';
import 'workout_templates_screen.dart';

class GymScreen extends StatefulWidget {
  const GymScreen({this.addRequest = 0, super.key});
  final int addRequest;

  @override
  State<GymScreen> createState() => _GymScreenState();
}

class _GymScreenState extends State<GymScreen> {
  final GymService _service = GymService();
  late Future<List<GymWorkout>> _future;

  @override
  void initState() {
    super.initState();
    _future = _service.fetchWorkouts();
  }

  @override
  void didUpdateWidget(covariant GymScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.addRequest != oldWidget.addRequest) {
      WidgetsBinding.instance.addPostFrameCallback((_) => _addWorkout());
    }
  }

  Future<void> _refresh() async {
    final next = _service.fetchWorkouts();
    setState(() {
      _future = next;
    });
    await next;
  }

  Future<void> _addWorkout([WorkoutTemplate? template]) async {
    final newRecords = await showModalBottomSheet<List<PersonalRecord>>(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      builder: (_) => _WorkoutForm(template: template),
    );
    if (newRecords == null) return;
    await _refresh();
    if (newRecords.isNotEmpty && mounted) {
      final summary = newRecords
          .map((item) => '${item.exercise} · ${item.recordType.label}')
          .join(', ');
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('🏆 New record: $summary')),
      );
    }
  }

  Future<void> _openTemplates() async {
    final template = await Navigator.of(context).push<WorkoutTemplate>(
      MaterialPageRoute<WorkoutTemplate>(
          builder: (_) => const WorkoutTemplatesScreen()),
    );
    if (template != null && mounted) await _addWorkout(template);
  }

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      child: FutureBuilder<List<GymWorkout>>(
        future: _future,
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting) {
            return const Center(child: CircularProgressIndicator());
          }
          final workouts = snapshot.data ?? const <GymWorkout>[];
          final chart = workouts.reversed
              .map((item) =>
                  MetricSample(time: item.date, value: item.totalVolumeKg))
              .toList(growable: false);
          final totalVolume =
              workouts.fold<double>(0, (sum, item) => sum + item.totalVolumeKg);

          return RefreshIndicator(
            onRefresh: _refresh,
            child: ListView(
              physics: const AlwaysScrollableScrollPhysics(),
              padding: const EdgeInsets.fromLTRB(20, 24, 20, 28),
              children: [
                Row(
                  children: [
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text('Gym',
                              style:
                                  Theme.of(context).textTheme.headlineMedium),
                          const SizedBox(height: 6),
                          Text(
                            'Workout logging and progressive overload tracking.',
                            style: TextStyle(
                                color: Theme.of(context)
                                    .colorScheme
                                    .onSurfaceVariant),
                          ),
                        ],
                      ),
                    ),
                    IconButton.filledTonal(
                      tooltip: 'Workout templates',
                      onPressed: _openTemplates,
                      icon: const Icon(Icons.view_list_rounded),
                    ),
                    const SizedBox(width: 8),
                    IconButton.filledTonal(
                      tooltip: 'Exercise progress',
                      onPressed: () => Navigator.of(context).push<void>(
                        MaterialPageRoute<void>(
                            builder: (_) => const ExerciseProgressScreen()),
                      ),
                      icon: const Icon(Icons.trending_up_rounded),
                    ),
                    const SizedBox(width: 8),
                    FilledButton.icon(
                      onPressed: _addWorkout,
                      icon: const Icon(Icons.add_rounded),
                      label: const Text('Workout'),
                    ),
                  ],
                ),
                const SizedBox(height: 20),
                const TrainingLoadCard(),
                const SizedBox(height: 20),
                const TrainingHeatmapCard(),
                const SizedBox(height: 20),
                const MuscleMapCard(),
                const SizedBox(height: 20),
                const StrengthScoreCard(),
                const SizedBox(height: 20),
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(20),
                    child: Wrap(
                      spacing: 32,
                      runSpacing: 16,
                      children: [
                        _Summary(
                            label: 'Workouts', value: '${workouts.length}'),
                        _Summary(
                            label: 'Total volume',
                            value: '${totalVolume.toStringAsFixed(0)} kg'),
                        _Summary(
                            label: 'Latest',
                            value: workouts.isEmpty
                                ? '—'
                                : '${workouts.first.totalVolumeKg.toStringAsFixed(0)} kg'),
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: 16),
                MetricLineChart(
                    title: 'Workout volume',
                    samples: chart,
                    valueSuffix: ' kg'),
                const SizedBox(height: 24),
                Text('Workout history',
                    style: Theme.of(context).textTheme.titleLarge),
                const SizedBox(height: 12),
                if (workouts.isEmpty)
                  const Card(
                    child: Padding(
                      padding: EdgeInsets.all(28),
                      child: Text(
                          'No workouts logged yet. Add your first session to begin tracking progress.'),
                    ),
                  )
                else
                  ...workouts.map(
                    (workout) => Padding(
                      padding: const EdgeInsets.only(bottom: 12),
                      child: Card(
                        child: ExpansionTile(
                          title: Text(workout.name),
                          subtitle: Text(
                              '${_dateLabel(workout.date)} · ${workout.sets.length} sets · ${workout.totalVolumeKg.toStringAsFixed(0)} kg'),
                          children: workout.sets
                              .map(
                                (set) => ListTile(
                                  dense: true,
                                  title: Text(set.exercise),
                                  subtitle: Text(
                                      '${set.weightKg.toStringAsFixed(1)} kg × ${set.reps}${set.rir == null ? '' : ' · ${set.rir} RIR'}'),
                                  trailing: Text(
                                      '${set.volumeKg.toStringAsFixed(0)} kg'),
                                ),
                              )
                              .toList(),
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

  static String _dateLabel(DateTime value) =>
      '${value.day}/${value.month}/${value.year}';
}

class _Summary extends StatelessWidget {
  const _Summary({required this.label, required this.value});
  final String label;
  final String value;

  @override
  Widget build(BuildContext context) => SizedBox(
        width: 120,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(value, style: Theme.of(context).textTheme.titleLarge),
            Text(label),
          ],
        ),
      );
}

class _WorkoutForm extends StatefulWidget {
  const _WorkoutForm({this.template});
  final WorkoutTemplate? template;

  @override
  State<_WorkoutForm> createState() => _WorkoutFormState();
}

class _WorkoutFormState extends State<_WorkoutForm> {
  final GymService _service = GymService();
  final _name = TextEditingController();
  final _notes = TextEditingController();
  final List<_SetDraft> _sets = [];
  bool _saving = false;
  bool _loadingSuggestions = false;
  String? _suggestionMessage;

  @override
  void initState() {
    super.initState();
    final template = widget.template;
    if (template == null) {
      _sets.add(_SetDraft());
      return;
    }
    _name.text = template.name;
    for (final exercise in template.exercises) {
      for (var index = 0; index < exercise.targetSets; index++) {
        _sets.add(
          _SetDraft(
            exercise: exercise.exercise,
            reps: '${exercise.targetReps}',
            rir: exercise.targetRir == null ? '' : '${exercise.targetRir}',
          ),
        );
      }
    }
    _loadSuggestedWeights();
  }

  Future<void> _loadSuggestedWeights() async {
    final template = widget.template;
    if (template == null) return;
    setState(() => _loadingSuggestions = true);
    try {
      var populated = 0;
      for (final templateExercise in template.exercises) {
        final ProgressiveOverloadSuggestion suggestion;
        try {
          suggestion =
              await _service.fetchSuggestion(templateExercise.exercise);
        } catch (_) {
          continue;
        }
        if (suggestion.status == ProgressiveOverloadStatus.noData ||
            suggestion.suggestedWeightKg == null) {
          continue;
        }
        final label = _weightLabel(suggestion.suggestedWeightKg!);
        for (final set in _sets.where(
          (item) =>
              item.exercise.text.trim().toLowerCase() ==
              templateExercise.exercise.trim().toLowerCase(),
        )) {
          set.weight.text = label;
          if (suggestion.suggestedReps != null) {
            set.reps.text = '${suggestion.suggestedReps}';
          }
          set.suggestion = suggestion.rationale;
          populated++;
        }
      }
      if (!mounted) return;
      setState(() {
        _loadingSuggestions = false;
        _suggestionMessage = populated == 0
            ? 'No matching exercise history was found. Enter today’s weights manually.'
            : 'Suggested weights use your latest matching sets and remain fully editable.';
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _loadingSuggestions = false;
        _suggestionMessage =
            'Could not load previous exercise history. Enter today’s weights manually.';
      });
    }
  }

  static String _weightLabel(double value) => value == value.roundToDouble()
      ? value.toStringAsFixed(0)
      : value.toStringAsFixed(1);

  @override
  void dispose() {
    _name.dispose();
    _notes.dispose();
    for (final item in _sets) item.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    final sets = <GymSet>[];
    for (final item in _sets) {
      final weight = double.tryParse(item.weight.text);
      final reps = int.tryParse(item.reps.text);
      final rir = item.rir.text.isEmpty ? null : int.tryParse(item.rir.text);
      if (item.exercise.text.trim().isEmpty || weight == null || reps == null) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
              content: Text('Complete every exercise, weight and reps field.')),
        );
        return;
      }
      sets.add(GymSet(
          exercise: item.exercise.text.trim(),
          weightKg: weight,
          reps: reps,
          rir: rir));
    }
    if (_name.text.trim().isEmpty) return;
    setState(() => _saving = true);
    try {
      final workout = await _service.createWorkout(
        date: DateTime.now(),
        name: _name.text.trim(),
        notes: _notes.text.trim(),
        sets: sets,
      );
      if (mounted) Navigator.pop(context, workout.newRecords);
    } catch (error) {
      if (mounted)
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(error.toString())));
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.fromLTRB(
          20, 20, 20, MediaQuery.viewInsetsOf(context).bottom + 20),
      child: ListView(
        children: [
          Text(
              widget.template == null
                  ? 'Log workout'
                  : 'Start ${widget.template!.name}',
              style: Theme.of(context).textTheme.headlineSmall),
          if (widget.template != null) ...[
            const SizedBox(height: 6),
            Text(
              'Targets are pre-filled. SirisOS uses your latest matching exercise history to suggest a starting weight.',
              style: TextStyle(
                  color: Theme.of(context).colorScheme.onSurfaceVariant),
            ),
            const SizedBox(height: 10),
            if (_loadingSuggestions) const LinearProgressIndicator(),
            if (_suggestionMessage != null) ...[
              const SizedBox(height: 8),
              Text(
                _suggestionMessage!,
                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                      color: Theme.of(context).colorScheme.onSurfaceVariant,
                    ),
              ),
            ],
          ],
          const SizedBox(height: 16),
          TextField(
              controller: _name,
              decoration: const InputDecoration(
                  labelText: 'Workout name',
                  hintText: 'Upper body, Push, Legs…')),
          const SizedBox(height: 12),
          TextField(
              controller: _notes,
              decoration: const InputDecoration(labelText: 'Notes (optional)')),
          const SizedBox(height: 20),
          ...List.generate(
            _sets.length,
            (index) => Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: Card(
                child: Padding(
                  padding: const EdgeInsets.all(14),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      TextField(
                          controller: _sets[index].exercise,
                          decoration: InputDecoration(
                              labelText: 'Exercise ${index + 1}')),
                      const SizedBox(height: 10),
                      Row(
                        children: [
                          Expanded(
                              child: TextField(
                                  controller: _sets[index].weight,
                                  keyboardType:
                                      const TextInputType.numberWithOptions(
                                          decimal: true),
                                  decoration: const InputDecoration(
                                      labelText: 'Weight kg'))),
                          const SizedBox(width: 8),
                          Expanded(
                              child: TextField(
                                  controller: _sets[index].reps,
                                  keyboardType: TextInputType.number,
                                  decoration: const InputDecoration(
                                      labelText: 'Reps'))),
                          const SizedBox(width: 8),
                          Expanded(
                              child: TextField(
                                  controller: _sets[index].rir,
                                  keyboardType: TextInputType.number,
                                  decoration:
                                      const InputDecoration(labelText: 'RIR'))),
                        ],
                      ),
                      if (_sets[index].suggestion != null) ...[
                        const SizedBox(height: 8),
                        Text(
                          _sets[index].suggestion!,
                          style: Theme.of(context)
                              .textTheme
                              .bodySmall
                              ?.copyWith(
                                color: Theme.of(context).colorScheme.primary,
                              ),
                        ),
                      ],
                    ],
                  ),
                ),
              ),
            ),
          ),
          OutlinedButton.icon(
            onPressed: () => setState(() => _sets.add(_SetDraft())),
            icon: const Icon(Icons.add_rounded),
            label: const Text('Add set'),
          ),
          const SizedBox(height: 12),
          FilledButton(
              onPressed: _saving ? null : _save,
              child: Text(_saving ? 'Saving…' : 'Save workout')),
        ],
      ),
    );
  }
}

class _SetDraft {
  _SetDraft(
      {String exercise = '',
      String weight = '',
      String reps = '',
      String rir = ''}) {
    this.exercise.text = exercise;
    this.weight.text = weight;
    this.reps.text = reps;
    this.rir.text = rir;
  }

  final exercise = TextEditingController();
  final weight = TextEditingController();
  final reps = TextEditingController();
  final rir = TextEditingController();
  String? suggestion;

  void dispose() {
    exercise.dispose();
    weight.dispose();
    reps.dispose();
    rir.dispose();
  }
}
