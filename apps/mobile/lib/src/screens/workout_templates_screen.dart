import 'package:flutter/material.dart';

import '../models/workout_template.dart';
import '../services/gym_service.dart';

class WorkoutTemplatesScreen extends StatefulWidget {
  const WorkoutTemplatesScreen({super.key});

  @override
  State<WorkoutTemplatesScreen> createState() => _WorkoutTemplatesScreenState();
}

class _WorkoutTemplatesScreenState extends State<WorkoutTemplatesScreen> {
  final GymService _service = GymService();
  late Future<List<WorkoutTemplate>> _future;

  @override
  void initState() {
    super.initState();
    _future = _service.fetchTemplates();
  }

  Future<void> _refresh() async {
    final next = _service.fetchTemplates();
    setState(() {
      _future = next;
    });
    await next;
  }

  Future<void> _create() async {
    final saved = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      builder: (_) => const _TemplateForm(),
    );
    if (saved == true) await _refresh();
  }

  Future<void> _delete(WorkoutTemplate template) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('Delete template?'),
        content: Text('Delete ${template.name}? Existing workouts will not be affected.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(context, true), child: const Text('Delete')),
        ],
      ),
    );
    if (confirmed != true) return;
    await _service.deleteTemplate(template.id);
    await _refresh();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Workout templates'),
        actions: [IconButton(onPressed: _create, icon: const Icon(Icons.add_rounded))],
      ),
      body: FutureBuilder<List<WorkoutTemplate>>(
        future: _future,
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting) {
            return const Center(child: CircularProgressIndicator());
          }
          final templates = snapshot.data ?? const <WorkoutTemplate>[];
          if (templates.isEmpty) {
            return Center(
              child: Padding(
                padding: const EdgeInsets.all(28),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Icon(Icons.view_list_rounded, size: 52),
                    const SizedBox(height: 14),
                    Text('No templates yet', style: Theme.of(context).textTheme.titleLarge),
                    const SizedBox(height: 8),
                    const Text('Create Push, Pull, Legs or any routine you use regularly.'),
                    const SizedBox(height: 18),
                    FilledButton.icon(onPressed: _create, icon: const Icon(Icons.add_rounded), label: const Text('Create template')),
                  ],
                ),
              ),
            );
          }
          return RefreshIndicator(
            onRefresh: _refresh,
            child: ListView.builder(
              padding: const EdgeInsets.all(20),
              itemCount: templates.length,
              itemBuilder: (context, index) {
                final template = templates[index];
                return Card(
                  margin: const EdgeInsets.only(bottom: 12),
                  child: ListTile(
                    leading: const CircleAvatar(child: Icon(Icons.fitness_center_rounded)),
                    title: Text(template.name),
                    subtitle: Text(template.exercises.map((item) => '${item.exercise} ${item.targetSets}×${item.targetReps}').join(' · ')),
                    trailing: PopupMenuButton<String>(
                      onSelected: (value) {
                        if (value == 'start') Navigator.pop(context, template);
                        if (value == 'delete') _delete(template);
                      },
                      itemBuilder: (_) => const [
                        PopupMenuItem(value: 'start', child: Text('Start workout')),
                        PopupMenuItem(value: 'delete', child: Text('Delete')),
                      ],
                    ),
                    onTap: () => Navigator.pop(context, template),
                  ),
                );
              },
            ),
          );
        },
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _create,
        icon: const Icon(Icons.add_rounded),
        label: const Text('Template'),
      ),
    );
  }
}

class _TemplateForm extends StatefulWidget {
  const _TemplateForm();

  @override
  State<_TemplateForm> createState() => _TemplateFormState();
}

class _TemplateFormState extends State<_TemplateForm> {
  final GymService _service = GymService();
  final TextEditingController _name = TextEditingController();
  final List<_TemplateExerciseDraft> _exercises = [_TemplateExerciseDraft()];
  bool _saving = false;

  @override
  void dispose() {
    _name.dispose();
    for (final item in _exercises) item.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    if (_name.text.trim().isEmpty) return;
    final exercises = <WorkoutTemplateExercise>[];
    for (final item in _exercises) {
      final sets = int.tryParse(item.sets.text);
      final reps = int.tryParse(item.reps.text);
      final rir = item.rir.text.isEmpty ? null : int.tryParse(item.rir.text);
      if (item.exercise.text.trim().isEmpty || sets == null || reps == null) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Complete each exercise, sets and reps field.')));
        return;
      }
      exercises.add(WorkoutTemplateExercise(exercise: item.exercise.text.trim(), targetSets: sets, targetReps: reps, targetRir: rir));
    }
    setState(() => _saving = true);
    try {
      await _service.createTemplate(name: _name.text.trim(), exercises: exercises);
      if (mounted) Navigator.pop(context, true);
    } catch (error) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(error.toString())));
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.fromLTRB(20, 20, 20, MediaQuery.viewInsetsOf(context).bottom + 20),
      child: ListView(
        children: [
          Text('Create workout template', style: Theme.of(context).textTheme.headlineSmall),
          const SizedBox(height: 16),
          TextField(controller: _name, decoration: const InputDecoration(labelText: 'Template name', hintText: 'Push A, Upper, Legs…')),
          const SizedBox(height: 18),
          ...List.generate(_exercises.length, (index) {
            final item = _exercises[index];
            return Card(
              margin: const EdgeInsets.only(bottom: 12),
              child: Padding(
                padding: const EdgeInsets.all(14),
                child: Column(
                  children: [
                    TextField(controller: item.exercise, decoration: InputDecoration(labelText: 'Exercise ${index + 1}')),
                    const SizedBox(height: 10),
                    Row(children: [
                      Expanded(child: TextField(controller: item.sets, keyboardType: TextInputType.number, decoration: const InputDecoration(labelText: 'Sets'))),
                      const SizedBox(width: 8),
                      Expanded(child: TextField(controller: item.reps, keyboardType: TextInputType.number, decoration: const InputDecoration(labelText: 'Reps'))),
                      const SizedBox(width: 8),
                      Expanded(child: TextField(controller: item.rir, keyboardType: TextInputType.number, decoration: const InputDecoration(labelText: 'RIR'))),
                    ]),
                  ],
                ),
              ),
            );
          }),
          OutlinedButton.icon(
            onPressed: () => setState(() => _exercises.add(_TemplateExerciseDraft())),
            icon: const Icon(Icons.add_rounded),
            label: const Text('Add exercise'),
          ),
          const SizedBox(height: 12),
          FilledButton(onPressed: _saving ? null : _save, child: Text(_saving ? 'Saving…' : 'Save template')),
        ],
      ),
    );
  }
}

class _TemplateExerciseDraft {
  final exercise = TextEditingController();
  final sets = TextEditingController(text: '3');
  final reps = TextEditingController(text: '8');
  final rir = TextEditingController(text: '2');

  void dispose() {
    exercise.dispose();
    sets.dispose();
    reps.dispose();
    rir.dispose();
  }
}
